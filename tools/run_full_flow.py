"""完整日常流程 runner（与 MXU 相同的任务栈）：一键日常 → 悬赏(全刷) → 学院(第1关)。

每阶段打印状态；汇总 maafw 日志中的 ERR/失败节点。
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT / "tools"))

import run_schedule
import run_bounty
from maa.controller import AdbController
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit
import io
import numpy as np
from PIL import Image

Toolkit.init_option("./")
res = Resource()
res.post_bundle(str(ROOT / "assets" / "resource")).wait()
res.register_custom_recognition("schedule_card_executable", run_schedule.CardExecutable())
res.register_custom_action("schedule_clear_all_areas", run_schedule.ClearAllAreas())
res.register_custom_action("bounty_academy_clear", run_bounty.ClearStages())
res.register_custom_action("stage_enter_level", run_bounty.EnterLevel())

ctl = AdbController(
    adb_path=r"D:/Program Files/Netease/MuMu/nx_main/adb.exe",
    address="127.0.0.1:16384",
    config={"extras": {"mumu": {"enable": True, "index": 0, "path": r"D:/Program Files/Netease/MuMu"}}},
)
ctl.post_connection().wait()

def ensure_game_running(ctl, tasker):
    """游戏不在前台则拉起，并循环确认到达主界面（OCR "等级"）。

    标题屏的点击可能被加载期吞掉（更新后首登常见），必须验证到主界面为止。
    """
    import subprocess, time
    import dataclasses
    adb = r"D:/Program Files/Netease/MuMu/nx_main/adb.exe"
    addr = "127.0.0.1:16384"
    pkg = "com.RoamingStar.BlueArchive"
    out = subprocess.run([adb, "-s", addr, "shell", "dumpsys", "window"],
                         capture_output=True, text=True, timeout=20).stdout
    if pkg not in out:
        print("[runner] 游戏未运行，拉起中...", flush=True)
        subprocess.run([adb, "-s", addr, "shell", "monkey", "-p", pkg,
                        "-c", "android.intent.category.LAUNCHER", "1"],
                       capture_output=True, timeout=30)
        time.sleep(30)

    @dataclasses.dataclass
    class _OCR:
        recognition: str = "OCR"
        expected: list = dataclasses.field(default_factory=lambda: ["等级"])
        roi: list = dataclasses.field(default_factory=lambda: [0, 0, 150, 80])

    def at_lobby():
        # 用 adb 裸截屏（MaaFW 的 MuMu IPC 截屏在游戏未加载完时会失败），
        # OCR 用 tasker.post_recognition 吃外部图像
        p = subprocess.run([adb, "-s", addr, "exec-out", "screencap", "-p"],
                           capture_output=True, timeout=25)
        try:
            img = np.ascontiguousarray(np.array(Image.open(io.BytesIO(p.stdout)).convert("RGB")))
        except Exception as e:
            print(f"[runner] adb 截屏失败: {e}", flush=True)
            return False
        det = tasker.post_recognition("OCR", _OCR(), img).wait().get()
        if det.nodes:
            rd = det.nodes[-1].recognition
            return bool(rd and rd.hit)
        return False

    for i in range(8):
        if at_lobby():
            if i:
                print(f"[runner] 已到主界面（第 {i+1} 次尝试）", flush=True)
            return
        print(f"[runner] 未到主界面，点标题屏重试 {i+1}/8", flush=True)
        subprocess.run([adb, "-s", addr, "shell", "input", "tap", "640", "360"], timeout=20)
        time.sleep(15)
    raise RuntimeError("8 次尝试后仍未进入游戏主界面，请人工检查模拟器/游戏状态")

    """游戏不在前台则拉起（模拟器重启/游戏被杀后 runner 不再空跑）。"""
    import subprocess, time
    adb = r"D:/Program Files/Netease/MuMu/nx_main/adb.exe"
    addr = "127.0.0.1:16384"
    pkg = "com.RoamingStar.BlueArchive"
    out = subprocess.run([adb, "-s", addr, "shell", "dumpsys", "window"],
                         capture_output=True, text=True, timeout=20).stdout
    if pkg in out:
        return
    print("[runner] 游戏未运行，拉起中...", flush=True)
    subprocess.run([adb, "-s", addr, "shell", "monkey", "-p", pkg,
                    "-c", "android.intent.category.LAUNCHER", "1"],
                   capture_output=True, timeout=30)
    # 等标题屏出现后点进游戏
    for _ in range(12):
        time.sleep(5)
        out = subprocess.run([adb, "-s", addr, "shell", "dumpsys", "window"],
                             capture_output=True, text=True, timeout=20).stdout
        if pkg in out:
            break
    time.sleep(20)
    subprocess.run([adb, "-s", addr, "shell", "input", "tap", "640", "360"], timeout=20)
    time.sleep(25)
    print("[runner] 游戏已拉起", flush=True)

tasker = Tasker()
tasker.bind(res, ctl)
ensure_game_running(ctl, tasker)

PHASES = [
    ("一键日常", "每日_主流程", {}),
    ("悬赏通缉·第10关·全刷", "悬赏_主流程", {
        "悬赏_模式_高架公路": {"enabled": True},
        "悬赏_总控": {"custom_action_param": {"kind": "bounty", "level_enabled": {"10": True}}},
        "悬赏_快战_最大值": {"enabled": True},
    }),
    ("学院交流会·崔尼蒂第1关", "学院_主流程", {
        "学院_模式_崔尼蒂": {"enabled": True},
        "学院_总控": {"custom_action_param": {"kind": "academy", "level_enabled": {"1": True}}},
    }),
]

results = []
for name, entry, overrides in PHASES:
    t0 = time.time()
    print(f"\n===== 阶段开始: {name} ({entry}) =====", flush=True)
    job = tasker.post_task(entry, overrides)
    job.wait()
    st = job.status
    ok = bool(st and st.succeeded)
    dt = time.time() - t0
    results.append((name, ok, dt))
    print(f"===== 阶段结束: {name} -> {'OK' if ok else 'FAIL'} ({dt:.0f}s) =====", flush=True)

print("\n===== 汇总 =====")
for name, ok, dt in results:
    print(f"{'✓' if ok else '✗'} {name} ({dt:.0f}s)")
