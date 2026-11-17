# 4-core bring-up hypothesis log (live experiment notes)

> 中文版：[hypothesis-log-4core.zh-CN.md](hypothesis-log-4core.zh-CN.md)

## Confirmed eliminated (2026-11-15 evening experiments)

| Hypothesis | Evidence | Status |
|---|---|---|
| VBS/Hyper-V intercepts AP startup → hang when off | Registry: `EnableVirtualizationBasedSecurity=0`, `HVCI Enabled=0`, `hypervisorlaunchtype off`; two independent 4-core boots still hard-froze | **ELIMINATED** |
| Windows arrays mis-sized (numproc runtime change) | Fresh boots with `numproc=4` from firmware (element 0x25000061=4); no repack involved | **ELIMINATED** |
| IDLEDISABLE not active | `powercfg` AC/DC = 1, forwarded path registered (value 1) | active, but see below |
| LOG/base mismatch | n/a for these boots (bcdedit-only changes) | n/a |

## Remaining hypotheses (ranked)

1. **AP early MWAIT hangs on this firmware** (Firebat GM6BG5Q-F, AMD Zen3+): secondary
   cores spin on MONITOR/MWAIT in early bring-up before OS idle policy applies.
   Ubuntu survives because `idle=poll` is global from before AP boot; Windows
   `IDLEDISABLE` only covers `PoIdle` after scheduler handoff — and, critically,
   the IDLEDISABLE→hypervisor forwarding may have been the only MWAIT-interception
   path, which we disabled with `hypervisorlaunchtype off`.
2. **x2APIC vs xAPIC** AP bring-up mode incompatibility with board firmware.

## Bracket experiments queued (Windows-side bcdedit only)

* **TEST-X**: `hypervisorlaunchtype auto` + `numproc=4` → reverts the hypervisor-off
  change while keeping everything else. Survive = hypervisor was helping; hang =
  hypothesis 1 weakened.
* **TEST-Y**: `hypervisorlaunchtype off` + `x2apicdisable 1` + `numproc=4` →
  legacy APIC bring-up. Survive = x2APIC issue.

## Forensic gaps (why evidence is thin)

Forced power-offs at boot-hang lose everything: evtx never flushed, bootlog absent
on new entries (must add `bootlog Yes` to test entries), no dump possible.
**Next test entries must include `bootlog yes`** to at least capture driver-load
progress.

## Update 2026-11-17: bracket results — BOTH eliminated

TEST-X (hypervisor ON) and TEST-Y (xAPIC legacy) both hard-froze at the same point:
end of driver load (~276 BOOTLOG_LOADED entries, same as all prior 4-core attempts).

| Hypothesis | Status |
|---|---|
| Hyper-V MWAIT interception needed | **ELIMINATED** (X died with HV on) |
| x2APIC incompatibility | **ELIMINATED** (Y died with xAPIC) |
| VBS interference | ELIMINATED (earlier) |

## Remaining architecture-level suspect

The FIREBAT chain entries in the menu are self-documenting:
`FIREBAT 12 CPUs idle-poll [boot via chain Boot0000 only]` — the old project's
design requires booting through UEFI `Boot0000` chain (FULL12.EFI) which installs
firmware gating tables (FirebatAcpiInstall + DYN12.EFI) BEFORE winload runs.
Without that pre-boot firmware preparation, direct BCD multi-core boots hang at
AP bring-up — consistent with every observation to date.

**Next test (user, no Linux involved):** reboot into the motherboard UEFI boot
menu (not Windows Boot Manager) and select the FIREBAT chain entry that goes
through Boot0000, letting FULL12.EFI run first. If 12-core Windows boots, the
entire solution is firmware-prep-dependent, and the hot-add project must target
the firmware gate — not OS-side numproc.
