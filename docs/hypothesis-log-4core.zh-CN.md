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
