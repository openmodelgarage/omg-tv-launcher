"""Small ADB wrapper shared by every script in this project.

Every adb call is appended to log/commands.jsonl (time, command, duration, exit code,
first 300 chars of output) so the process log for the video is written automatically.

Device selection: env ADB_SERIAL (e.g. <tv-ip>:5555), else the only attached device.
adb: env ADB, else "adb" on PATH.
"""
import datetime as _dt
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "log"
CAP_DIR = ROOT / "captures"

_DEFAULT_ADB = ""
ADB = os.environ.get("ADB") or (_DEFAULT_ADB if Path(_DEFAULT_ADB).exists() else shutil.which("adb") or "adb")


def now_iso():
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _log(entry):
    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_DIR / "commands.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def serial():
    s = os.environ.get("ADB_SERIAL")
    if s:
        return s
    out = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=30).stdout
    devs = [l.split("\t")[0] for l in out.splitlines()[1:] if l.strip().endswith("device")]
    if len(devs) != 1:
        raise SystemExit(f"Need exactly one device (found {devs}); set ADB_SERIAL.")
    return devs[0]


def adb(*args, timeout=120, check=False, quiet=False, binary=False):
    """Run `adb -s <serial> <args...>`; returns stdout (str, or bytes if binary)."""
    cmd = [ADB, "-s", serial(), *args]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    dt = time.perf_counter() - t0
    out = p.stdout if binary else p.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    if not quiet:
        _log({"t": now_iso(), "cmd": "adb " + " ".join(args), "sec": round(dt, 3), "rc": p.returncode,
              "out": "<binary>" if binary else out[:300]})
    if check and p.returncode != 0:
        raise RuntimeError(f"adb {' '.join(args)} failed rc={p.returncode}: {p.stderr.decode(errors='replace')}")
    return out


def sh(command, **kw):
    """Run one shell command string on the TV."""
    return adb("shell", command, **kw)


def getprop(name):
    return sh(f"getprop {name}", quiet=True).strip()


def screencap(name):
    """Save a PNG screenshot of the TV to captures/<timestamp>_<name>.png (binary-safe)."""
    CAP_DIR.mkdir(exist_ok=True)
    path = CAP_DIR / f"{_dt.datetime.now():%Y%m%d_%H%M%S}_{name}.png"
    data = adb("exec-out", "screencap", "-p", binary=True)
    path.write_bytes(data)
    _log({"t": now_iso(), "capture": str(path.relative_to(ROOT)), "bytes": len(data)})
    return path


def screenrecord(name, seconds=10, bitrate="8M"):
    """Record the TV screen on the device, then pull it to captures/. Blocks for `seconds`.
    Never run during a timed benchmark: screenrecord loads the CPU/encoder."""
    CAP_DIR.mkdir(exist_ok=True)
    remote = f"/sdcard/omg_{name}.mp4"
    sh(f"screenrecord --time-limit {int(seconds)} --bit-rate {bitrate.rstrip('M')}000000 {remote}",
       timeout=seconds + 60)
    path = CAP_DIR / f"{_dt.datetime.now():%Y%m%d_%H%M%S}_{name}.mp4"
    adb("pull", remote, str(path), timeout=300)
    sh(f"rm -f {remote}")
    return path


def note(text):
    """Free-text entry in the process log (for the narration script later)."""
    _log({"t": now_iso(), "note": text})
