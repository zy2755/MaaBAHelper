"""P0 验证：只跑一键日常（不耗券），验证 唤醒/弹窗链/认证链/蒙版/邮件兜底。"""
import sys, time
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

t0 = time.time()
job = tasker.post_task("每日_主流程", {})
job.wait()
ok = bool(job.status and job.status.succeeded)
print(f"每日_主流程 -> {'OK' if ok else 'FAIL'} ({time.time()-t0:.0f}s)")
