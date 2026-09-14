# 页面方向合同

首次完整视觉实现前填写，保存为 `.site/design/surface-brief.md`。它不是页面文案或固定布局；它把事实、任务、三个设计层和验证连接起来。随后从同一内容生成紧凑 DesignPacket。

## 本轮问题与事实

- **要验证的问题：**
- **工作类型：** `new-surface | redesign | existing-system | local-change | flow-state`
- **最终用户/场景：**
- **核心任务/业务对象：**
- **真实内容形态与数量：**
- **设备/输入环境：**
- **后果、可逆性与高风险边界：**

| 来源 | 精确观察 | 作用 | 证据 |
| --- | --- | --- | --- |
|  |  | `inherit | adapt | avoid | unknown` | `measured | derived | inferred` |

## 任务交互合同

| ID | 约束 | 等级 | 依据 | 对结构/状态的影响 |
| --- | --- | --- | --- | --- |
| IC-01 |  | `required | recommended | confirm | excluded` |  |  |

| Flow | 起点 | 操作与响应 | 保留/改变什么 | 结果 |
| --- | --- | --- | --- | --- |
| 主路径 |  |  |  |  |
| 成功 |  |  |  |  |
| 失败恢复 |  |  |  |  |
| 中途退出 |  |  |  |  |
| 再次打开 |  |  |  |  |

- **本地化条件：** 中文输入、日期时间、数字金额、地址电话、触屏、弱网中的适用项；严禁境外不可达 CDN（防白屏）；适配 100dvh 弹性视口与微信防手势冲突；页面包含社交分享卡片元标签
- **明确排除：**

## Direction

```yaml
direction:
  source: existing | reference | project-derived
  evidence:
    - source:
      observation:
      confidence: measured | derived | inferred
  visual_world:
  motif:
  composition:
  project_signature:
```

- **替换检查：** 换一个项目名或行业后，母题/构图/签名是否仍无损成立？若是，继续推导。
- **参考边界：** reference 来源时分别写可借鉴与不可借鉴。
- **真实素材主角与缺口：** 记录来源、用途、裁剪和缺少什么；不把示意内容说成真实。

## Grammar

```yaml
grammar:
  source: existing-system | packaged-spec | project-tokens
  spec_id:
  mode:
  cjk_fallback:
  deviations:
    - rule:
      reason:
      evidence:
```

grammar 只约束视觉语言，不改变 direction 或任务合同。使用 packaged-spec 时从语义选择结果中选一份，只读取该完整规范；大师 `method` 不填在这里。

## Patterns

```yaml
patterns:
  selected:
    - id:
      fit:
  adaptations:
    - pattern:
      change:
      reason:
  rejected:
    - id:
      reason:
```

模板只能在任务合同和 direction 之后进入。复制现成代码不等于适配完成；真实字段、状态、内容、grammar、移动重排和验证命令都要落到项目。

## 选择画像

写入给 `select.mjs` 的 JSON：

```yaml
task:
content_shape:
content_subject:
audience:
trust_posture:
asset_conditions:
interaction_intensity:
primary_device:
constraints:
  color_scheme:
  images_available:
  reduced_motion:
  max_visual_risk:
```

只有行业名称不能运行选型。候选最多三个，记录每个理由、强项、代价和拒绝条件；没有命中时允许 no_match。

## 候选与确认

存在结构不确定性时先用相同内容做低成本结构候选；结构固定后才比较视觉。完整风格候选保持任务与信息架构不变，在母题、构图和项目签名上有实质差异。

| 候选 | Direction 依据 | Grammar | Patterns | 突出 / 牺牲 | 结果 |
| --- | --- | --- | --- | --- | --- |
| A |  |  |  |  | `pending` |

- **推荐与理由：** 推荐不是确认。
- **结构确认原话：** 只有实际比较多个结构时填写。
- **视觉确认原话：**
- **模拟范围：**

## 验收条件

- **页面与状态：**
- **桌面/手机视口：**
- **核心任务：**
- **失败恢复：**
- **再次打开：**
- **自动渲染证据：** `check-render.mjs` JSON 与截图
- **独立视觉判断：** direction 可追溯、项目特异性、构图和工艺

## DesignPacket 输入

将上述内容压缩为 `prepare-design.mjs` 接受的 JSON；只保留 `project / facts / task_contract / direction / grammar / patterns / acceptance / selection_profile`。生成的 packet 最大 12,000 bytes，`gaps` 必须为空再交 builder/checker。旧 `visual_source` 仅由工具兼容读取，不写进本合同。
