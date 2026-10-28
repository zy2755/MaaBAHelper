"""binding 直连模式跑悬赏通缉/学院交流会（调试用）。

用法：python tools/run_bounty.py [bounty|academy] [mode] [level]
默认：bounty 高架公路 第10关（入场后即返回，不开战）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from stage_config import KINDS  # noqa: E402

from maa.custom_action import CustomAction  # noqa: E402


class ClearStages(CustomAction):
    """总控：业务区入口 → 模式 → 逐关（滚动搜索→入场→返回）。"""

    def run(self, context, argv):
        import json

        param = json.loads(argv.custom_action_param or "{}") or {}
        # 框架对 custom_action_param 是整体替换（非深合并），interface/override 可能丢 kind，
        # 从节点名（悬赏_总控/学院_总控）兜底推导
        kind = param.get("kind") or ("bounty" if argv.node_name.startswith("悬赏") else "academy")
        cfg = KINDS[kind]
        prefix = "悬赏" if kind == "bounty" else "学院"

        level_enabled = param.get("level_enabled", {})
        levels = [i for i in range(1, cfg["levels"] + 1) if level_enabled.get(str(i))]
        if not levels and not level_enabled:
            levels = list(range(1, cfg["levels"] + 1))  # 无选项时默认全部（调试模式）
        print(f"[{kind}] 目标关卡: {levels}", flush=True)

        # 回主界面保障：任务可能从任意页面启动；先清弹窗队列再判主界面
        for _ in range(10):
            td = context.run_task("通用_弹窗返回键")
            if not (td and td.nodes and td.status and td.status.succeeded):
                break
        for _ in range(6):
            td = context.run_task("主界面_判定")
            if td and td.nodes and td.status and td.status.succeeded:
                break
            context.run_task("通用_按返回")
        # 主界面闲置息屏会让 UI 淡出，先点一下顶部空白唤醒
        context.run_task("通用_唤醒屏幕")

        # 进业务区的 next 链内已处理剧情警告弹窗和点入口，勿重复调用（否则空烧 ~7s）
        context.run_task(f"{prefix}_进业务区")

        # 模式选择：两轮机会，点击后验证进入关卡列表
        for _round in range(2):
            hit = False
            for m in cfg["modes"]:
                td = context.run_task(f"{prefix}_模式_{m}")
                if td and td.nodes and td.status and td.status.succeeded:
                    hit = True
            if hit:
                vtd = context.run_task("通用_列表页判定")
                if vtd and vtd.nodes and vtd.status and vtd.status.succeeded:
                    break
                print(f"[{kind}] 点击了模式但未进入列表，重试", flush=True)

        fail_streak = 0
        for i in levels:
            td = context.run_task(f"{prefix}_关卡_第{i}关")
            if td and td.nodes and td.status and td.status.succeeded:
                fail_streak = 0
                print(f"[{kind}] level {i}: DONE", flush=True)
            else:
                fail_streak += 1
                print(f"[{kind}] level {i}: SKIP/FAIL", flush=True)
                if fail_streak >= 3:
                    print(f"[{kind}] 连续3关未命中（券尽或界面异常），收尾", flush=True)
                    break

        # 收尾：从关卡列表/编队页返回主界面，到位即停（盲点会在主界面点开菜单弹窗）
        for _ in range(4):
            context.run_task(f"{prefix}_收尾_返回")
            ltd = context.run_task("主界面_判定")
            if ltd and ltd.nodes and ltd.status and ltd.status.succeeded:
                break
        return True


class EnterLevel(CustomAction):
    def run(self, context, argv):
        import json

        param = json.loads(argv.custom_action_param or "{}") or {}
        kind = param.get("kind") or ("bounty" if argv.node_name.startswith("悬赏") else "academy")
        level = int(param.get("level", 1))
        prefix = "悬赏" if kind == "bounty" else "学院"
        level_str = f"{level:02d}"

        for _ in range(3):
            context.run_task(f"{prefix}_列表滑到顶")

        for attempt in range(4):
            td = context.run_task(f"{prefix}_找关卡_第{level}关")
            if td and td.nodes and td.status and td.status.succeeded:
                reco = td.nodes[-1].recognition
                box = reco.box if reco else None
                if box:
                    import time as _time
                    _time.sleep(1.2)  # 等列表滚动惯性停止，否则点击打在移动目标上
                    # 同帧 OCR 的 all_results 里取与编号行 y 对齐的"入场"按钮。
                    # 注意 run_action 不执行识别，roi 覆盖无效，必须直接传 box
                    cy = box[1] + box[3] / 2
                    btns = [
                        r
                        for r in (reco.all_results or [])
                        if getattr(r, "text", "") == "入场" and r.box
                    ]
                    ok = False
                    if btns:
                        btn = min(
                            btns, key=lambda r: abs(r.box[1] + r.box[3] / 2 - cy)
                        )
                        if abs(btn.box[1] + btn.box[3] / 2 - cy) <= 40:
                            act = context.run_action(f"{prefix}_点入场", box=btn.box)
                            ok = bool(act and act.success)
                    if not ok:
                        # 兜底：run_task 会跑识别，行对齐 roi 防止点中相邻行
                        ftd = context.run_task(
                            f"{prefix}_点入场",
                            pipeline_override={
                                f"{prefix}_点入场": {
                                    "roi": [1000, max(80, box[1] - 25), 280, 80]
                                }
                            },
                        )
                        ok = bool(ftd and ftd.nodes and ftd.status and ftd.status.succeeded)
                    if ok:
                        print(f"[{kind}] level {level}: entered at {box}", flush=True)
                        return True
                    print(f"[{kind}] level {level}: 入场点击失败", flush=True)
                    return False
            context.run_task(f"{prefix}_列表下滑")

        print(f"[{kind}] level {level}: not found", flush=True)
        return False


def main():
    from maa.controller import AdbController
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.toolkit import Toolkit

    kind = sys.argv[1] if len(sys.argv) > 1 else "bounty"
    mode = sys.argv[2] if len(sys.argv) > 2 else KINDS[kind]["modes"][0]
    prefix = "悬赏" if kind == "bounty" else "学院"
    raw_levels = sys.argv[3] if len(sys.argv) > 3 else "10"
    if raw_levels.lower() == "all":
        level_enabled = {str(i): True for i in range(1, KINDS[kind]["levels"] + 1)}
    else:
        level_enabled = {str(int(x)): True for x in raw_levels.split(",")}

    Toolkit.init_option("./")
    res = Resource()
    res.post_bundle("assets/resource").wait()

    res.register_custom_action("bounty_academy_clear", ClearStages())
    res.register_custom_action("stage_enter_level", EnterLevel())

    ctl = AdbController(
        adb_path=r"D:/Program Files/Netease/MuMu/nx_main/adb.exe",
        address="127.0.0.1:16384",
        config={"extras": {"mumu": {"enable": True, "index": 0, "path": r"D:/Program Files/Netease/MuMu"}}},
    )
    ctl.post_connection().wait()
    tasker = Tasker()
    tasker.bind(res, ctl)

    overrides = {
        f"{prefix}_模式_{mode}": {"enabled": True},
        # 注意：post_task 的 pipeline_override 对 custom_action_param 是整体替换而非深合并，
        # 必须显式带 kind，否则 agent 侧默认 bounty、走错整条链
        f"{prefix}_总控": {
            "custom_action_param": {"kind": kind, "level_enabled": level_enabled}
        },
    }
    job = tasker.post_task(f"{prefix}_主流程", overrides)
    job.wait()
    st = job.status
    print("FINAL_RESULT succeeded:", st.succeeded, "failed:", st.failed, flush=True)


if __name__ == "__main__":
    main()
