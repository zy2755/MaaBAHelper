"""binding 直连模式跑日程清券（调试用）。

不 import agent_server（与 framework 二进制互斥）；
自定义识别/动作继承 framework 侧基类并注册到 Resource。
通用 UI/正式包走 agent 子进程模式（agent/schedule_helper.py），逻辑共用 agent/card_config.py。

用法：python tools/run_schedule.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from card_config import CARD_ORDER, MAX_AREAS, card_executable  # noqa: E402

from maa.custom_action import CustomAction  # noqa: E402
from maa.custom_recognition import CustomRecognition  # noqa: E402


class CardExecutable(CustomRecognition):
    def analyze(self, context, argv):
        import json

        param = json.loads(argv.custom_recognition_param or "{}") or {}
        name = param.get("name")
        if not card_executable(argv.image, name):
            return CustomRecognition.AnalyzeResult(box=None)
        from card_config import CARDS

        return CustomRecognition.AnalyzeResult(box=list(CARDS[name]["click"]), detail={"name": name})


class ClearAllAreas(CustomAction):
    def run(self, context, argv):
        # 视图分发已由 pipeline 完成（日程_视图分发），此处必在地图视图
        # 清掉上次中断可能残留的日程信息面板
        context.run_task("日程_收尾_关信息面板")
        # 先按左箭头归位到第一个区域（沙勒业务区），再向右遍历
        for _ in range(12):
            context.run_task("日程_切上一区域")
        print("[schedule_clear] at leftmost area", flush=True)

        empty_area_streak = 0
        for area in range(MAX_AREAS):
            print(f"[schedule_clear] === area {area + 1}/{MAX_AREAS} ===", flush=True)

            # 屏保唤醒：看板状态（UI 全消失）点顶部空白即恢复，正常状态无副作用
            context.run_task("日程_唤醒屏幕")

            # 打开面板（失败重试一次，中途可能撞转场动画）
            td = context.run_task("日程_打开全部日程")
            if not (td and td.nodes and td.status and td.status.succeeded):
                print("[schedule_clear] open panel retry...", flush=True)
                td = context.run_task("日程_打开全部日程")
            if not (td and td.nodes and td.status and td.status.succeeded):
                print("[schedule_clear] open panel FAILED, abort", flush=True)
                return False

            # 逐卡片尝试：失败（含券尽灰按钮）只关掉可能开着的面板，继续下一张
            executed = 0
            for name in CARD_ORDER:
                td = context.run_task(f"日程_卡_{name}")
                if td and td.nodes and td.status and td.status.succeeded:
                    executed += 1
                    print(f"[schedule_clear] {name}: DONE", flush=True)
                else:
                    # 兜底关闭可能停在日程信息面板的画面（未打开时空转）
                    context.run_task("日程_收尾_关信息面板")
                    print(f"[schedule_clear] {name}: SKIP/FAIL", flush=True)

            context.run_task("日程_收尾_关列表面板")

            # 券尽判定：连续多个区域没有任何日程被执行
            empty_area_streak = empty_area_streak + 1 if executed == 0 else 0
            if empty_area_streak >= 3:
                print("[schedule_clear] 3 areas with zero execution => tickets exhausted", flush=True)
                context.run_task("日程_收尾_home")
                return True

            if area < MAX_AREAS - 1:
                context.run_task("日程_切下一区域")

        print("[schedule_clear] all areas visited", flush=True)
        context.run_task("日程_收尾_home")
        return True


def main():
    from maa.controller import AdbController
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.toolkit import Toolkit

    Toolkit.init_option("./")
    res = Resource()
    res.post_bundle("assets/resource").wait()

    res.register_custom_recognition("schedule_card_executable", CardExecutable())
    res.register_custom_action("schedule_clear_all_areas", ClearAllAreas())

    ctl = AdbController(
        adb_path=r"D:/Program Files/Netease/MuMu/nx_main/adb.exe",
        address="127.0.0.1:16384",
        config={"extras": {"mumu": {"enable": True, "index": 0, "path": r"D:/Program Files/Netease/MuMu"}}},
    )
    ctl.post_connection().wait()
    tasker = Tasker()
    tasker.bind(res, ctl)

    job = tasker.post_task("日程_主流程")
    job.wait()
    st = job.status
    print("FINAL_RESULT succeeded:", st.succeeded, "failed:", st.failed, flush=True)


if __name__ == "__main__":
    main()
