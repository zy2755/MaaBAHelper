"""蔚蓝档案日程清券：卡片可执行判定（自定义识别）。

判定逻辑（对应"全部日程"面板上的日程卡片）：
- 绿勾（亮绿色成簇像素）出现在第一个学生头像右上角 => 该日程今日已执行，跳过
- 爱心数字徽章（粉色圆）在第一个学生头像右下角 => 该日程已安排学生，可执行
- 可执行 = 无绿勾 且 有徽章；其余情况返回未命中
"""

import json
import os

from card_config import CARDS, CARD_ORDER, MAX_AREAS, card_executable, count_pixels, is_green, is_pink, GREEN_MIN, PINK_MIN

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.custom_recognition import CustomRecognition
from maa.context import Context

# AgentServer 装饰注册仅在 agent 子进程模式（agent/main.py）下生效；
# binding 直连模式（调试脚本）由调用方 register 到 Resource，避免上下文冲突
_AGENT_MODE = os.environ.get("MAA_AGENT_MODE") == "1"


def _as_recognition(name):
    def wrapper(cls):
        return AgentServer.custom_recognition(name)(cls) if _AGENT_MODE else cls
    return wrapper


def _as_action(name):
    def wrapper(cls):
        return AgentServer.custom_action(name)(cls) if _AGENT_MODE else cls
    return wrapper


# 卡片坐标表（1280x720 基准）：绿勾检测区 / 爱心徽章检测区 / 点击热区
CARDS = {
    "六和阁":     {"green": (199, 253, 24, 20), "badge": (185, 290, 40, 30), "click": (275, 220, 40, 60)},
    "白虎公园":   {"green": (546, 253, 24, 20), "badge": (532, 290, 40, 30), "click": (621, 220, 40, 60)},
    "茶园":       {"green": (199, 557, 24, 20), "badge": (185, 594, 40, 30), "click": (275, 524, 40, 60)},
    "玄武商会":   {"green": (199, 405, 24, 20), "badge": (185, 442, 40, 30), "click": (275, 372, 40, 60)},
    "竹林":       {"green": (546, 557, 24, 20), "badge": (532, 594, 40, 30), "click": (621, 524, 40, 60)},
    "桃源香":     {"green": (892, 253, 24, 20), "badge": (878, 290, 40, 30), "click": (966, 220, 40, 60)},
    "梅花园本馆": {"green": (546, 405, 24, 20), "badge": (532, 442, 40, 30), "click": (621, 372, 40, 60)},
    "炼丹研究会": {"green": (892, 405, 24, 20), "badge": (878, 442, 40, 30), "click": (966, 372, 40, 60)},
}

GREEN_MIN = 15   # roi 内绿勾像素数阈值
PINK_MIN = 100   # roi 内徽章粉色像素数阈值


is_green = lambda r, g, b: g > 150 and g > r + 40 and g > b + 40 and r < 180
is_pink = lambda r, g, b: r > 210 and b > 185 and r > g + 40  # 徽章粉偏紫(高蓝)，排除粉发/橙发


@_as_recognition("schedule_card_executable")
class ScheduleCardExecutable(CustomRecognition):
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:

        param = json.loads(argv.custom_recognition_param or "{}") or {}
        name = param.get("name")
        cfg = CARDS.get(name)
        if not cfg:
            print(f"[schedule_card_executable] 未知卡片: {name}")
            return CustomRecognition.AnalyzeResult(box=None)

        img = argv.image

        if not card_executable(img, name):
            return CustomRecognition.AnalyzeResult(box=None)

        return CustomRecognition.AnalyzeResult(box=list(cfg["click"]), detail={"name": name})


@_as_action("schedule_clear_all_areas")
class ScheduleClearAllAreas(CustomAction):
    """跨区域清券总控（在选择日程地图页调用）。

    遍历 11 个日程区域：每个区域打开"全部日程"面板，逐卡片尝试执行
    （单卡片链为 pipeline 的 日程_卡_X → 日程_面板_开始日程 → 日程_报告确认），
    全部区域处理完或券耗尽（可执行卡片的"开始日程"变灰）后结束。
    """

    MAX_AREAS = 11

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
