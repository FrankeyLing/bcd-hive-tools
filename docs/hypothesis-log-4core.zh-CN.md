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

## 更新 2026-11-17（后续）：固件预备链同样死亡

用户从主板固件菜单 → `Boot0000`（FULL12.EFI 链先运行）引导 → 12 核 Windows
仍在同一特征点硬死。

| 假设 | 状态 |
|---|---|
| 缺失固件门控表（FirebatAcpiInstall/DYN12.EFI 预备） | **已排除**（带预备的链式引导照样死） |

**所有引导前假设全部排除**（VBS、hypervisor、x2APIC、固件预备）。死点在
Windows 内核 AP 启动/调度器内部，无论引导路径如何都停在 ~276 条
BOOTLOG_LOADED 处。与全部 Windows 尝试唯一的差异是 Ubuntu 的全局
`idle=poll`（在任何 AP 启动之前就生效）。

下一步方向：内核级等效全局 poll-idle / 禁 C-state（powercfg 路线），
或 testsigning 内核级驱动（Route B）；并做核数二分（带 IDLEDISABLE 的
2→3→4 核）定位阈值。
