# 教训：PowerShell 位置参数绑定在与显式 Position 混用时失效

**背景：** 交付热加载控制台脚本时，所有启动器（launcher）全部失败，报
`PositionalParameterNotFound`。

> English version: [lessons-powershell-binding.md](lessons-powershell-binding.md)

## 陷阱

```powershell
param(
    [Parameter(Position=0)]
    [string]$Action = 'status',
    [int]$Core = 1        # 没有 [Parameter] 属性
)
```

以 `powershell -File script.ps1 unpark 1` 调用 →
**"A positional parameter cannot be found that accepts argument '1'."**
（找不到可接受实参 '1' 的位置参数）

PowerShell 的规则：**只要任意一个参数声明了显式 `[Parameter(Position=N)]`，
其余没有声明显式 `[Parameter]` 属性的参数就失去隐式位置绑定**。于是 `$Core`
变成了仅具名参数，实参 `1` 无处可绑。

## 修复

```powershell
param(
    [Parameter(Position=0)]
    [ValidateSet('status','park','unpark','all','one')]
    [string]$Action = 'status',
    [Parameter(Position=1)]
    [ValidateRange(1,3)]
    [int]$Core = 1
)
```

## 规则（已作为 TOP2 写入创作记忆，强制执行）

任何交付给用户的脚本都必须通过强制的静态防御性检查：
每个位置参数显式声明 `Position`、数值输入做范围验证（ValidateRange）、
文件级花括号/圆括号平衡、Windows 脚本统一 UTF-8 BOM + CRLF 编码、
写盘后从磁盘重读文件确认持久化。
