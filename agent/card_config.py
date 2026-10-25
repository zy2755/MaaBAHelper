"""日程卡片坐标表与像素判定（纯数据，无 maa 依赖，agent/binding 两模式共用）。"""

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

GREEN_MIN = 15    # roi 内绿勾像素数阈值
PINK_MIN = 100    # roi 内徽章粉色像素数阈值

CARD_ORDER = list(CARDS.keys())
MAX_AREAS = 11


def count_pixels(img, roi, predicate):
    # argv.image 为 BGR 格式（MaaFW 约定），解包按 B, G, R
    x, y, w, h = roi
    region = img[y : y + h, x : x + w]
    count = 0
    for row in region:
        for b, g, r in row:
            if predicate(int(r), int(g), int(b)):
                count += 1
    return count


def is_green(r, g, b):
    return g > 150 and g > r + 40 and g > b + 40 and r < 180


def is_pink(r, g, b):
    return r > 210 and b > 185 and r > g + 40  # 徽章粉偏紫(高蓝)，排除粉发/橙发


def card_executable(img, name):
    """卡片可执行 = 无绿勾（未执行）且 有爱心徽章（已安排学生）。"""
    cfg = CARDS.get(name)
    if not cfg:
        return False
    green = count_pixels(img, cfg["green"], is_green)
    pink = count_pixels(img, cfg["badge"], is_pink)
    print(f"[card_check] {name}: green={green} badge={pink} => {'EXEC' if green < GREEN_MIN and pink >= PINK_MIN else 'SKIP'}")
    return green < GREEN_MIN and pink >= PINK_MIN
