# 旧风格索引入口

本文件不再提供“场景/行业 → 风格”的快捷映射。那种映射缺少任务、内容、受众、信任姿态、素材、交互和设备信息，会把目录名称误当成项目方向。

50 份 style 的完整正文仍位于 `styles/`，20 份大师资料仍位于 `masters/`。运行时使用与选择输入一致的语义目录：

```sh
node tools/catalog.mjs --check
node tools/select.mjs --profile profile.json --kind style --limit 3
```

选择结果来自 `profiles.json` 与生成的 `catalog.json`，最多返回三个候选及匹配、代价和拒绝原因。只有行业输入时返回 `needs_profile`；没有核心语义命中时返回 `no_match`。大师资料属于 `method`，只在明确需要方法时读取，不参与 style 排名。

人类浏览目录见 [INDEX.md](INDEX.md)。不要从本文件、文件名或规范名称直接选择。
