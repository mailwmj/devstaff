# AI员工「网站开发专家」全配置项与内容档案

本规范为 **帝王蟹（DevStaff / ClawHive）** 平台 AI 员工包（`website-developer`）的完整配置项与内容档案。  
全文面向企业办公、教育及知识工作者定位，严格剔除技术黑话，且**不包含任何生图或对话提示词**。

---

## 一、 员工基础身份与元数据配置

对应文件：[`release/metadata.json`](release/metadata.json)

| 配置字段 | 属性类型 | 当前配置值 | 业务作用与说明 |
| :--- | :--- | :--- | :--- |
| `schemaVersion` | string | `"2.0"` | 平台元数据规范契约版本 |
| `id` / `name` | string | `"website-developer"` | 员工包全局唯一系统标识 |
| `version` | string | `"1.1.0"` | 语义化版本号 |
| `type` | string | `"agent"` | 扩展包实体类型（AI 员工） |
| `ownership` | string | `"general"` | 权限与归属级别（通用通用级） |
| `displayName` | string | `"网站开发专家"` | 客户端界面、应用市场与列表标题名称 |
| `slogan` | string | `"不懂技术也能做网站，内置丰富风格模板，每步看满意才交付"` | 核心一句话价值主张（显示在对话工作台头像下方） |
| `description` | string | `"不懂技术也能轻松做出好网站。无论是单位介绍、产品展示、日常事务登记还是活动报名，直接把想法告诉我。系统内置了丰富的版面和视觉风格，我会先做两版 Demo 给你直观对比，你点头认可后我再动手做，每步看得见、测得通，踏实又省心。"` | 岗位详细职责介绍（显示在市场招募详情页，通俗人话） |
| `categoryId` | string | `"developer-tools"` | 平台市场分类（开发与建站工具） |
| `icon` | string | `"./agent/assets/logo.png"` | 员工主头像文件路径 |
| `iconAlt` | string | `"网站开发专家"` | 头像替代文本（无障碍支持） |
| `tags` | array | `["网站开发", "机构门户", "产品展示", "业务工作台", "活动落地页"]` | 市场检索与能力标签 |
| `agent.action.type` | string | `"conversation"` | 交互模式（原生对话型，打开后进入专属工作台） |
| `agent.owner` | string | `"fde-dev"` | 业务责任人 / 维护团队标识 |
| `agent.visibility.departments` | array | `[]` | 可见部门限制（空数组表示全员可见） |
| `agent.defaultEnabled` | boolean | `true` | 招募安装后是否默认启用 |
| `agent.quickPrompts` | array | 4 个快捷发起项（对应四大核心场景快捷唤起胶囊） | 首页底部快捷推荐胶囊标识与场景归属 |

---

## 二、 市场与招募详情页场景 Case 配置（Showcases）

对应技术字段：[`release/metadata.json`](release/metadata.json) 中的 `agent.showcases`  
**展示场景**：用户招募该员工前的市场预览详情页，标题为**「推荐场景」**，用户可横滑并点击放大查看案例全景网页截图与详细说明。

| 序号 | 案例唯一标识 (`id`) | 业务场景定位 | 案例详细解析文案 (`description`) | 配套素材规格与路径 |
| :---: | :--- | :--- | :--- | :--- |
| **Case 1** | `official-portal-case` | **机构与团队官方门户** | **机构与团队主页**：展示核心业务布局、团队骨干阵容、专业资质与在线联系入口，全方位展现机构权威与品牌风采。 | 16:9 全景网页效果图<br>`./agent/assets/showcases/portal.png` |
| **Case 2** | `product-showcase-case` | **产品与服务展示中心** | **产品与服务展示**：图文并茂陈列核心方案、功能亮点与服务报价，内置咨询预约与联系通道，助力业务成果直观转化。 | 16:9 全景网页效果图<br>`./agent/assets/showcases/showcase.png` |
| **Case 3** | `admin-workbench-case` | **轻量业务与事务工作台** | **轻量业务工作台**：提供日常事项登记、流转审批、状态过滤与数据统计看板，数据本地运行安全可控，免去繁琐纸质流转。 | 16:9 全景网页效果图<br>`./agent/assets/showcases/workbench.png` |
| **Case 4** | `campaign-landing-case` | **活动与沙龙报名单页** | **活动与报名单页**：集成活动倒计时、时间轴议程安排、嘉宾阵容展示与在线报名表单，一键上线高效沉淀参会名单。 | 16:9 全景网页效果图<br>`./agent/assets/showcases/landing.png` |

---

## 三、 对话工作台 6 大常用操作入口配置（Scenes）

对应文件：[`release/agent/home.json`](release/agent/home.json)  
**展示场景**：招募成功后进入日常对话工作台，输入框上方横向轮播的 6 张操作卡片，点击即完成意图识别。

| 序号 | 场景标识 (`id`) | 卡片主标题 (`name`) | 卡片副标题 (`description`) | 绑定 3D 高清图标 (`icon`) | 推荐项标题与说明 (`items[0]`) | 驱动技能 (`skillRefs`) |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `official-portal` | **机构与团队主页** | 展示业务特色与团队风采 | [`icon-portal.png`](release/agent/assets/icons/icon-portal.png)<br>*(564×576 PNG)* | **搭建机构与团队主页**<br>展示核心业务、成员风采与联系入口，先出双风格 Demo 对比。 | `site-brief`<br>`site-design` |
| **2** | `product-showcase` | **产品与服务展示** | 图文并茂陈列核心成果 | [`icon-showcase.png`](release/agent/assets/icons/icon-showcase.png)<br>*(564×576 PNG)* | **制作产品与服务展示页**<br>图文陈列主打特色与价格，带扫码或电话咨询入口。 | `site-design`<br>`site-builder` |
| **3** | `admin-workbench` | **轻量业务工作台** | 事项登记与看板流转 | [`icon-workbench.png`](release/agent/assets/icons/icon-workbench.png)<br>*(564×576 PNG)* | **创建日常事项工作台**<br>表单录入、状态过滤与看板流转，本地运行数据安全。 | `site-brief`<br>`site-builder` |
| **4** | `campaign-landing` | **活动与报名单页** | 动态日程与留资预约 | [`icon-landing.png`](release/agent/assets/icons/icon-landing.png)<br>*(564×576 PNG)* | **设计活动落地页**<br>包含活动倒计时、时间轴议程与在线报名留资表单。 | `site-design`<br>`site-check` |
| **5** | `personal-bio` | **个人专业主页** | 展示资历经验与成果名片 | [`icon-bio.png`](release/agent/assets/icons/icon-bio.png)<br>*(564×576 PNG)* | **打造个人专业名片**<br>展现讲师资质、专业履历与学术成果，体面得体。 | `site-design`<br>`site-builder` |
| **6** | `process-guide` | **办事指南与问答** | 步骤指引与折叠问答速查 | [`icon-guide.png`](release/agent/assets/icons/icon-guide.png)<br>*(564×576 PNG)* | **生成办事指南与 FAQ**<br>步骤条清晰拆解流程，折叠卡片整理高频解答。 | `site-brief`<br>`site-design` |

---

## 四、 内置技能绑定与能力契约

对应文件：[`release/agent/bindings.yaml`](release/agent/bindings.yaml) 及各技能目录

| 技能标识 (`id`) | 技能显示名 | 引用来源 (`source`) | 强依赖 (`required`) | 核心职能分工 |
| :--- | :--- | :---: | :---: | :--- |
| **`site-builder`** | **建站编排与实施** | `embedded` | **true (主控)** | 唯一业务编排者：状态机推进、按纵向切片小步增量修改代码、守住不乱重写防线。 |
| **`site-brief`** | **需求梳理** | `embedded` | `false` | 需求前置收敛：向用户提问核心诉求与关键边界，用一句话通俗选项明确首版范围。 |
| **`site-design`** | **网站设计与体验稿** | `embedded` | `false` | 视觉与排版保障：骨架屏双选、双风格高保真体验稿对比、中文字阶与设计 Token 管理。 |
| **`site-check`** | **网站检查与验证** | `embedded` | `false` | 交付前客观巡检：真实浏览器端到端主流程演练、移动端横向滚动排查、出具客观事实报告。 |

---

## 五、 资产与工程文件清单规范

对应文件：[`release/package-files.txt`](release/package-files.txt) 与打包脚本 [`tools/build_dist.py`](tools/build_dist.py)

### 1. 图像视觉资产列表
- **员工头像**：`agent/assets/logo.png`
- **工作台 3D 高清图标**（尺寸严格保持 188:192 比例，3 倍 Retina 高清分辨率 `564 × 576` PNG）：
  - `agent/assets/icons/icon-portal.png`（机构与团队主页）
  - `agent/assets/icons/icon-showcase.png`（产品与服务展示）
  - `agent/assets/icons/icon-workbench.png`（轻量业务工作台）
  - `agent/assets/icons/icon-landing.png`（活动与报名单页）
  - `agent/assets/icons/icon-bio.png`（个人专业主页）
  - `agent/assets/icons/icon-guide.png`（办事指南与问答）
- **招募详情页案例效果图（规划中）**：
  - `agent/assets/showcases/portal.png`（16:9 全景效果图）
  - `agent/assets/showcases/showcase.png`（16:9 全景效果图）
  - `agent/assets/showcases/workbench.png`（16:9 全景效果图）
  - `agent/assets/showcases/landing.png`（16:9 全景效果图）

### 2. 平台安装包构建与检验
- **构建输出**：`dist/website-developer-1.1.0.zip`
- **自动化测试校验**：
  - `test_package_manifest_covers_every_release_file`：保证 `release/` 内所有文件无遗漏列入清单；
  - `test_dist_directory_matches_manifest_byte_for_byte`：保证分发包产物与源码目录达到字节级一致。
