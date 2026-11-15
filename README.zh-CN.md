# bcd-hive-tools

对 Windows 注册表 hive（包括引导配置数据 BCD）进行外科手术式、与 Windows 兼容的
Linux 离线编辑。

**状态：在真实硬件上历经实战检验。** 本项目的每一项技术都源于一次真实教训——
朴素的编辑方法曾两次毁掉一台真实机器的启动菜单。详见
[docs/incident-postmortem.zh-CN.md](docs/incident-postmortem.zh-CN.md)。

> English documentation: [README.md](README.md)

## 为什么需要这个项目

Windows 的 hive 不是"一个装着键值的文件"。它是事务型数据库，包含：

* 带序列号与 XOR 校验和的基块（base block），
* 以相对偏移链接的 `hbin` 页，
* 必须保持一致的单元格分配器（空闲/占用记账），
* 以及——对带日志的 hive——成对的 `.LOG1/.LOG2` 文件：加载时其页回放
  **会覆盖**基块。

整树重建的写入器（典型如 `hivex` 的 `commit()`）产出的文件虽然可以被解析，
但 Windows 依然可能拒绝：文件多出一页、单元格布局被完全重排，任何微妙的记账
偏差都会让 `bootmgr` 静默拒绝整个存储。症状：启动菜单消失、引导卡在
"Please wait"、或系统回退到默认项。

本项目反其道而行之：

> **你只改你打算改的那几个字节。**

`regf_patch.py` 执行同长度就地字节补丁（例如在 `REG_MULTI_SZ` 中把一个 GUID
字符串换成另一个）。输出 hive 在补丁范围之外与输入**逐字节相同**——这是被验证
的，不是被假设的。不重排、不改头部、不破坏校验和、不产生 LOG 失配。

## 工具

| 工具 | 用途 | 风险等级 |
|---|---|---|
| `tools/regf_patch.py` | multi_sz 数据内的同长度 GUID 补丁 | **最低**——字节范围受限 |
| `tools/regf_validate.py` | V1–V4 结构/语义验证（基块、hbin 链、单元格遍历、BCD 交叉引用） | 必经闸门 |
| `tools/bcd_inspect.py` | 只读枚举 BCD（含 bootmgr displayorder） | 零风险 |
| `scripts/install.sh` | 原子安装：原始备份 → LOG 隔离 → mv → 重解析 | 操作类 |

## 黄金法则（用真实代价换来的）

1. **绝不重排一个你无法立即开机验证的 hive。** 只有当 Windows 自己接下来会
   重写该 hive 时，重排型写入器才是安全的。
2. **始终在活文件旁保留原始备份。** 恢复必须只隔一条 `cp` 命令。
3. **安装任何 Linux 写入的 hive 后，必须隔离 `.LOG1/.LOG2`。** Windows 加载时
   会用日志回放覆盖基块；陈旧日志获胜，你的编辑就丢了——甚至更糟。
4. **BCD 的 GUID 比较必须不区分大小写。** 对象键是 `{大写}`，
   `displayorder` 列表是 `{小写}`。很多工具都栽在这里。
5. **displayorder 就是菜单。** 不在 `{bootmgr}` 的 `Elements\24000001` 里的
   条目不会出现在启动菜单里，无论对象是否存在。删除对象却把 GUID 留在
   displayorder 里 = 引导报废。
6. **Linux 侧验证只证明格式健全，不证明 Windows 接受。** 下一次开机才是验收
   测试。失败的编辑绝不要原地重试第二次——先恢复，再用 Windows 侧的
   `bcdedit`。

## 快速上手

```bash
# 只读检查活 BCD
tools/bcd_inspect.py /mnt/esp/EFI/Microsoft/Boot/BCD

# 在 displayorder 中补丁一个 GUID（先 dry run！）
tools/regf_patch.py patch-guid-in-multisz BCD.copy \
    '{11111111-...}' '{22222222-...}' --dry-run
tools/regf_patch.py patch-guid-in-multisz BCD.copy \
    '{11111111-...}' '{22222222-...}'

# 写盘之前先验证
tools/regf_validate.py BCD.copy --bcd

# 原子安装（备份 + LOG 隔离 + mv + 重解析）
sudo scripts/install.sh BCD.copy /mnt/esp/EFI/Microsoft/Boot/BCD
```

## 测试

`tests/run_tests.py` 从一份原始（已知可引导）副本构建测试件——绝不触碰你的
活文件——并断言：

* **T1** 完全相同的副本 → 验证通过
* **T2** raw-patch 后的 displayorder → 验证通过，差异限于补丁范围
* **T3** 被删除但仍被 displayorder 引用的对象 → 验证**失败**
  *（针对真实抹掉过一台机器启动菜单的那个 bug 的回归测试）*
* **T4** 破坏的 magic → 失败
* **T5** 脏序列号但校验和自洽 → 带警告通过
* **T6** 截断的文件 → 失败
* **T7** 补丁工具的 confinement：目标范围之外零字节变化

```bash
python3 tests/run_tests.py --pristine /path/to/known-good/BCD
```

## 环境要求

* Python 3.8+
* `python3-hivex`（读写解析）—— `apt install python3-hivex`
* `chntpw`（可选，用于叶键删除编辑）

## 范围与保证

* **已证明安全：** `REG_MULTI_SZ` 值数据内的同长度 GUID 替换（补丁字节范围
  相对原件验证；必须通过 hivex 重解析）。
* **支持但需开机测试：** 经验证的 hivex 值写入，用于非引导 hive
  （SOFTWARE/SAM/NTUSER）。
* **不支持：** 重排型写入（hivex `commit()` 的结构性变更）、单元格分配、
  在引导关键 hive 上新建键。这些曾毁掉真实机器；本项目不会加入这些能力。

## 教训与复盘

* [docs/incident-postmortem.zh-CN.md](docs/incident-postmortem.zh-CN.md) —
  hive 重排两次毁掉启动菜单，完整二进制取证
* [docs/lessons-powershell-binding.zh-CN.md](docs/lessons-powershell-binding.zh-CN.md) —
  PowerShell 位置参数绑定陷阱（真实交付事故）

## 许可证

MIT — 见 [LICENSE](LICENSE)。
