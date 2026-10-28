"""MaaBAHelper 本地控制台（Web GUI）。

数据驱动：任务与选项从 assets/interface.json 动态渲染，
以后新增任务/选项只需改 interface.json 与 pipeline，界面自动跟随。

用法：python tools/maa_gui.py  然后浏览器打开 http://127.0.0.1:8787
"""

import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import jsonc

ROOT = Path(__file__).parent.parent
LOG_PATH = ROOT / "debug" / "maafw.log"

# ---------------------------------------------------------------- Maa 核心


class MaaCore:
    """MaaFramework binding 单例：连接、执行、停止、截图。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.core_ready = False
        self.adb_address = "127.0.0.1:16384"
        self.current_task = None
        self._init_core()

    def _init_core(self):
        from maa.toolkit import Toolkit

        Toolkit.init_option(str(ROOT))
        self.core_ready = True

    def connect(self, adb_address=None):
        from maa.controller import AdbController
        from maa.resource import Resource
        from maa.tasker import Tasker

        with self.lock:
            if adb_address:
                self.adb_address = adb_address
            self.res = Resource()
            if not self.res.post_bundle(str(ROOT / "assets" / "resource")).wait().status.succeeded:
                raise RuntimeError("资源加载失败")
            self.ctl = AdbController(
                adb_path=r"D:/Program Files/Netease/MuMu/nx_main/adb.exe",
                address=self.adb_address,
                config={"extras": {"mumu": {"enable": True, "index": 0, "path": r"D:/Program Files/Netease/MuMu"}}},
            )
            if not self.ctl.post_connection().wait().status.succeeded:
                raise RuntimeError(f"模拟器连接失败: {self.adb_address}")
            self.tasker = Tasker()
            if not self.tasker.bind(self.res, self.ctl):
                raise RuntimeError("Tasker 绑定失败")
            self._register_custom()
            return f"已连接 {self.adb_address}"

    def _register_custom(self):
        """binding 模式的自定义识别/动作（与 agent 子进程模式共用判定逻辑）。"""
        import sys

        sys.path.insert(0, str(ROOT / "agent"))
        from card_config import CARDS, CARD_ORDER, MAX_AREAS, card_executable  # noqa: E402
        from stage_config import KINDS, ENTRY_TO_BUTTON  # noqa: E402
        from maa.custom_action import CustomAction  # noqa: E402
        from maa.custom_recognition import CustomRecognition  # noqa: E402

        class CardExecutable(CustomRecognition):
            def analyze(self, context, argv):
                import json as _json

                param = _json.loads(argv.custom_recognition_param or "{}") or {}
                name = param.get("name")
                if not card_executable(argv.image, name):
                    return CustomRecognition.AnalyzeResult(box=None)
                return CustomRecognition.AnalyzeResult(box=list(CARDS[name]["click"]), detail={"name": name})

        class ScheduleClearAllAreas(CustomAction):
            def run(self, context, argv):
                for area in range(MAX_AREAS):
                    print(f"[schedule_clear] === area {area + 1}/{MAX_AREAS} ===", flush=True)
                    context.run_task("日程_唤醒屏幕")
                    td = context.run_task("日程_打开全部日程")
                    if not (td and td.nodes and td.status and td.status.succeeded):
                        td = context.run_task("日程_打开全部日程")
                    if not (td and td.nodes and td.status and td.status.succeeded):
                        print("[schedule_clear] open panel FAILED", flush=True)
                        return False
                    executed = 0
                    for name in CARD_ORDER:
                        td = context.run_task(f"日程_卡_{name}")
                        if td and td.nodes and td.status and td.status.succeeded:
                            executed += 1
                        else:
                            context.run_task("日程_收尾_关信息面板")
                    context.run_task("日程_收尾_关列表面板")
                    empty = executed == 0
                    if empty and area >= 2:
                        break
                    if area < MAX_AREAS - 1:
                        context.run_task("日程_切下一区域")
                return True

        class ClearStages(CustomAction):
            def run(self, context, argv):
                import json as _json

                param = _json.loads(argv.custom_action_param or "{}") or {}
                # 框架对 custom_action_param 整体替换，可能丢 kind，从节点名兜底推导
                kind = param.get("kind") or (
                    "bounty" if argv.node_name.startswith("悬赏") else "academy"
                )
                cfg = KINDS[kind]
                prefix = "悬赏" if kind == "bounty" else "学院"

                level_enabled = param.get("level_enabled", {})
                levels = [i for i in range(1, cfg["levels"] + 1) if level_enabled.get(str(i))]
                if not levels and not level_enabled:
                    levels = list(range(1, cfg["levels"] + 1))

                # 回主界面保障：先清弹窗队列（登录弹窗会盖屏）再判主界面
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

                # 进业务区的 next 链内已处理剧情警告弹窗和点入口，勿重复调用
                context.run_task(f"{prefix}_进业务区")
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

                fail_streak = 0
                for i in levels:
                    td = context.run_task(f"{prefix}_关卡_第{i}关")
                    if td and td.nodes and td.status and td.status.succeeded:
                        fail_streak = 0
                    else:
                        fail_streak += 1
                        if fail_streak >= 3:
                            break
                # 收尾：到位即停（盲点会在主界面点开菜单弹窗）
                for _ in range(4):
                    context.run_task(f"{prefix}_收尾_返回")
                    ltd = context.run_task("主界面_判定")
                    if ltd and ltd.nodes and ltd.status and ltd.status.succeeded:
                        break
                return True

        class EnterLevel(CustomAction):
            def run(self, context, argv):
                import json as _json

                param = _json.loads(argv.custom_action_param or "{}") or {}
                kind = param.get("kind") or (
                    "bounty" if argv.node_name.startswith("悬赏") else "academy"
                )
                level = int(param.get("level", 1))
                prefix = "悬赏" if kind == "bounty" else "学院"
                level_str = f"{level:02d}"
                for _ in range(3):
                    context.run_task(f"{prefix}_列表滑到顶")
                for _attempt in range(4):
                    td = context.run_task(f"{prefix}_找关卡_第{level}关")
                    if td and td.nodes and td.status and td.status.succeeded:
                        reco = td.nodes[-1].recognition
                        box = reco.box if reco else None
                        if box:
                            import time as _time
                            _time.sleep(1.2)  # 等列表滚动惯性停止
                            # run_action 不执行识别：同帧 OCR 里取 y 对齐"入场"按钮 box 直传
                            cy = box[1] + box[3] / 2
                            btns = [
                                r
                                for r in (reco.all_results or [])
                                if getattr(r, "text", "") == "入场" and r.box
                            ]
                            ok = False
                            if btns:
                                btn = min(
                                    btns,
                                    key=lambda r: abs(r.box[1] + r.box[3] / 2 - cy),
                                )
                                if abs(btn.box[1] + btn.box[3] / 2 - cy) <= 40:
                                    act = context.run_action(
                                        f"{prefix}_点入场", box=btn.box
                                    )
                                    ok = bool(act and act.success)
                            if not ok:
                                ftd = context.run_task(
                                    f"{prefix}_点入场",
                                    pipeline_override={
                                        f"{prefix}_点入场": {
                                            "roi": [1000, max(80, box[1] - 25), 280, 80]
                                        }
                                    },
                                )
                                ok = bool(
                                    ftd and ftd.nodes and ftd.status and ftd.status.succeeded
                                )
                            if ok:
                                return True
                            return False
                    context.run_task(f"{prefix}_列表下滑")
                return False

        self.res.register_custom_recognition("schedule_card_executable", CardExecutable())
        self.res.register_custom_action("schedule_clear_all_areas", ScheduleClearAllAreas())
        self.res.register_custom_action("bounty_academy_clear", ClearStages())
        self.res.register_custom_action("stage_enter_level", EnterLevel())

    # ---- 状态与控制 ----

    def connected(self):
        return hasattr(self, "tasker")

    def running(self):
        return self.connected() and self.tasker.running

    def status(self):
        if not self.connected():
            return {"connected": False, "running": False, "task": self.current_task}
        return {
            "connected": True,
            "running": self.tasker.running,
            "stopping": self.tasker.stopping,
            "task": self.current_task,
            "adb": self.adb_address,
        }

    def run_task(self, entry, overrides=None):
        if not self.connected():
            raise RuntimeError("未连接模拟器")
        if self.tasker.running:
            raise RuntimeError("已有任务在运行")
        self.current_task = entry
        job = self.tasker.post_task(entry, overrides)

        def _watch():
            job.wait()
            self.current_task = None

        threading.Thread(target=_watch, daemon=True).start()
        return entry

    def stop(self):
        if self.connected():
            self.tasker.post_stop()

    def screenshot(self):
        if not self.connected():
            return None
        self.ctl.post_screencap().wait()
        import numpy as np
        from PIL import Image
        import io

        img = Image.fromarray(self.ctl.cached_image)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode()


CORE = MaaCore()

# ---------------------------------------------------------------- interface 解析


def load_interface():
    data = jsonc.loads((ROOT / "assets" / "interface.json").read_text(encoding="utf-8"))
    tasks = [
        {"name": t["name"], "entry": t["entry"], "options": t.get("option", [])}
        for t in data.get("task", [])
    ]
    options = data.get("option", {})
    return {"tasks": tasks, "options": options}


def build_overrides(selection):
    """把界面选择（{option_name: value}）按 cases 定义合并成 pipeline_override。数据驱动，无需理解语义。"""
    interface = load_interface()
    options = interface["options"]
    override = {}

    def merge(dst, src):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                merge(dst[k], v)
            else:
                dst[k] = v

    for opt_name, value in (selection or {}).items():
        opt = options.get(opt_name)
        if not opt:
            continue
        if opt.get("type") == "checkbox":
            names = value if isinstance(value, list) else [value]
            for case in opt.get("cases", []):
                if case["name"] in names:
                    merge(override, case.get("pipeline_override", {}))
        else:  # select
            for case in opt.get("cases", []):
                if case["name"] == value:
                    merge(override, case.get("pipeline_override", {}))
    return override


def tail_log(lines=60):
    try:
        text = LOG_PATH.read_text(encoding="utf-8", errors="replace")
        return "\n".join(text.splitlines()[-lines:])
    except OSError:
        return ""


# ---------------------------------------------------------------- HTTP

HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>MaaBAHelper 控制台</title>
<style>
  :root { --bg:#1b1b28; --panel:#232338; --line:#33334d; --fg:#e8e8f0; --dim:#9a9ab0; --acc:#7aa2f7; --ok:#9ece6a; --warn:#f7768e; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--fg); font-family:"Segoe UI",system-ui,sans-serif; height:100vh; display:flex; flex-direction:column; }
  header { padding:10px 18px; border-bottom:1px solid var(--line); display:flex; align-items:center; gap:14px; }
  header h1 { font-size:17px; font-weight:600; }
  header .dot { width:10px; height:10px; border-radius:50%; background:#555; }
  header .dot.on { background:var(--ok); }
  header .dot.busy { background:var(--warn); }
  header input { background:var(--panel); border:1px solid var(--line); color:var(--fg); padding:5px 8px; border-radius:6px; width:170px; }
  button { background:var(--acc); border:none; color:#111; padding:6px 14px; border-radius:6px; cursor:pointer; font-weight:600; }
  button.gray { background:var(--panel); color:var(--fg); }
  button.red { background:var(--warn); }
  button:disabled { opacity:.45; cursor:default; }
  main { flex:1; display:flex; overflow:hidden; }
  #tasks { width:210px; border-right:1px solid var(--line); padding:12px; overflow:auto; }
  #tasks h3, #opts h3, #right h3 { font-size:12px; color:var(--dim); text-transform:uppercase; letter-spacing:.08em; margin-bottom:10px; }
  .task { padding:9px 12px; border-radius:8px; cursor:pointer; margin-bottom:6px; border:1px solid transparent; }
  .task:hover { background:var(--panel); }
  .task.sel { background:var(--panel); border-color:var(--acc); }
  #opts { width:290px; border-right:1px solid var(--line); padding:12px; overflow:auto; }
  .opt { margin-bottom:16px; }
  .opt label.t { display:block; font-size:13px; margin-bottom:6px; color:var(--dim); }
  .opt select { width:100%; background:var(--panel); color:var(--fg); border:1px solid var(--line); padding:7px; border-radius:6px; }
  .opt .cb { display:flex; align-items:center; gap:8px; padding:4px 2px; cursor:pointer; font-size:14px; }
  #right { flex:1; display:flex; flex-direction:column; padding:12px; overflow:hidden; }
  #shot { background:#111; border:1px solid var(--line); border-radius:8px; height:42%; display:flex; align-items:center; justify-content:center; overflow:hidden; }
  #shot img { max-width:100%; max-height:100%; }
  #log { flex:1; background:#13131d; border:1px solid var(--line); border-radius:8px; margin-top:10px; padding:8px; font-family:Consolas,monospace; font-size:11px; color:#a9b1d6; overflow:auto; white-space:pre-wrap; }
  #runbar { display:flex; gap:10px; margin:10px 0; }
  #runbar button { font-size:14px; padding:9px 22px; }
</style>
</head>
<body>
<header>
  <h1>MaaBAHelper</h1>
  <span class="dot" id="dot"></span><span id="state" style="font-size:13px;color:var(--dim)">未连接</span>
  <span style="flex:1"></span>
  <input id="adb" value="127.0.0.1:16384" placeholder="模拟器 ADB 地址">
  <button class="gray" onclick="connect()">连接模拟器</button>
</header>
<main>
  <div id="tasks"><h3>任务</h3><div id="tasklist"></div></div>
  <div id="opts"><h3>选项</h3><div id="optlist"><p style="color:var(--dim);font-size:13px">选择左侧任务</p></div></div>
  <div id="right">
    <h3>画面与日志</h3>
    <div id="shot"><span style="color:#555">连接后显示实时画面</span></div>
    <div id="runbar">
      <button id="runbtn" onclick="run()" disabled>开始任务</button>
      <button class="red" id="stopbtn" onclick="stop()" disabled>停止</button>
    </div>
    <div id="log"></div>
  </div>
</main>
<script>
let TASKS = [], OPTIONS = {}, SEL = null;
const $ = id => document.getElementById(id);

async function jfetch(url, body) {
  const r = await fetch(url, body ? {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)} : undefined);
  return r.json();
}

async function refreshStatus() {
  const s = await jfetch("/api/status");
  const dot = $("dot");
  dot.className = "dot" + (s.running ? " busy" : s.connected ? " on" : "");
  $("state").textContent = s.running ? "运行中: " + s.task : s.connected ? "已连接 " + s.adb : "未连接";
  $("runbtn").disabled = !s.connected || s.running || !SEL;
  $("stopbtn").disabled = !s.running;
  return s;
}

async function loadInterface() {
  const d = await jfetch("/api/interface");
  TASKS = d.tasks; OPTIONS = d.options;
  const box = $("tasklist");
  box.innerHTML = "";
  TASKS.forEach((t, i) => {
    const el = document.createElement("div");
    el.className = "task"; el.textContent = t.name;
    el.onclick = () => selectTask(i);
    box.appendChild(el);
  });
}

function selectTask(i) {
  SEL = TASKS[i];
  document.querySelectorAll(".task").forEach((e, j) => e.classList.toggle("sel", j === i));
  const box = $("optlist"); box.innerHTML = "";
  if (!SEL.options.length) { box.innerHTML = '<p style="color:var(--dim);font-size:13px">此任务无选项</p>'; refreshStatus(); return; }
  SEL.options.forEach(name => {
    const opt = OPTIONS[name]; if (!opt) return;
    const div = document.createElement("div"); div.className = "opt";
    const label = document.createElement("label"); label.className = "t"; label.textContent = name; div.appendChild(label);
    if (opt.type === "select") {
      const sel = document.createElement("select"); sel.dataset.opt = name; sel.dataset.type = "select";
      opt.cases.forEach(c => { const o = document.createElement("option"); o.value = c.name; o.textContent = c.name; sel.appendChild(o); });
      div.appendChild(sel);
    } else {
      opt.cases.forEach(c => {
        const l = document.createElement("label"); l.className = "cb";
        const cb = document.createElement("input"); cb.type = "checkbox"; cb.value = c.name; cb.dataset.opt = name; cb.dataset.type = "checkbox";
        l.appendChild(cb); l.appendChild(document.createTextNode(c.name)); div.appendChild(l);
      });
    }
    box.appendChild(div);
  });
  refreshStatus();
}

async function connect() {
  $("state").textContent = "连接中...";
  try { await jfetch("/api/connect", {adb: $("adb").value}); } catch (e) { $("state").textContent = "连接失败"; }
  await loadInterface(); await refreshStatus();
}

async function run() {
  if (!SEL) return;
  const selection = {};
  document.querySelectorAll("[data-opt]").forEach(el => {
    const name = el.dataset.opt;
    if (el.dataset.type === "checkbox") {
      selection[name] = selection[name] || [];
      if (el.checked) selection[name].push(el.value);
    } else selection[name] = el.value;
  });
  await jfetch("/api/run", {task: SEL.entry, selection});
  refreshStatus();
}

async function stop() { await jfetch("/api/stop"); refreshStatus(); }

async function pollVisual() {
  try {
    const s = await refreshStatus();
    if (s.connected) {
      const shot = await fetch("/api/screenshot");
      if (shot.ok) { const d = await shot.json(); if (d.img) $("shot").innerHTML = '<img src="data:image/jpeg;base64,' + d.img + '">'; }
    }
    $("log").textContent = (await jfetch("/api/log")).text;
    $("log").scrollTop = $("log").scrollHeight;
  } catch (e) {}
  setTimeout(pollVisual, 3000);
}

loadInterface(); pollVisual();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/interface":
            self._json(load_interface())
        elif self.path == "/api/status":
            self._json(CORE.status())
        elif self.path == "/api/log":
            self._json({"text": tail_log()})
        elif self.path == "/api/screenshot":
            try:
                img = CORE.screenshot()
                self._json({"img": img})
            except Exception:
                self._json({"img": None})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._json({"ok": False, "error": "bad request body"}, 400)
            return
        try:
            if self.path == "/api/connect":
                msg = CORE.connect(payload.get("adb"))
                self._json({"ok": True, "msg": msg})
            elif self.path == "/api/run":
                entry = payload.get("task")
                selection = payload.get("selection", {})
                override = build_overrides(selection)
                msg = CORE.run_task(entry, override or None)
                self._json({"ok": True, "msg": msg, "override": override})
            elif self.path == "/api/stop":
                CORE.stop()
                self._json({"ok": True})
            else:
                self._json({"ok": False}, 404)
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 500)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("MaaBAHelper 控制台: http://127.0.0.1:8787")
    ThreadingHTTPServer(("127.0.0.1", 8787), Handler).serve_forever()
