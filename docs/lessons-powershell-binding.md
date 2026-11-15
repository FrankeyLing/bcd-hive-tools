# Lesson: PowerShell positional binding breaks when mixed with explicit Position

**Context:** delivery of a hot-add console script; every launcher failed with
`PositionalParameterNotFound`.

> 中文版：[lessons-powershell-binding.zh-CN.md](lessons-powershell-binding.zh-CN.md)

## The trap

```powershell
param(
    [Parameter(Position=0)]
    [string]$Action = 'status',
    [int]$Core = 1        # NO [Parameter] attribute
)
```

Called as `powershell -File script.ps1 unpark 1` →
**"A positional parameter cannot be found that accepts argument '1'."**

PowerShell's rule: if ANY parameter declares an explicit `[Parameter(Position=N)]`,
parameters without an explicit `[Parameter]` attribute lose their implicit
positional binding. `$Core` became named-only, and the `1` had nowhere to bind.

## The fix

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

## The rule (now enforced in authoring memory as TOP2)

Any script delivered to a user gets a mandatory static defensive pass:
explicit `Position` on every positional parameter, range validation on numeric
inputs, file-level brace/paren balance, UTF-8 BOM + CRLF for Windows scripts,
and re-reading the written file from disk to confirm persistence.
