# Incident Postmortem: Boot menu destroyed by hive repacking (x2)

**Machine:** Firebat GM6BG5Q-F laptop, Windows 11 26100, UEFI + VBS
**Impact:** 2 failed boots requiring Linux-side recovery; no data loss
**Author:** reconstructed from session logs, 2026-11-15

## Timeline

### Attempt 1 — hivex structural edit
* Goal: delete two stale BCD entries, rewrite bootmgr `displayorder`.
* Tool: python-hivex `node_delete_child` + `node_set_value` + `commit()`.
* Content verification passed (hivex re-parse showed intended state).
* **Result: bootmgr refused the hive. No menu, "Please wait" → crash.**
* Recovery: pristine backup copied back; machine boots again.

### Attempt 2 — chntpw deletes + hivex value write
* Goal: same change, believing attempt 1's failure was LOG mismatch.
* chntpw `rdel` for objects (format-faithful), hivex `commit()` again for the
  displayorder value; LOGs quarantined this time.
* Content verification passed again.
* **Result: identical failure.**

## Root cause analysis

Binary forensics comparing the known-good hive with the rejected one:

| Region | Verdict |
|---|---|
| Base block | only legit diffs (seq++, binsize +1 page, checksum coherent) |
| hbin chain | 30 pages, all `hbin`, rel-offsets correct |
| nk/vk/index records | all parse, counts consistent with 2 deleted subtrees |
| Header checksum | recomputed correctly by hivex |

Every check we can run offline passes. **The hive is structurally valid by every
available measure and bootmgr still refuses it.** The remaining divergence is
inside hivex's repacking (cell layout, allocation granularity, or some regf
minor-version subtlety hivex does not reproduce). We cannot fully characterize it,
which is precisely the point: **when you cannot characterize what bootmgr accepts,
do not regenerate the container — patch the minimum bytes.**

## Fix: byte-confined patching

The same semantic change, done as in-place same-length byte replacement inside the
`displayorder` value data:

* 2 bytes total changed (GUID digits `'90'→'92'`, `'91'→'92'`)
* file length, header, hbins, checksums, sequence numbers: untouched
* diff verifiably confined to the two patch ranges

This eliminates the entire failure class **by construction**: if the original
booted, the patched copy boots (only value payload bytes differ, and payload
semantics were chosen to reference existing entries).

## Lessons encoded in this repo

1. Content-level verification (even hivex re-parse) does NOT imply Windows
   acceptance for repacked hives.
2. LOG quarantine is necessary but not sufficient.
3. `chntpw`'s silent write failures (RO fallback prints one line) must be
   checked by re-reading the file, not by trusting its "OK".
4. GUID casing differs between object keys and displayorder lists — case-sensitive
   membership checks produce false "MISSING" diagnostics (cost: one wrong
   forensic conclusion).
5. The boot menu is displayorder. Semantic changes there are the safe subset;
   structural object deletion is the dangerous subset. Prefer pointer swaps.
