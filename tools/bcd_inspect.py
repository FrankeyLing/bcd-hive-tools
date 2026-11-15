#!/usr/bin/env python3
"""bcd_inspect — read-only enumeration of a BCD hive.

Prints all objects with type + description, then bootmgr displayorder/default
resolved to descriptions. Zero write risk.

Usage: bcd_inspect.py <BCD.hive> [--cjk]
"""
import sys, re
try:
    import hivex
except ImportError:
    sys.exit("requires python3-hivex")
CJK = re.compile(r'[\u3000-\u9fff]')

def main():
    if len(sys.argv) < 2: print(__doc__); return 2
    h = hivex.Hivex(sys.argv[1])
    root = h.root()
    objs = None
    for c in h.node_children(root):
        if h.node_name(c).lower() == 'objects': objs = c
    if objs is None: sys.exit("not a BCD hive (no Objects root key)")
    def child(n, name):
        for c in h.node_children(n):
            if h.node_name(c).lower() == name.lower(): return c
    def desc(o):
        els = child(o, 'Elements')
        e = child(els, '12000004') if els else None
        for v in h.node_values(e or o):
            try: return h.value_string(v)
            except Exception: pass
        return None
    def objtype(o):
        for v in h.node_values(o):
            if h.value_key(v) == 'Type':
                raw = h.value_value(v)[1]
                return struct.unpack('<I', raw[:4])[0] if len(raw) >= 4 else None
        return None
    import struct
    entries = []
    for o in h.node_children(objs):
        g, d, t = h.node_name(o), desc(o), objtype(o)
        if '--cjk' in sys.argv and not (d and CJK.search(d)): continue
        entries.append((g, d, t))
    for g, d, t in entries:
        print(f"{g}  type={t:#x}  | {d}" if t is not None else f"{g}  | {d}")
    bm = child(objs, '{9dea862c-5cdd-4e70-acc1-f32b344d4795}')
    els = child(bm, 'Elements')
    print("\nboot menu (displayorder):")
    disp = child(els, '24000001')
    seen = []
    if disp:
        for v in h.node_values(disp):
            txt = h.value_value(v)[1].decode('utf-16-le', errors='replace')
            for g in re.findall(r'\{[0-9a-fA-F-]{36}\}', txt):
                o = child(objs, g)
                d = desc(o) if o else '**MISSING OBJECT — broken menu**'
                print(f"  {g}  {d}")
                seen.append(g)
    default = child(els, '23000003')
    if default:
        for v in h.node_values(default):
            g = h.value_value(v)[1].decode('utf-16-le', errors='replace').strip('\x00')
            print(f"default: {g}")
    missing = [g for g in seen if child(objs, g) is None]
    if missing:
        print(f"\n!! {len(missing)} displayorder entries reference missing objects")
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
