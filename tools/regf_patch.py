#!/usr/bin/env python3
"""
regf_patch — surgical in-place editing of Windows registry hives (BCD, SYSTEM, ...)
with byte-level confinement: the output hive is byte-for-byte identical to the input
except inside explicitly targeted regions. No cell repacking, no header rewriting,
no hbin restructuring. This is the only editing mode we trust after two real-world
boot failures caused by repacking writers (python-hivex commit) whose output Windows
bootmgr refused despite passing structural checks.

Operations
----------
patch-guid-in-multisz <hive> <old-guid> <new-guid> [--occurrence N] [--all] --dry-run
    Replace the UTF-16LE encoding of <old-guid> with <new-guid> (same 78-byte length)
    at selected occurrence(s). The tool refuses to run unless:
      * both GUIDs are 38 chars
      * replacement length equals original length
      * the patched byte range is reported and verified afterwards
verify-region <patched> <original>  -> prints every differing byte range

Exit codes: 0 ok, 1 refused/failed, 2 usage.
"""
import sys, re, struct, hashlib

GUID_RE = re.compile(r'^\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}$')

def die(msg, code=1):
    print(f"REFUSED: {msg}", file=sys.stderr); sys.exit(code)

def load(p):
    with open(p,'rb') as f: return bytearray(f.read())

def check_regf(data):
    if data[:4] != b'regf': die("not a regf hive (magic mismatch)")
    s1, s2 = struct.unpack_from('<II', data, 4)
    if s1 != s2: print("NOTE: hive dirty (seq1!=seq2); patching bytes only — consider LOG quarantine")

def occurrences(data, pattern):
    out=[]; off=0
    while True:
        i = data.find(pattern, off)
        if i < 0: break
        out.append(i); off = i + 1
    return out

def sha256(b): return hashlib.sha256(b).hexdigest()

def main():
    a = sys.argv[1:]
    if not a or a[0] in ('-h','--help'): print(__doc__); return 0
    cmd = a[0]
    if cmd == 'patch-guid-in-multisz':
        args=[x for x in a[1:] if not x.startswith('--')]
        flags=set(x for x in a[1:] if x.startswith('--'))
        dry = '--dry-run' in flags
        if len(args) < 3: print(__doc__); return 2
        path, old, new = args[0], args[1], args[2]
        for g in (old, new):
            if not GUID_RE.match(g): die(f"not a plain GUID: {g}")
        gb_old, gb_new = utf16(old), utf16(new)
        if len(gb_old) != len(gb_new): die("GUID lengths differ; same-length patching only")
        data = load(path); check_regf(data)
        occs = occurrences(data, gb_old)
        if not occs: die("GUID not found in hive")
        # cluster detection: consecutive GUIDs of a multi_sz sit within (len+2) bytes of each other
        keep = gb_new if '--occurrence' in flags else None
        sel = []
        if '--all' in flags:
            sel = occs
        else:
            # multi_sz membership: GUIDs of one multi_sz value are contiguous —
            # a neighbor GUID starts exactly at ±(len+2) bytes (utf16 GUID + NUL separator)
            L = len(gb_old)
            occset = set(occs)
            for o in occs:
                def is_guid(off):
                    if off < 0 or off + L > len(data): return False
                    s = bytes(data[off:off+L]).decode('utf-16-le', errors='ignore')
                    return GUID_RE.match(s) is not None
                # right neighbor: GUID begins at o+L+2 (this GUID + NUL separator)
                # left neighbor: GUID ending at o-2, starting at o-L-2
                if is_guid(o + L + 2) or is_guid(o - L - 2):
                    sel.append(o)
            if not sel:
                die("no contiguous multi_sz occurrence found; use --all to override")
        print(f"patch targets ({len(sel)}/{len(occs)} occurrences):", [hex(o) for o in sel])
        if dry:
            print("dry-run: no changes written"); return 0
        before = sha256(bytes(data))
        ranges=[]
        for o in sel:
            data[o:o+len(gb_old)] = gb_new
            ranges.append((o, o+len(gb_old)))
        # verify confinement
        orig = load(path)
        diffs=[i for i in range(min(len(orig),len(data))) if orig[i]!=data[i]]
        assert all(any(s<=i<e for s,e in ranges) for i in diffs), "diff outside target ranges!"
        assert len(orig)==len(data), "length changed — impossible in same-length patch"
        with open(path,'wb') as f: f.write(data)
        print(f"patched {len(sel)} occurrence(s); file size unchanged: {len(data)}")
        print(f"sha256: {before} -> {sha256(bytes(data))}")
        for s,e in ranges: print(f"  patched range: {s:#x}-{e:#x}")
        return 0
    elif cmd == 'verify-region':
        if len(a) < 3: print(__doc__); return 2
        x, y = load(a[1]), load(a[2])
        if len(x) != len(y): print(f"SIZE MISMATCH {len(x)} vs {len(y)}"); return 1
        diffs=[i for i in range(len(x)) if x[i]!=y[i]]
        if not diffs: print("identical"); return 0
        ranges=[]
        for i in diffs:
            if ranges and i == ranges[-1][1]+1: ranges[-1][1]=i
            else: ranges.append([i,i])
        for s,e in ranges: print(f"diff: {s:#x}-{e:#x} ({e-s+1} bytes)")
        return 0
    print(__doc__); return 2

def utf16(s): return s.encode('utf-16-le')

if __name__ == '__main__':
    sys.exit(main())
