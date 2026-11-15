#!/usr/bin/env python3
"""
run_tests.py — fixture-based test suite for bcd-hive-tools.

Builds test fixtures from a PRISTINE (known-bootable) BCD copy — never touches
your live file — and asserts behavior of regf_validate + regf_patch.

Usage:
  python3 tests/run_tests.py --pristine /path/to/known-good/BCD [--keep]
Exit: 0 all pass, 1 any failure.
"""
import sys, os, shutil, struct, subprocess, tempfile, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', 'tools')
sys.path.insert(0, TOOLS)

def run(*args, expect=0):
    p = subprocess.run(args, capture_output=True, text=True)
    ok = (p.returncode == 0) if expect == 0 else (p.returncode != 0)
    return ok, p

def check(name, ok, detail=''):
    status = 'PASS' if ok else 'FAIL'
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not ok else ''))
    return ok

def vpatch(*a): return sys.executable, os.path.join(TOOLS,'regf_patch.py'), *a
def vval(*a): return sys.executable, os.path.join(TOOLS,'regf_validate.py'), *a

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pristine', required=True, help='known-good BCD copy')
    ap.add_argument('--keep', action='store_true')
    args = ap.parse_args()
    pristine = os.path.abspath(args.pristine)
    results = []
    tmp = tempfile.mkdtemp(prefix='bcd-tools-test-')
    print(f"fixtures dir: {tmp}\n")

    def fx(name):
        dst = os.path.join(tmp, name + '.hive')
        shutil.copy(pristine, dst); os.chmod(dst, 0o644)
        return dst

    OLD = '{82e3e790-e05d-11f1-8851-bc0358d5b569}'
    NEW = '{82e3e792-e05d-11f1-8851-bc0358d5b569}'

    # T1 identical copy validates
    t1 = fx('T1')
    ok,_ = run(*vval(t1, '--bcd'))
    results.append(check("T1 pristine copy validates", ok))

    # T2 raw patch → validates + diff confined
    t2 = fx('T2')
    ok,_ = run(*vpatch('patch-guid-in-multisz', t2, OLD, NEW))
    t2a = check("T2a patch tool succeeds", ok)
    results.append(t2a)
    orig = open(pristine,'rb').read(); new = open(t2,'rb').read()
    same_len = len(orig)==len(new)
    diffs=[i for i in range(min(len(orig),len(new))) if orig[i]!=new[i]]
    confined = same_len and diffs and max(diffs) < 0x10000  # displayorder region (fixture-dependent)
    results.append(check("T2b patch is same-length & confined", same_len and bool(diffs) and confined,
                         f"len {len(orig)}->{len(new)}, diffs {len(diffs)}"))
    ok,_ = run(*vval(t2, '--bcd'))
    results.append(check("T2c patched copy validates", ok))

    # T3 dangling ref (regression: the boot-menu-killer)
    t3 = fx('T3')
    import hivex
    h = hivex.Hivex(t3, write=True, unsafe=True)
    root=h.root()
    for c in h.node_children(root):
        if h.node_name(c).lower()=='objects': objs=c
    for c in h.node_children(objs):
        if 'f1f1a000' in h.node_name(c).lower():
            h.node_delete_child(c)
    h.commit(None)
    ok,_ = run(*vval(t3, '--bcd'), expect=1)
    results.append(check("T3 dangling displayorder ref REJECTED (menu-killer regression)", ok))

    # T4 bad magic
    t4 = fx('T4')
    d=bytearray(open(t4,'rb').read()); d[0:4]=b'Xegf'
    open(t4,'wb').write(bytes(d))
    ok,_ = run(*vval(t4), expect=1)
    results.append(check("T4 corrupt magic rejected", ok))

    # T5 dirty seq with coherent checksum → warn but pass
    t5 = fx('T5')
    d=bytearray(open(t5,'rb').read())
    s=struct.unpack_from('<I',d,4)[0]+1
    struct.pack_into('<I',d,4,s)  # bump primary seq only => seq1!=seq2, dirty-looking
    x=0
    for off in range(0,0x1FC,4): x^=struct.unpack_from('<I',d,off)[0]
    struct.pack_into('<I',d,0x1FC,x)  # checksum coherent with new bytes
    open(t5,'wb').write(bytes(d))
    ok,p = run(*vval(t5))
    results.append(check("T5 dirty-but-coherent hive passes with warning", ok and 'WARN' in p.stdout))

    # T6 truncated
    t6 = fx('T6')
    d=open(t6,'rb').read()
    open(t6,'wb').write(d[:0x1000+2048])  # cuts mid-hbin
    ok,_ = run(*vval(t6), expect=1)
    results.append(check("T6 truncated file rejected", ok))

    # T7 patch refusals
    t7 = fx('T7')
    ok,_ = run(*vpatch('patch-guid-in-multisz', t7, '{not-a-guid}', NEW), expect=1)
    results.append(check("T7a invalid GUID refused", ok))
    ok,_ = run(*vpatch('patch-guid-in-multisz', t7, OLD, '{00000000-0000-0000-0000-00000000000}'), expect=1)
    results.append(check("T7b length-mismatch GUID refused", ok))
    ok,_ = run(*vpatch('patch-guid-in-multisz', t7, '{ffffffff-ffff-ffff-ffff-ffffffffffff}', NEW), expect=1)
    results.append(check("T7c absent GUID refused", ok))

    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"\nfixtures kept at {tmp}")

    n_ok = sum(1 for r in results if r)
    print(f"\n{n_ok}/{len(results)} tests passed")
    return 0 if all(results) else 1

if __name__=='__main__':
    sys.exit(main())
