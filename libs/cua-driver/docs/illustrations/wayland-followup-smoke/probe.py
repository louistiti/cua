import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from PIL import Image

driver = Path(sys.argv[1])
repo = Path(sys.argv[2])
phase = sys.argv[3]
root = Path(tempfile.mkdtemp(prefix="cua-native-" + phase + "-"))
root.chmod(0o700)
env = os.environ.copy()
env["CUA_TELEMETRY_ENABLED"] = "false"
env["CUA_DRIVER_RS_ENABLE_WAYLAND"] = "1"
env["GDK_BACKEND"] = "wayland"
for kind in ("CONFIG", "CACHE", "STATE", "DATA"):
    path = root / kind.lower()
    path.mkdir()
    env["XDG_" + kind + "_HOME"] = str(path)
token = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "cua-driver/libei-persistent.token"
if token.is_file():
    dest = root / "config/cua-driver/libei-persistent.token"
    dest.parent.mkdir(parents=True)
    shutil.copy2(token, dest)
env["CUA_PROBE_FIXTURE"] = str(repo / "libs/cua-driver/tests/fixtures/apps/linux/gtk3/main.py")
env["CUA_PROBE_JOURNAL"] = str(root / "fixture-state.json")
socket = str(root / "driver.sock")
summary = {"phase": phase, "private_artifact_dir": str(root), "fixture_observations": {}}
processes = []
logs = []


def call(tool, args, label=None):
    label = label or tool
    args["session"] = "native-followup"
    try:
        result = subprocess.run([str(driver), "call", tool, json.dumps(args), "--socket", socket], env=env, capture_output=True, text=True, timeout=35)
        (root / (label + ".stdout")).write_text(result.stdout)
        (root / (label + ".stderr")).write_text(result.stderr)
        if result.returncode:
            summary[label] = {"exit": result.returncode, "status": "failed; raw details kept private"}
            return None
        if "no evdev keycode mapping for key" in result.stdout:
            summary[label] = {"status": "refused: no evdev keycode mapping", "requested_key": args.get("keys", [None])[-1]}
            return None
        data = json.loads(result.stdout)
        summary[label] = {"exit": 0, "keys": list(data) if isinstance(data, dict) else []}
        return data
    except subprocess.TimeoutExpired:
        summary[label] = {"status": "timeout after 35 seconds"}
        return None
    except ValueError:
        summary[label] = {"status": "non-JSON response; raw details kept private"}
        return None


def journal():
    path = root / "fixture-state.json"
    return json.loads(path.read_text()) if path.exists() else None


try:
    for name, args in [("fixture", ["/usr/bin/python3", str(Path(__file__).with_name("fixture.py"))]), ("daemon", [str(driver), "serve", "--socket", socket, "--dangerously-bypass-approvals", "--no-overlay"])]:
        log = open(root / (name + ".log"), "w")
        logs.append(log)
        processes.append(subprocess.Popen(args, env=env, stdout=log, stderr=log))
    for _ in range(100):
        if Path(socket).exists() and journal():
            break
        time.sleep(0.1)
    time.sleep(1)
    initial = journal()
    summary["fixture_observations"]["initial"] = initial
    if initial is None:
        raise RuntimeError("fixture did not start")
    screen = call("get_screen_size", {})
    if screen:
        summary["screen_metadata"] = {k: v for k, v in screen.items() if k in ("width", "height", "scale", "scale_factor", "coordinate_space", "display_id")}
    shot = root / "desktop-private.png"
    if phase == "scaling":
        capture = call("get_desktop_state", {"screenshot_out_file": str(shot)})
    if shot.exists():
        image = Image.open(shot).convert("RGB")
        summary["desktop_png_dimensions"] = image.size
        # The magenta marker belongs only to the isolated fixture's Increment button.
        pixels = image.load()
        runs = []
        for y in range(image.height):
            xs = [x for x in range(image.width) if pixels[x, y][0] > 230 and pixels[x, y][1] < 25 and pixels[x, y][2] > 230]
            if len(xs) > 30:
                runs.append((y, xs))
        groups = []
        for row in runs:
            if not groups or row[0] > groups[-1][-1][0] + 1:
                groups.append([])
            groups[-1].append(row)
        groups = [g for g in groups if len(g) > 8]
        if len(groups) == 1:
            group = groups[0]
            xs = [x for _, row in group for x in row]
            x = (min(xs) + max(xs)) // 2
            y = (group[0][0] + group[-1][0]) // 2
            summary["screenshot_grounded_point"] = [x, y]
            call("click", {"target": {"kind": "desktop", "display_id": "primary"}, "x": x, "y": y, "delivery_mode": "foreground"})
            time.sleep(0.5)
            summary["fixture_observations"]["after_click"] = journal()
        else:
            summary["click_gap"] = "unique fixture marker was not found"
    windows = call("list_windows", {})
    entries = windows.get("windows", []) if isinstance(windows, dict) else []
    matching = [w for w in entries if w.get("pid") == initial["pid"]]
    summary["fixture_window_count"] = len(matching)
    if matching:
        w = matching[0]
        wid = w.get("window_id", w.get("id", w.get("xid")))
        if wid is not None:
            crop = root / "window-private.png"
            state = call("get_window_state", {"pid": initial["pid"], "window_id": wid, "screenshot_out_file": str(crop)})
            if crop.exists():
                image = Image.open(crop).convert("RGB")
                summary["window_png_dimensions"] = image.size
                summary["window_crop_contains_fixture_marker"] = any(r > 230 and g < 25 and b > 230 for r, g, b in image.getdata())
            if phase.startswith("punctuation"):
                summary["shortcut_attempts"] = []
                for index, keys in enumerate((["Ctrl", ","], ["Ctrl", "/"], ["Ctrl", "Shift", "/"])):
                    call("hotkey", {"pid": initial["pid"], "window_id": wid, "keys": keys, "delivery_mode": "foreground"}, "hotkey_" + str(index))
                    time.sleep(0.3)
                    summary["shortcut_attempts"].append({"requested": keys, "fixture_state": journal()})
                summary["fixture_observations"]["after_shortcuts"] = journal()
    (root / "summary.json").write_text(json.dumps(summary, indent=2))
finally:
    for proc in processes:
        proc.terminate()
    for proc in processes:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    for log in logs:
        log.close()
    print(json.dumps(summary, indent=2))
