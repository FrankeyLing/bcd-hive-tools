# Technique: in-place REG_MULTI_SZ shortening without repacking

**Risk class: proven minimal** (single-digit byte semantic diff, structure untouched).
Status: validated offline (V1–V4 + hivex re-parse); boot acceptance pending by design.

> 中文版：[technique-in-place-shorten.zh-CN.md](technique-in-place-shorten.zh-CN.md)

## Why it works

A `REG_MULTI_SZ` value in a regf hive is described by a `vk` record:

```
vk  sig(2) | namesize u16 | dsize u32 | data-offset u32 | type u32 | flags...
```

The data cell holds `dsize` bytes of payload. Parsers read exactly `dsize` bytes at
the data offset — **bytes beyond `dsize` inside the same cell are invisible slack**.

Therefore shortening a value is three confined writes, zero structural change:

1. write the new (shorter) payload at the same data offset;
2. NUL-fill the slack up to the old `dsize`;
3. patch the 4-byte `dsize` field in the vk record.

No cell is freed or moved; the hbin chain, base block, checksums, and sequence
numbers are untouched. If the original hive booted, the shortened hive boots —
only value-payload bytes and one length field differ.

## vk record field offsets (corrected)

```
vk@payload+0x00  sig 'vk'
+0x02  namesize (u16)
+0x04  dsize    (u32)   <-- the field you patch
+0x08  doff     (u32)   data offset: high bit = resident (relative to vk), else
                        absolute = hbase + doff + 4
+0x0C  vtype    (u32)   7 = REG_MULTI_SZ
+0x14  name bytes (namesize), then resident data (if flagged)
```

> **Offset bug warning:** several naive walkers read `dsize@+8` — that is `doff`,
> which silently corrupts every downstream scan. We hit this ourselves; the
> symptom is an empty multi_sz scan result.

## Applied example (this repo's origin case)

BCD displayorder: 6 GUID entries (2 duplicates, 2 orphans) → 4 entries.
`dsize 470 → 312`; total file diff = 104 bytes confined to the value-data region
plus the 4-byte size field. Validation V1–V4 passed; hivex re-parse lists exactly
the intended 4-entry menu.

## Limits

* Only shortening. Growth beyond the original cell requires reallocation →
  repack class → banned on boot-critical hives.
* First boot after install is still the acceptance test.
