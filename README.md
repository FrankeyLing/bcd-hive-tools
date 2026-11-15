# bcd-hive-tools

Surgical, Windows-compatible editing of Windows registry hives — including the
Boot Configuration Data (BCD) — from Linux.

**Status: battle-tested on real hardware.** Every technique here exists because a
naive approach broke a real machine's boot menu twice. See
[docs/incident-postmortem.md](docs/incident-postmortem.md).

> 中文文档：[README.zh-CN.md](README.zh-CN.md)

## Why this exists

Windows hives are not just "a file with keys and values". They are transactional
databases with:

* a base block containing sequence numbers and a XOR checksum,
* `hbin` pages chained by relative offsets,
* a cell allocator whose free/used accounting must stay coherent,
* and — for hives with logging — sibling `.LOG1/.LOG2` files whose page replay
  **overrides** the base on load.

Writers that rebuild the whole hive (notably `hivex`'s `commit()`) produce
structurally-parseable files that Windows can still reject: the hive grows by one
page, cell layout is fully repacked, and any subtle bookkeeping divergence makes
`bootmgr` refuse the store — silently. Symptoms: boot menu disappears, boot hangs
at "Please wait", or the system falls back to defaults.

This project takes the opposite approach:

> **The only bytes you change are the bytes you mean to change.**

`regf_patch.py` performs same-length, in-place byte patching (e.g. swapping one
GUID string for another inside a `REG_MULTI_SZ`). The output hive is
byte-for-byte identical to the input outside the patched ranges — verified, not
assumed. Nothing is repacked, no header field changes, no checksum invalidation,
no LOG mismatch.

## Tools

| Tool | Purpose | Risk class |
|---|---|---|
| `tools/regf_patch.py` | same-length GUID patching inside multi_sz data | **lowest** — byte-confined |
| `tools/regf_validate.py` | V1–V4 structural/semantic validation (base block, hbin chain, cell walk, BCD cross-refs) | required gate |
| `tools/bcd_inspect.py` | read-only BCD enumeration incl. bootmgr displayorder | zero risk |
| `scripts/install.sh` | atomic install: pristine backup → LOG quarantine → mv → re-parse | operational |

## Golden rules (learned the hard way)

1. **Never repack a hive you cannot immediately boot-test.** Repacking writers are
   only safe when Windows itself will next write the hive.
2. **Always keep a pristine backup next to the live file.** Recovery must be one
   `cp` away.
3. **Quarantine `.LOG1/.LOG2` after installing any Linux-written hive.** Windows
   replays logs over the base on load; stale logs win, your edit loses — or worse.
4. **BCD GUIDs compare case-insensitively.** Object keys are `{UPPERCASE}`,
   `displayorder` lists `{lowercase}`. Many tools have tripped on this.
5. **Displayorder is the menu.** An entry absent from `{bootmgr}`'s
   `Elements\24000001` does not appear in the boot menu, no matter what objects
   exist. Deleting an object while leaving its GUID in displayorder = broken boot.
6. **Linux-side validation proves format sanity, not Windows acceptance.** The
   next boot is the acceptance test. Never retry a failed edit a second time —
   restore, then use Windows-side `bcdedit`.

## Quickstart

```bash
# inspect the live BCD (read-only)
tools/bcd_inspect.py /mnt/esp/EFI/Microsoft/Boot/BCD

# patch a GUID inside displayorder (dry run first!)
tools/regf_patch.py patch-guid-in-multisz BCD.copy \
    '{11111111-...}' '{22222222-...}' --dry-run
tools/regf_patch.py patch-guid-in-multisz BCD.copy \
    '{11111111-...}' '{22222222-...}'

# validate before it goes anywhere near the disk
tools/regf_validate.py BCD.copy --bcd

# atomic install (backup + LOG quarantine + mv + reparse)
sudo scripts/install.sh BCD.copy /mnt/esp/EFI/Microsoft/Boot/BCD
```

## Tests

`tests/run_tests.py` builds fixture hives from a pristine copy (never your live
file) and asserts:

* **T1** identical copy → validation passes
* **T2** raw-patched displayorder → validation passes, diff confined to patch ranges
* **T3** deleted object still referenced by displayorder → validation **fails**
  *(regression test for the exact bug that erased a real boot menu)*
* **T4** corrupted magic → fails
* **T5** dirty sequence numbers with coherent checksum → passes with warning
* **T6** truncated file → fails
* **T7** patch-tool confinement: no byte changes outside the target ranges

```bash
python3 tests/run_tests.py --pristine /path/to/know-good/BCD
```

## Requirements

* Python 3.8+
* `python3-hivex` (read/write parse) — `apt install python3-hivex`
* `chntpw` (optional, for leaf-key deletion edits)

## Scope & guarantees

* **Proven safe:** same-length GUID replacement inside `REG_MULTI_SZ` value data
  (patch byte ranges verified against the original; hivex re-parse required to pass).
* **Supported but test-boot required:** value writes via hivex on non-boot hives
  (SOFTWARE/SAM/NTUSER) with validation.
* **Unsupported:** repacking writes (hivex `commit()` structural changes),
  cell allocation, new-key creation on boot-critical hives. These broke real
  machines; they will not be added.

## Lessons & postmortems

* [docs/incident-postmortem.md](docs/incident-postmortem.md) — boot menu destroyed
  by hive repacking (x2), full binary forensics
* [docs/lessons-powershell-binding.md](docs/lessons-powershell-binding.md) —
  PowerShell positional-binding trap (real delivery incident)

## License

MIT — see [LICENSE](LICENSE).
