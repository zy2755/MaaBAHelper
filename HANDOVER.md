# MaaBAHelper 交接文档

> 更新时间：2026-10-26 01:30。本文档供新会话/新开发者接手，包含项目全貌、已完成功能的**真实验证状态**、未完成项和全部踩坑记录。
>
> **2026-10-26 凌晨会话进展**：悬赏/学院两条链均已真机全链验证通过（binding + 真实 MXU 双路径，详见"三"），发现并修复 8 个坑（见"六"#19-25），新增 tools/build_mxu.py 一键同步打包、**刷取次数（刷一次/全刷）选项**，导航 30 秒卡顿已修（实测 11.2s 到列表）。**用户侧使用要点：改 interface.json / agent / pipeline 后，先 `python tools/build_mxu.py` 同步，再重启 MXU（它会缓存旧 interface 映射，见坑 #22）。**

## 一、项目概况

蔚蓝档案（BA）国服的每日/活动自动化项目，基于 MaaFramework PI V2。

- **源项目**：`D:\Downloads\Zcode\自动化\MaaBAHelper`
- **MXU 分发目录**：`D:\Downloads\Zcode\自动化\MXU`（M9A 同款界面，读同目录 interface.json，双击 mxu.exe 即用；**注意**：`MXU/agent` 和 `MXU/resource/pipeline` 是源目录的副本，改源后必须同步，历史上多次因忘同步出 bug）
- **模拟器**：MuMu，ADB `127.0.0.1:16384`，分辨率 1280x720，adb 路径 `D:/Program Files/Netease/MuMu/nx_main/adb.exe`（代码里硬编码）
- **环境**：Python 3.14 + pip 包 `MaaFw`（自带 maafw 二进制）、Node 24（校验工具）、git 代理 127.0.0.1:7897（**大文件 GitHub 下载要走 gh-proxy.com 镜像**）

## 二、目录结构

```
MaaBAHelper/
├── assets/
│   ├── interface.json          # PI V2 入口：任务清单 + 全部 option（select/checkbox）
│   └── resource/
│       ├── pipeline/
│       │   ├── daily.json      # 每日任务环（咖啡厅/邮箱/商店/日程/业务区）
│       │   ├── schedule.json   # 日程清券（agent 总控 + 原子节点）
│       │   ├── bounty.json     # 悬赏通缉 + 学院交流会（78 节点）
│       │   └── common/         # lobby.json(主界面导航)、popup.json(弹窗兜底)
│       ├── image/              # 模板图（placeholder.png 为噪声占位）
│       └── model/ocr/          # ppocr_v6（git 忽略，CI 自动配）
├── agent/                      # agent 子进程模式代码（MXU 用）
│   ├── main.py                 # agent 入口（MAA_AGENT_MODE=1）
│   ├── card_config.py          # 纯数据：日程卡片坐标表+像素判定（无 maa 依赖）
│   ├── stage_config.py         # 纯数据：悬赏/学院的模式、关卡数、坐标
│   ├── schedule_helper.py      # 日程清券（ScheduleClearAllAreas）
│   ├── bounty_helper.py        # 悬赏/学院清剿（BountyAcademyClear + StageEnterLevel）
│   └── my_reco.py / my_action.py
├── tools/
│   ├── maa_gui.py              # 自研 Web 控制台（127.0.0.1:8787，数据驱动读 interface.json）
│   ├── run_bounty.py           # binding 直连调试：悬赏/学院
│   ├── run_schedule.py         # binding 直连调试：日程清券
│   ├── build_mxu.py            # MXU 一键同步+校验+打包（--zip）
│   └── validate_schema.py      # JSON Schema 校验
├── deps/tools/                 # pipeline/interface schema
└── MXU/（在上级目录）           # 组装好的 MXU 分发目录（可打包发人）
```

## 三、功能与真实验证状态（诚实版）

| 功能 | 状态 | 验证情况 |
| ---- | ---- | ---- |
| 环境自检（OCR"等级"） | ✅ 可用 | 多次验证 |
| 咖啡厅领收益+返回 | ✅ 可用 | 真机验证，红点 ColorMatch 防循环 |
| 邮箱一键领取+返回 | ✅ 可用 | 真机验证，+20000 信用点实测 |
| 商店筛选+全选购买 | ✅ 可用 | 真机验证（品类 checkbox 联动购买链；**未勾品类不购买**） |
| 日程跨区域清券 | ✅ 可用 | 真机验证 券 4→0/7，青辉石零消耗（"购买日程券"弹窗自动取消） |
| 悬赏通缉导航+选模式+找关+入场 | ✅ 全链通 | **2026-10-26 双路径复验通过**：binding（券 5→4、+17,140）+ **真实 MXU agent 模式**（用户重启 MXU 后 `[10]→entered→DONE`）；入场方案=同帧 OCR 按钮box直传 run_action |
| 悬赏/学院 快速战斗+结算确认 | ✅ 全链通 | **2026-10-26 真机复验通过**：拆字坑已修（快战确认 expected 改列表 `["是否使用","快速战斗"]`），"快速战斗完成"→结算确认→关面板实测命中 |
| 学院交流会（崔尼蒂/歌赫娜/千禧年 ×4关） | ✅ 崔尼蒂单关验证通过 | 2026-10-26 崔尼蒂第3/1关 binding 全链 DONE ×3（入场→快战→结算→收尾）；**MXU 路径复验**：重启后的 MXU 里悬赏全链 DONE（学院被用户手动停止于导航中途，非代码问题）；歌赫娜/千禧年同构未单独验证 |
| 屏保唤醒 | ✅ 已内置 | 每区域循环前点顶部空白（用户确认屏保=只剩看板，点一下恢复） |
| 青辉石防误购拦截 | ✅ 已内置 | OCR"购买日程券"→点取消（**实测拦截过真实弹窗**） |
| 业务区剧情警告弹窗 | ✅ 已处理 | 自动点取消（实测触发过） |

**实测账目**（截至 2026-10-29 04:45）：信用点 1,040,958,614 → 1,041,336,614。本日消耗：悬赏券 6/6 用尽（含一次真实验证的全刷 x4，+216,000）、学院交流券 2 张（崔尼蒂第1/3关，+70,560/+18,000）。邮件领取今晚未验证成功（见坑#26/#27，修复已就位待下次日常验证）。体力曾异常 -20 未定位（疑似并行 runner 期间误触，坑#29 同期）。本会话消耗：悬赏券 2 张（binding 第10关 + 用户 MXU 复跑第10关，约 3→3/6 中的两张，以游戏内计数为准）、学院券 2 张（binding 崔尼蒂第3关 ×2，现约 4/6）。奖励到账：悬赏 +17,140×1、学院 +70,560×2。

## 四、当前进行中

**无进行中项**——悬赏/学院两条链均已闭环。日常使用入口：
- MXU 界面双击 `../MXU/mxu.exe`
- 调试：`python tools/run_bounty.py [bounty|academy] [模式] [关卡|all|逗号列表]`（如 `academy 崔尼蒂 3`）

占位待启用（遇现场后启用）：邮件"自选奖励跳过"（遇到时 debug/on_error 有现场图）、日程页偶发 abort 的重试优化。

## 五、技术架构要点（为什么这样设计）

- **控制流在 agent 自定义动作，pipeline 只放原子节点**：纯 JSON pipeline 表达不了"循环+计数+条件"，这是日程/悬赏反复失败后定下的架构。agent 通过 `context.run_task(节点名)` 调用 pipeline 原子节点，通过返回的 `TaskDetail`（nodes/status）判断成败。
- **选项开关用 `custom_action_param` 传表而不是节点 enabled**：MaaFW `run_task` 对 disabled 节点**立即失败**，会污染 agent 的失败计数；checkbox 的 override 是 **dict 深合并**（`level_enabled: {"3": true}` 多 case 合并不冲突），select 是单 case 覆盖。
- **两个执行模式**：
  - **agent 子进程模式**（MXU/通用 UI 用）：interface.json 的 `agent` 段拉起 `python ./agent/main.py`，识别器用 `@AgentServer.custom_recognition` 装饰器（`MAA_AGENT_MODE=1` 时才装饰，避免污染 binding）。
  - **binding 直连模式**（tools/ 调试脚本用）：`res.register_custom_recognition(name, obj)` 注册到 Resource。**两种模式的基类/二进制互斥**，详见踩坑 #5。
- **界面**：MXU（官方）为主界面；`tools/maa_gui.py` 是自研 Web 备用（数据驱动读 interface.json，同样支持全部任务）。

## 六、踩坑记录（每条都真实付出过调试时间）

1. **MaaFW OCR 的 expected 用短词**：BA 按钮字距大，OCR 会拆字（"确认"→"确"/"认"），长词匹配失败；识别结果以 maafw.log 的 `reco_details.all` 为准。
2. **ColorMatch 的 method 默认 4 = RGB**（不是 OpenCV 默认 BGR），lower/upper 按 R,G,B 写。
3. **agent 的 argv.image 是 BGR** numpy（文档写明）；颜色判定解包按 `for b, g, r in row`。
4. **And 组合识别不支持子条件 inverse**（内联和节点引用都无效）→ 组合条件改用 agent 像素判定。
5. **`maa.agent.agent_server` 与 framework 二进制互斥**：进程 import 了 agent_server 后 `Resource()` 等框架 API 全部 NotImpl。binding 脚本**禁止** import 任何 agent 模块；共用逻辑放无 maa 依赖的纯数据模块（card_config/stage_config）。
6. **`CustomAction.RunArg` 没有 image 字段**（CustomRecognition.AnalyzeArg 才有）；CustomAction 里拿不到截图，识别要靠 run_task 节点或参数传递。
7. **next 列表共享父节点的 20s 总超时**：排前面的不命中候选会吃光窗口，后面的候选不被尝试——分发节点的前置候选必须设小 timeout。
8. **`run_task`/`post_task` 的入口识别不命中立即失败（不重试）**；next 匹配才有超时重试。
9. **disabled 节点 run_task 立即失败**（"no valid/enabled node"）——不要用节点 enabled 当 agent 循环的开关。
10. **adb 点击后必须 sleep**：弹窗/转场动画帧上的点击无效（曾因无 sleep 点空结算确认）。
11. **列表滑动后有惯性滚动**：点击前等 1.2s，否则打在移动目标上（悬赏入场时灵时不灵的根因）。
12. **圆形按钮 + DirectHit 随机点击会出框**：返回箭头等圆形按钮用 target 收紧到圆心。
13. **用户发的截图与实机坐标不一致**（缩放比不同）——一切坐标以 MaaFW 实拍（debug/on_error 现场）为准。
14. **MXU/agent 与 MaaBAHelper/agent 是双副本**，改源必须同步（diff 校验过一致）。
15. **汇报只报日志证实的事实**：曾把任务信息面板的券预览标签（5→4）当成实际消耗汇报，被用户抓到（券一直 5/6）。
16. **MAA 日志文件有轮转**（maafw.log 按启动轮换目录/文件），找日志先 `stat` mtime 确认是新文件；agent 的 print 在 MXU 的 `debug/mxu-agent-0-*.log`。
17. **主界面/日程页等有"双视图"状态**（地图视图 vs Location Select 列表视图），入口节点要做双起点适配（OCR 两个特征并行匹配）。
18. **BA 业务区进图会弹"剧情警告"**（确认会跳活动界面），必须点取消——已有节点处理。
19. **tools/maa_gui.py 的 HTTP 接口对非 UTF-8 请求体要加解析保护**（曾因 curl 发 GBK body 的 UnicodeDecodeError 崩掉整个服务器，已修：do_POST 解析异常返回 400）。
19. **`run_action` 不执行识别**：只跑节点动作部分，直接用传入的 `box` 当点击目标；`pipeline_override` 改 roi 对它无效（曾因此"failed to get target rect"）。要"识别后点击"用 `run_task`；要精确点某个已识别目标，把该目标的 box 通过 `context.run_action(entry, box=...)` 直传。悬赏入场最终方案：从 `找关卡` 节点同帧 OCR 的 `recognition.all_results` 里取与编号行 y 对齐（±40px）的"入场"按钮 box 直传——同帧坐标天然对齐，配合 1.2s 惯性等待稳定命中。
20. **`post_task` 的 pipeline_override 对 `custom_action_param` 是整体替换不是深合并**：override 只写 `level_enabled` 会把 pipeline 里的 `kind` 丢掉，agent 默认成 bounty 走错整条链（学院任务跑去悬赏页找"03"，现象是 `not found`）。**修复**：agent 侧从 `argv.node_name`（悬赏_总控/学院_总控、悬赏_关卡_第N关/学院_关卡_第N关）兜底推导 kind，三处实现（agent/bounty_helper.py、tools/run_bounty.py、tools/maa_gui.py）已统一；run_bounty.py 的 override 也显式带 kind。注意 interface checkbox 的 override 依旧只传 level_enabled——靠 node_name 推导兜住。
21. **确认弹窗文案 OCR 会拆行**："是否使用悬赏通缉挑战券x1进行1次快速战斗?"被拆成"…进行1次快速"+"战斗?"两个框，expected="快速战斗"匹配不上导致确认按钮永远不点。**修复**：expected 用列表 `["是否使用","快速战斗"]`（行首短词兜底），悬赏/学院两处已改。
22. **MXU 界面进程会缓存 interface.json 的选项映射**：改 interface.json 后不重启 MXU，它仍按旧格式的 case→override 映射发参数（2026-10-26 01:26 事故：旧映射发出 `{"学院_关卡_第3关":{"enabled":true}}`，总控参数没传 → `level_enabled` 落回 pipeline 默认全 false → `目标关卡: []` 什么都不打直接收尾）。**改 interface.json 后必须重启 MXU**；agent 侧 levels=[] 的保守行为（不打任何关）是故意的，防误刷全量。
23. **收尾_返回 的点击坐标 (1225,8) 在主界面是"菜单"键**：收尾盲点 4 次会在主界面点开菜单弹窗，给下一个任务留雷（主界面_判定仍命中、但界面脏）。**修复**：收尾循环改为"点一次返回→判定主界面→命中即停"（三处实现同步）。
24. **"可能不出现"的检测节点必须设小 timeout**：剧情警告_取消/警告点取消/点入口/模式节点原本无 timeout，未命中时空烧默认超时（10-20s），且进业务区 next 链和总控显式调用各烧一次——这就是"进悬赏/学院界面停 30 秒"的根因。**修复**：上述节点 timeout 2000-5000，且总控删掉冗余的 剧情警告/点入口 显式调用（进业务区 next 链已处理）。实测主界面→关卡列表 11.2s（8s 为转场动画必要等待）。
25. **Toolkit.init_option 传绝对路径会在该路径下再嵌一层 debug/**（日志写到 debug/debug/maafw.log）；调试脚本一律用 `Toolkit.init_option("./")` 相对路径。
26. **BA 主界面闲置约 3 分钟后 UI 整体淡出**（只剩场景人物，顶栏/导航/邮件红点全消失；MaaFW 截图可证）。此时邮件 ColorMatch、日程入口 OCR 等全部落空，链穿透到 DirectHit 节点造成假失败——"一键日常启动即 22s FAIL"的根因。**修复**：新增 `通用_唤醒屏幕`（点顶部空白 (600,80,80,40)，用户实测点一下即恢复），挂在每日链头（弹窗清除后）和悬赏/学院 agent 回主界面保障后。
27. **登录弹窗是排队的**：签到簿 → 沙勒新闻 → 活动通知 依次出现。已建 `通用_弹窗返回键` 清除链：标题命中 → 勾"今日不再显示"（沙勒新闻）→ 按安卓返回键（ClickKey keycode 4）；**签到簿走专属分支**——它是全屏页，无视返回键、无关闭钮（全屏 OCR 证实），按返回只弹"当前无法使用"toast，必须点"今日"格子（未签则签、已签 toast 后关板）。点格子关闭不算正规关闭，之后每次回主界面它还会再弹，清除链每次自动处理。
28. **ClickKey 节点不可自引用 next**（曾写 `next:[自己]` 触发连环报错）；另外日志里 "invalid node id, handle error" 多数是**良性噪音**——链超时/bad next 都会打这行，别当节点表损坏去查。
29. **同设备禁止两个 Tasker 并行**：调试时开第二个 tasker 抢控制器，两个 runner 互相干扰，表现为节点时好时坏、动作丢失、进程静默退出（2026-10-29 深夜踩过，浪费一小时）。多进程调试前先 `tasklist | findstr python`。
30. **每日 04:00 刷新券**；入场成功后 `SKIP/FAIL` 多半是券尽的预期行为（快战按钮不可用）。日志时间戳跨越 0 点时注意对账。
31. **流程日志里 OCR expected 是子串匹配**：主界面的活动倒计时 "10m" 会被 `expected:"10"` 误命中——找关卡节点 roi 已收窄到编号列 [660,90,300,630] 规避；新节点选 roi 时避开屏上其他含数字的区域。

## 六点五、刷取次数功能（2026-10-26 02:00 新增）

- interface 新增共享 select 选项 **刷取次数**（悬赏通缉/学院交流会任务都引用）：**刷一次**（默认）/**全刷**。
- 全刷 = 每关入场后先点任务信息面板的"最大值"按钮（`悬赏/学院_快战_最大值` 节点，roi [1020,265,120,65] 实测校准，默认 disabled，选项启用），再"开始快速战斗"→确认，一次用尽剩余挑战券。
- 关卡节点 next 链：`[快战_最大值, 快战_点击]`（disabled 跳过零成本）。
- **零消耗验证已做**：入场→最大值命中(0.9993)→快战点击→确认弹窗显示"挑战券x4进行4次快速战斗"（与账目 4/6 吻合）→手动取消，未耗券。真实全刷的确认+多倍结算未实测（结算节点与单刷共用，首次真实使用时留意）。

## 七、调试方法

```bash
# binding 直连跑悬赏/学院（关卡可单关数字、逗号列表或 all；跑完自动收尾回主界面）
cd MaaBAHelper && python tools/run_bounty.py bounty 高架公路 10
cd MaaBAHelper && python tools/run_bounty.py academy 崔尼蒂 3

# 真实战斗未实现——当前到任务信息面板后走"快速战斗"链（快速战斗=三星关直接拿奖励）
# 日志（先 stat mtime 确认新文件）：
#   binding 调试 → MaaBAHelper/debug/maafw.log + on_error/ 现场截图
#   MXU 运行    → MXU/debug/maafw.log + mxu-agent-0-*.log（agent print）
#   grep 记得加 -a（日志混中文会被当二进制）
# 校验（每次改 pipeline/interface 后必跑）：
cd MaaBAHelper && npx @nekosu/maa-tools check && python tools/validate_schema.py --schema-dir deps/tools --resource-dirs assets/resource --interface-files assets/interface.json
# 同步 MXU（改 agent/pipeline/interface 后，含校验；--zip 额外打包 dist/MXU_<日期>.zip 剔除pdb/运行时目录）：
cd MaaBAHelper && python tools/build_mxu.py [--zip]
```

## 八、下一步计划（按优先级）

1. ~~悬赏入场真机复验~~ ✅ 2026-10-26 完成（券 5→4）
2. ~~学院交流会链真机验证~~ ✅ 2026-10-26 崔尼蒂第3关完成（歌赫娜/千禧年同构，用户崔尼蒂第4关未打故未全测）
3. 邮件自选跳过、屏保节点：遇现场后启用
4. 未做的功能：总力战周常、活动关扫荡（interface 已有"活动扫荡"占位说明）
5. 可选：切区动画 abort 重试优化；~~MXU 一键打包脚本~~ ✅ tools/build_mxu.py 已实现（同步+校验+--zip）
