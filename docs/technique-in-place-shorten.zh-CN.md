# 技术：无需重排的就地 REG_MULTI_SZ 缩短

**风险等级：已证明极低**（语义差异仅个位数字节，结构零改动）。
状态：离线验证完成（V1–V4 + hivex 重解析）；按设计，开机验收待做。

> English: [technique-in-place-shorten.md](technique-in-place-shorten.md)

## 原理

regf hive 中的 `REG_MULTI_SZ` 值由一个 `vk` 记录描述：

```
vk  sig(2) | namesize u16 | dsize u32 | data-offset u32 | type u32 | flags...
```

数据单元格持有 `dsize` 字节载荷。解析器只读取数据偏移处的 `dsize` 字节——
**同一单元格内超出 `dsize` 的字节是不可见的松弛空间**。

因此缩短一个值只需三次受限写入，零结构变化：

1. 在同一数据偏移处写入新的（更短的）载荷；
2. 把旧 `dsize` 范围内的松弛空间填 NUL；
3. 补丁 vk 记录中的 4 字节 `dsize` 字段。

不释放、不移动任何单元格；hbin 链、基块、校验和、序列号全部未动。
如果原 hive 能引导，缩短后的 hive 就能引导——只有值载荷字节和一个长度字段不同。

## vk 记录字段偏移（修正版）

```
vk@payload+0x00  sig 'vk'
+0x02  namesize (u16)
+0x04  dsize    (u32)   <-- 你要补丁的字段
+0x08  doff     (u32)   数据偏移：高位=驻留（相对 vk），否则绝对= hbase + doff + 4
+0x0C  vtype    (u32)   7 = REG_MULTI_SZ
+0x14  名字字节 (namesize)，随后为驻留数据（若有标志）
```

> **偏移 bug 警告：** 不少朴素的遍历器把 `dsize` 读在 `+8`——那是 `doff`，
> 会静默污染所有下游扫描。我们自己就踩过，症状是 multi_sz 扫描结果为空。

## 应用实例（本仓库的起源案例）

BCD displayorder：6 个 GUID 条目（2 个重复、2 个孤儿）→ 4 个条目。
`dsize 470 → 312`；全文件差异 = 104 字节，限于值数据区域加 4 字节长度字段。
V1–V4 验证通过；hivex 重解析列出精确的 4 条目菜单。

## 边界

* 只能缩短。超出原单元格的增长需要再分配 → 重排类 → 引导关键 hive 上禁止。
* 安装后的第一次开机仍是验收测试。
