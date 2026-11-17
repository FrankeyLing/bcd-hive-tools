# 4 核 bring-up 假设日志（实时实验笔记）

> English: [hypothesis-log-4core.md](hypothesis-log-4core.md)

## 已排除（2026-11-15 晚间实验）

| 假设 | 证据 | 状态 |
|---|---|---|
| VBS/Hyper-V 拦截 AP 启动 → 关闭后挂死 | 注册表确认 `EnableVirtualizationBasedSecurity=0`、`HVCI=0`、`hypervisorlaunchtype off`；两次独立 4 核引导仍硬死锁 | **已排除** |
| 内核数组按 1 核分配（运行期 numproc 问题） | 本次是固件期 `numproc=4` 的全新引导（BCD 元素 0x25000061=4），无任何运行期重配 | **已排除** |
| IDLEDISABLE 未生效 | `powercfg` AC/DC=1，转发回调已注册（值 1） | 生效中，但见下 |
| LOG/基块失配 | 本次引导只经 bcdedit 改动，不适用 | 不适用 |

## 剩余假设（按优先级）

1. **AP 早期 MWAIT 在此固件上挂死**（火影 GM6BG5Q-F，AMD Zen3+）：次级核心在 OS
   空闲策略生效前，于早期 bring-up 阶段就在 MONITOR/MWAIT 上自旋。Ubuntu 能活是因为
   `idle=poll` 在 AP 引导之前就全局生效；Windows 的 `IDLEDISABLE` 只覆盖调度器交接
   后的 `PoIdle`——而且关键点：IDLEDISABLE→hypervisor 转发可能一直是唯一的 MWAIT
   拦截路径，而我们用 `hypervisorlaunchtype off` 把它关掉了。
2. **x2APIC 与 xAPIC** 的 AP bring-up 模式与主板固件不兼容。

## 已排队的对照实验（仅 Windows 侧 bcdedit）

* **TEST-X**：`hypervisorlaunchtype auto` + `numproc=4` → 只回退"关 hypervisor"这一项。
  存活 = hypervisor 一直在帮忙；挂死 = 假设 1 削弱。
* **TEST-Y**：`hypervisorlaunchtype off` + `x2apicdisable 1` + `numproc=4` →
  传统 xAPIC bring-up。存活 = x2APIC 问题。

## 取证缺口（证据薄弱的原因）

引导挂死后强制断电会丢掉一切：evtx 从未刷盘、新条目没开 bootlog、无法产生 dump。
**下一批测试条目必须加 `bootlog yes`**——至少能记录到驱动加载进度。

## 更新 2026-11-17：对照实验结果——两个假设全部排除

TEST-X（hypervisor 开）与 TEST-Y（xAPIC 传统模式）都在同一位置硬死锁：
驱动加载结束处（~276 条 BOOTLOG_LOADED，与之前所有 4 核尝试一致）。

| 假设 | 状态 |
|---|---|
| Hyper-V 的 MWAIT 拦截是必需的 | **已排除**（X 在 HV 开启下仍死） |
| x2APIC 兼容性问题 | **已排除**（Y 在 xAPIC 下仍死） |
| VBS 干扰 | 已排除（更早） |

## 剩下的架构级嫌疑

菜单里的 FIREBAT 链式条目自述：`[boot via chain Boot0000 only]`——老项目的设计
要求先经 UEFI `Boot0000` 链（FULL12.EFI）在 winload 运行前装好固件门控表
（FirebatAcpiInstall + DYN12.EFI）。缺少这次引导前固件准备时，直接从 BCD 选
多核条目会在 AP bring-up 阶段挂死——与迄今全部观测一致。

**下一步实验（用户操作，不涉及 Linux）：** 重启进主板 UEFI 启动菜单（不是
Windows Boot Manager），选择经过 Boot0000 链的 FIREBAT 条目，让 FULL12.EFI 先跑。
如果 12 核 Windows 能进，整个方案就是固件预备依赖型的，热加载项目必须瞄准固件
门控——而不是 OS 侧的 numproc。
