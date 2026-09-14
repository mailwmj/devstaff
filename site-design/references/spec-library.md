# 随包样式语法

随包规范只提供 `grammar`：颜色角色、字体角色、边界、组件状态与布局尺度。它不能替项目产生 direction，也不能带入页面、角色、数据或流程。

## 选择

先从任务合同形成画像，再运行：

```sh
node tools/catalog.mjs --check
node tools/select.mjs --profile profile.json --kind style --limit 3
```

目录字段与选择条件完全一致：task、content shape/subject、audience、trust posture、asset conditions、interaction intensity、primary device；明暗、素材可用性、减弱动效和视觉风险作为硬约束。行业字段被忽略。

结果处理：

- `matched`：比较至多三个候选的理由、强项、代价和拒绝条件，选定一份；
- `needs_profile`：补工具返回的缺失维度，不用行业标签猜；
- `no_match`：接受弃权，使用已有系统或项目 token，不强配；
- `method`：大师资料只在明确需要一种评审/构图方法时另行读取，不参与 style 排名。

只打开最终选中的 `styles/<id>-DESIGN.md`。不要读取全量 70 份正文或 `style-index.md`，也不要从名称直接映射。

## 落实

1. 读取规范的颜色、排版、组件与 Do/Don't 部分。
2. 用 `catalog.json` 的 `is_dark/multi_theme` 选择一致主题块，不混用亮暗 token。
3. 需要时导出：

   ```sh
   node tools/export.mjs --format css assets/spec/styles/<id>-DESIGN.md
   ```

4. 已有项目把 token 映射到现有主题，不并列创建第二套全局变量。
5. 与更高优先级项目事实冲突时做最小覆盖，并写 `{ rule, reason, evidence }` deviation。

## 中文字体

多数规范只声明拉丁字体。中文页面必须在同一角色里补中文回退，例如 `PingFang SC / Microsoft YaHei / Noto Sans SC / sans-serif`；中文连续阅读可以按项目选择宋体角色。保持规范的角色层级，但中文标题 `letter-spacing: 0`，正文不低于 16px，连续正文行高至少 1.7。

字体交付方式只需与真实分发条件一致：系统字体无需额外文件；bundled/CDN 字体在实际页面加载失败时必须有回退；离线要求下不能依赖未缓存网络字体。许可审计不属于本流程，默认资产可用。

## 静态预检与真实验证

```sh
node tools/check-output.mjs <output.html> assets/spec/styles/<id>-DESIGN.md
node tools/check-render.mjs --entry <URL或HTML> --contract contract.json --output evidence
```

`check-output.mjs` 扫描 HTML、内联样式和本地链接 CSS，提示未声明颜色、泛化色名、声明字体缺失和 token 覆盖；它不运行浏览器。

`check-render.mjs` 才读取 computed style、实际相邻背景、字体状态、桌面/手机布局和交互合同。两者通过都不等于设计成立；还要独立判断 direction 是否有证据、页面是否有项目签名、构图与真实内容是否匹配。

## 交接

DesignPacket 只需要：

```yaml
grammar:
  source: packaged-spec
  spec_id: <id>
  deviations: []
```

另保留选择器返回的候选/拒绝理由和 `check-output`、`check-render` 证据。来源记录文件可以随包保留，但不进入普通选型与生成上下文。
