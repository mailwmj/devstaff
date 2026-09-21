---
name: site-check
version: 1.1.0
description: 只读验证。生成和校验检查计划与报告，按 L0-L5 轴只读验证核心任务和相称的静态、错误、移动端、再次打开行为，不改源码。
---
# 网站检查与验证

检查本身很轻，结果确定且机器可读，自己不启动浏览器。先用 `check.py` 生成计划或校验报告协议，再按计划在浏览器里只读取证；浏览器验证由宿主在独立的 Checker 上下文里完成。

## 协议

`check.py plan PROJECT --contract .site/design/surface-brief.md [--changed-from REF] [--out PATH] [--summary]` 读合同和源码，算出 SHA-256 指纹，给出本轮要查的轴和门禁顺序，并输出 `source_files / source_excluded / source_manifest`——哪些文件算产品、哪些被排除，都摆出来。默认打印完整 manifest；`--summary` 把 stdout 收敛成计数、指纹和轴，完整 plan 用 `--out` 落盘，两个一起用就不会把逐文件清单灌进上下文。产品源码之外的运行期状态（`uploads/`、构建产物、`*.db`、`*.sqlite`、`*.log`）不进指纹：店主卖出第一瓶水不该作废一份关于代码的报告。根目录 `data/` 不整体排除——静态站的 `data/products.json` 是产品内容，改了就该作废报告；运行期数据仍按后缀排除。工具链也一样：项目根目录里有 `skills.json` 时，它声明的 skill 目录（`site-brief`、`site-builder`、`site-design`）连同 `AGENTS.md`、`install.py`、`skills.json` 都不进指纹——那些是干活用的说明书，改一次 skill 不该作废一轮检查。检查脚本自己仍算源码，改了它，它产出过的 PASS 就不再作数：能被中途放松的检查，说不了算数。

本轮的 plan、report 和临时探针脚本都放 `.site/` 下。`.site` 不进源码指纹，产物写在那里不会影响自己；写进项目根会让产物算进源码，刚写完的报告就对自己失效了。

`source_excluded` 是给你核对的：如果里面出现了真正属于产品的东西（比如一个随产品发布的只读 `.db`），那说明排除规则猜错了，把它当成限制如实写进报告，不要当作已覆盖。

给了 `--changed-from` 时，报告**哪些文件变了**（`changed_files` 的 added / removed / modified）。`REF` 有两种输入，不会混淆：可读的旧计划或报告 JSON（直接用它的指纹；旧文件里带 `source_manifest` 时也能列出逐文件变化），或者项目所在仓库里能解析的 git revision（分支、标签、提交，按该 revision 重算再比对）。两种都不是时，机器可读地报错，`changed_files` 为 `null`，不猜范围。**哪些轴要重验由你判断，不由工具规定**：文件后缀推不出影响面，一条 `display:none` 就能让核心任务消失，和挪一个像素的代价完全不同。

`check.py validate-report PROJECT REPORT.json` 校验一份检查报告是否符合协议，返回 `valid / overall / invalidated_axes / reverify / reverify_vas / browser_blocked / errors`。`state.py verify --report` 会先跑它，`valid` 不为真就拒绝记录，所以它是交付的**门禁**，不是参考意见：指纹对不上当前源码的报告不是"部分过期"，而是不成立。**每一轮都针对当前源码写一份新报告**，没重跑的轴如实记为 `limited` 并写明是哪条，不要拿旧报告凑。

报告的骨架（下面的指纹从 `check.py plan` 的输出里取，不要自己算）：

```json
{
  "project_root": "/项目绝对路径",
  "mode": "guided",
  "overall": "verified",
  "independent": false,
  "contract_sha256": "plan 的 contract_sha256",
  "source_sha256": "plan 的 source_sha256",
  "axes": {
    "core_task": {"status": "verified", "observed": "登记 → 刷新 → 数量正确，5 条记录"}
  },
  "evidence": ["可核对的事实"],
  "limitations": []
}
```

`axes` 的键取 `plan` 的 `required_axes`；没过的视觉轴把受影响的 VA 写进 `failed_vas`。`overall` 取最差的那条轴，不能比轴的结果更好。报告不强制带 `source_manifest`：把 plan 用 `--out` 存在 `.site/` 下，下一轮 `--changed-from` 直接指向它就能列出逐文件变化；要报告自包含再原样带上（代价是体积，每个文件约 100 字节）。无论带不带，指纹对不上当前源码的报告都不成立。

浏览器从哪来：这份协议自己不启动浏览器，由宿主提供。宿主没有现成浏览器工具时，按当前环境找一条可用路径：宿主内置浏览器、`playwright-cli` 或 `npx @playwright/cli`、Python 的 playwright 包，或本机已缓存的 Chromium 加 CDP 端点。一条都找不到时，浏览器轴记 `not_run`、`overall` 记 `blocked`，并写清缺的是哪种能力；不要用文件存在、构建成功或桩断言顶上。证据落在渲染结果上：元素的实际可见性、文本和布局，不是 DOM 属性、桩数据或截图数量。

六个层级、八条轴：

| 层级 | 轴 | 浏览器 |
| --- | --- | --- |
| L0 | `contract` | 否 |
| L1 | `static_build` | 否 |
| L2 | `core_task` | 是 |
| L3 | `negative_path` | 是 |
| L4 | `visual_desktop` / `visual_mobile` | 是 |
| L5 | `reopen` / `risk` | 是 |

`guided` 的下限是 `guided-core`（contract + static_build + core_task）再加一条最可能失败的路径；`strict` 还要查 `reopen` 和 `risk`，并且独立验证。范围边界说不清时按 `guided-core` 查，不要悄悄缩小覆盖。

合同里的 `动效主张` 存在且不是 `none` 时，视觉轴要额外在“减少动态”下复核一次，不新开轴：

- 把系统或浏览器的“减少动态效果”打开（Playwright 用 `reducedMotion: 'reduce'`），用同一视口重新打开同一页面；
- 检查首屏标题与主行动按钮仍完整可见可用，正文里没有以透明或位移起始、再也回不来的残留，图片是原图而不是空白；
- 声明了动效但页面上一处都没有（相关元素扫出来是 0 个）按空样本判失败，写清扫了多少个对象；
- 动效存在时，在同一个浏览器会话里用一次真实的滚动或指针手势跑一遍，取手势前后 `LayoutCount` 与 `RecalcStyleCount` 的增量（CDP 的 `Performance.getMetrics`，任意 Chromium 端点都取得到），写进 `observed`（只走 `transform` / `opacity` 的动效应当接近 0）。纯 CSS 的动效也要跑一遍：它同样可能在每帧触发重排；
- 结论写进 `visual_desktop` / `visual_mobile` 的 `observed`。**能测“这一拍有没有造成布局工作”，测不了“在某台低端设备上够不够流畅”**；后者做不到就记 `limited` 并点名缺的是哪项。

## 失败与复验

- **静态门禁**：L0/L1 没过就不启动浏览器；浏览器轴必须记为 `not_run`，overall 为 `blocked`。
- **视觉复验范围**：视觉轴没过只复验受影响的页面、状态和视口（报告里记 `failed_vas`），不重跑全部视口。
- **哈希失效**：合同或源码的 SHA-256 对不上，整份报告不成立（合同在 `.site` 下单独指纹，改源码不影响 L0）。指纹管的是"这份报告还算不算数"，不是"哪几条轴要重跑"：对不上之后，重验范围由 `changed_files` 加你的判断决定，别拿后缀当映射。
- **轴依赖**：一条轴没过，依赖它的轴要复验（L0→全部，L1→L2-L5，L2→L3-L5，L3/L4→L5）。
- **说清查了什么**：报 `verified` 的轴必须写 `observed`。这个字段是给下一个读报告的人看的，不是机器在核对你说没说真话——没有字段能承担那件事。写的时候带上数字（"扫了 24 个文字节点"比"对比度检查通过"有用得多），因为空样本是这套流程里唯一能静默通过的错误：选择器一个都没命中时被测对象是 0 个，`every()` 对空列表恒真，你手上那 80 条断言会全部通过并报出 PASS。**这件事只有探针自己能拦**：扫到 0 个对象必须判失败，不能报 PASS。写探针时就把这条写进去，别指望报告能替你发现它。
- **排除项**：指纹只覆盖产品源码，`plan` 的 `source_excluded` 列出被排掉的路径。随产品发布的只读库（种子库、字典）和运行期状态在指纹里长得一样，机器分不出来，所以这份清单要人读一遍：排掉的确实是运行期状态就继续，是产品的一部分就把规则改掉。
- **模式**：`guided` 可以如实返回 `limited`；`strict` 不能 `limited`，而且 `verified` 必须带 `independent`。`independent` 只有在宿主用独立 Checker 上下文真的查过之后才算数；做不到就返回 `blocked`，不要自己打标。

## 五字段回执

返回 `status / summary / artifacts / evidence / limitations`，说完发现、证据和限制就停下，不改源码、不改需求、不说交付。这些字段最终会变成用户看到的话，措辞按 Agent 指令文件的《说人话》（安装后为项目根 `AGENTS.md`，分发根为 `agent/Agent.md`）。`status` 用 `verified`、`limited` 或 `blocked`：

- `verified`：这轮核心任务真的跑通了，有证据。
- `limited`：核心任务实现了，但有明确没验证的部分；`guided` 可以据此交付，但要把限制说清楚。
- `blocked`：核心任务没过，或者缺了让结论成立的关键证据。

有 `.site/design/surface-brief.md` 时，以里面适用的页面、状态、视口和 `VA-*` 为依据；视觉检查走 `site-design` 的只读审查分支，不重新发明方向。先按风险选最小够用的范围：局部修改只查静态和受影响的结果；普通首版查核心任务的成功路径加一个最可能失败的反例（长文本不换行、0 条数据、320px 窄屏这类情况也要试）；严格项目查核心任务、关键反例、适用视口、再次打开和权限隐私风险，并独立取证。

验收依据不止合同。**合同之外，把用户能看到的承诺读一遍**：README、页面文案、按钮和空状态里对用户说过的话，都是要兑现的判据。项目的承诺写在 `README.md` 而验收标准里没写，是这套流程最常见的漏法——判据和探针由同一个人写，会共享同一个盲区；读承诺本身，是唯一能跳出这个盲区的一步。发现的缺陷写进回执的 `limitations`，由 `site-builder` 落进工作日志；你是只读的，不改项目里任何文件。

合同里出现枚举式验收标准（"这三对要达标"）时不要照抄范围：把它当全称量化来查，枚举整页的同类对象。少测的代价由用户承担，多测的代价只是一点时间。
