<!-- markdownlint-disable MD033 MD041 -->

# MaaBAHelper

蔚蓝档案（Blue Archive）国服每日自动化助手，基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) PI V2。

> **MaaFramework** 是基于图像识别的自动化黑盒测试框架，用 JSON 流水线描述任务，低代码且高扩展。
> 本项目仅供学习研究，请合理使用，账号风险自负。

控制流放在 **agent 自定义动作**（Python），pipeline 只放原子识别/点击节点——日程、悬赏这类"循环+计数+条件"逻辑用纯 JSON 表达不了，这是项目反复失败后定下的架构。界面使用 M9A 同款 **MXU**（Tauri）。

## 功能与验证状态

下表为**真实验证**情况（以日志、券计数、信用点到账为准，不报"应该没问题"）：

| 功能 | 状态 | 验证情况 |
| ---- | ---- | ---- |
| 环境自检（OCR"等级"） | ✅ | 多次验证 |
| 咖啡厅领收益+返回 | ✅ | 真机验证，红点 ColorMatch 防循环 |
| 邮箱一键领取 | ✅ | 真机验证 |
| 商店筛选+购买 | ✅ | 品类 checkbox 联动，未勾品类不购买 |
| 日程跨区域清券 | ✅ | 券 4→0/7，青辉石零消耗（购买弹窗自动取消） |
| 悬赏通缉：导航/选模式/找关/入场/快速战斗/结算 | ✅ | binding + MXU 双路径全链验证，券计数与信用点到账吻合 |
| 学院交流会（入场/快战/结算） | ✅ | 崔尼蒂第 3 关全链 ×2；歌赫娜/千禧年同构未单独实测 |
| 刷取次数（刷一次/全刷=点"最大值"后快战） | 🆕 | 零消耗验证到确认弹窗（"挑战券x4"与余量吻合）；多倍结算画面未实测 |
| 屏保唤醒 / 青辉石防误购 / 剧情警告取消 | ✅ | 均实测触发过 |

## 当前进度（2026-10-26）

- 悬赏/学院两条链完成双路径（调试脚本 + MXU 界面）真机闭环
- 导航 30 秒卡顿已修（可选弹窗节点加小 timeout + 删冗余调用），实测主界面→关卡列表 **11.2s**（8s 为转场动画必要等待）
- 入场点击方案定型：同帧 OCR 结果里取与关卡行 y 对齐的"入场"按钮坐标直传 `run_action(box=...)`
- `tools/build_mxu.py`：MXU 分发目录一键同步 + 一致性校验 + `--zip` 打包
- 收尾保护：返回循环到位即停，不再在主界面误点菜单弹窗

## 不足与已知问题

诚实清单，接手前请先看这里和 [HANDOVER.md](HANDOVER.md)（含 25 条踩坑记录）：

1. **真实战斗未实现**——所有关卡走"快速战斗"（仅三星关可直接拿奖励），不满足条件的关卡无法打。
2. **学院交流会只实测了崔尼蒂**；歌赫娜/千禧年结构与悬赏同构，预计可用但未验证。
3. **全刷（最大值）的多倍结算画面未实测**（零消耗验证停在确认弹窗后取消），首次真实使用请留意结算是否正常关闭。
4. 邮件"自选奖励"跳过、日程页偶发 abort 的重试优化：占位待启用（需要遇到现场截图）。
5. 总力战周常、活动关扫荡：未实现（interface 已留占位说明）。
6. **MXU 界面会缓存 interface.json 的选项映射**——改配置后必须重启 MXU，否则勾选不生效（表现为目标关卡为空、任务空跑）。
7. BA 按钮字距大，OCR 偶发拆字（确认弹窗文案曾被拆成两段导致匹配失败）；已用短词/expected 列表兜底，无法根除。
8. 环境绑定较死：1280x720、MuMu 模拟器，adb 地址/路径硬编码在调试脚本中。
9. 学院"全刷+多关"组合未测（券尽后下一关会 SKIP/FAIL 并收尾，不会误操作但会空跑导航）。

## 快速开始

```bash
# 依赖：Python 3.10+、pip install MaaFw、Node（仅校验工具需要）
# 1. 配置 OCR 模型（首次）：
#    下载 ppocr 到 assets/resource/model/ocr（该目录不入库，CI 亦可自动配置）
# 2. 校验资源：
npx @nekosu/maa-tools check
python tools/validate_schema.py --schema-dir deps/tools --resource-dirs assets/resource --interface-files assets/interface.json
# 3. 界面：MXU 分发目录双击 mxu.exe（读同目录 interface.json），
#    或用自研 Web 控制台：python tools/maa_gui.py （127.0.0.1:8787）
```

## 开发

```bash
# binding 直连调试（悬赏/学院，关卡支持数字/逗号列表/all）
python tools/run_bounty.py bounty 高架公路 10
python tools/run_bounty.py academy 崔尼蒂 3

# 日志：debug/maafw.log + on_error/ 现场截图（grep 记得加 -a）
# 改动 agent/pipeline/interface 后：同步 MXU + 校验
python tools/build_mxu.py [--zip]
```

目录结构：`agent/`（agent 子进程模式代码）、`assets/resource/pipeline/`（原子节点）、`tools/`（调试/校验/打包）、`HANDOVER.md`（完整交接文档）。

## 致谢

- [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 与 MaaXYZ 练习模板
- [MXU](https://github.com/MaaXYZ/MXU) 界面

## 免责声明

本项目仅供学习与交流，登录态自动化存在账号风险，使用产生的后果自负。
