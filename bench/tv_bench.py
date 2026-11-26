"""Repeatable launcher benchmark over ADB (the SAME script runs BEFORE and AFTER).

    python tv_bench.py --label before                 (all tests except boot)
    python tv_bench.py --label before --tests boot --allow-reboot --reps 3
    python tv_bench.py --label before --tests home,launch --reps 10

Tests (each repeated --reps times; summary = median, min, max, IQR, stdev):
  home      Settings in front -> HOME intent: `am start -W` TotalTime/WaitTime (system-reported).
            `input keyevent HOME`) and the launcher's on_resume event, plus the system-reported
            TotalTime/WaitTime of `am start -W` with the HOME intent. `input` itself costs a few
            hundred ms of JVM start on old TVs: measured separately as input_overhead_ms.
  launcher_cold  force-stop the launcher, `am start -W` HOME: cold start of the launcher itself.
  launch    per app: cold (force-stop first) and warm, `am start -W` TotalTime/WaitTime.
  scroll    `dumpsys gfxinfo <launcher> reset`, a fixed D-pad path over the home rows, then
            frames rendered, janky %, 50/90/95/99th percentile frame time.
  clean_idle  reboot, wait calm, 120 s on home with no app opened, then the idle sample (fair across stages)
  idle      at home after --settle seconds: CPU busy % from /proc/stat over 30 s, MemAvailable,
            dumpsys meminfo Free/Used RAM, launcher PSS, process count.
  boot      (only with --allow-reboot) reboot; boot_progress_* events, launcher first frame
            (uptime ms) and "settled" = first time 3 x 2 s CPU samples are all under 40% busy.

Changes on the TV: key presses, force-stop of apps (same as closing them), `logcat -c` (clears the
log buffer), gfxinfo reset, and a reboot only for the boot test. Nothing is installed or disabled.
Output: results/<label>_<timestamp>/ (meta.json, runs.csv, runs.json, summary.json, raw/).
"""
import argparse
import csv
import datetime as dt
import json
import re
import statistics as st
import time
from pathlib import Path

import adbtool as A

DEFAULT_APPS = [  # used only if installed; override with --apps
    "com.android.tv.settings",
    "com.google.android.youtube.tv",
    "com.netflix.ninja",
    "com.amazon.amazonvideo.livingroom",
    "com.android.vending",
]
# D-pad path over the home rows: (keycode, count). 22 right, 21 left, 20 down, 19 up.
SCROLL_PATH = [(22, 6), (20, 1), (21, 6), (19, 1)] * 2  # 28 presses; each `input` call takes ~1.6 s on this TV
KEY_GAP = 0.35  # seconds between D-pad presses (about a person browsing quickly)

ROWS = []
RAW = None


def row(test, item, rep, metric, value, unit):
    ROWS.append({"test": test, "item": item, "rep": rep, "metric": metric, "value": value, "unit": unit})


def save_raw(name, text):
    (RAW / f"{name}.txt").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- device helpers
def home_component():
    out = A.sh("cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME")
    lines = [l.strip() for l in out.splitlines() if "/" in l]
    return lines[-1] if lines else ""


def app_component(pkg):
    """Returns am-start arguments for the app (component, or an intent for Settings)."""
    if pkg in ("com.android.tv.settings", "com.android.settings"):
        return "-a android.settings.SETTINGS"
    for cat in ("android.intent.category.LEANBACK_LAUNCHER", "android.intent.category.LAUNCHER"):
        out = A.sh(f"cmd package resolve-activity --brief -a android.intent.action.MAIN -c {cat} {pkg}")
        lines = [l.strip() for l in out.splitlines() if "/" in l]
        if lines:
            return "-n " + lines[-1]
    return ""


def installed(pkg):
    return f"package:{pkg}" in A.sh(f"pm list packages {pkg}", quiet=True).split()


def wake():
    if "mWakefulness=Awake" not in A.sh("dumpsys power | grep mWakefulness", quiet=True):
        A.sh("input keyevent KEYCODE_WAKEUP")
        time.sleep(3)


def am_start(args):
    try:
        out = A.sh(f"am start -W {args}", timeout=60)
    except A.subprocess.TimeoutExpired:
        # the app never reported its first frame (e.g. a sign-in prompt on top): record it, clean up, go on
        A.note(f"am start -W {args}: no answer in 60 s (timeout)")
        A.sh("input keyevent KEYCODE_BACK")
        time.sleep(2)
        return {"timeout": 1, "LaunchState": "TIMEOUT"}, "TIMEOUT after 60 s"
    vals = {k: int(v) for k, v in re.findall(r"^(ThisTime|TotalTime|WaitTime): (\d+)", out, re.M)}
    m = re.search(r"LaunchState: (\w+)", out)
    vals["LaunchState"] = m.group(1) if m else ""
    return vals, out


def go_home(settle=2.0):
    A.sh("input keyevent KEYCODE_HOME")
    time.sleep(settle)


def uptime_ms():
    return float(A.sh("cat /proc/uptime", quiet=True).split()[0]) * 1000


def cpu_sample():
    f = [int(x) for x in A.sh("head -1 /proc/stat", quiet=True).split()[1:]]
    idle = f[3] + (f[4] if len(f) > 4 else 0)
    return sum(f), idle


def cpu_busy(seconds):
    t1, i1 = cpu_sample()
    time.sleep(seconds)
    t2, i2 = cpu_sample()
    return 100.0 * (1 - (i2 - i1) / max(1, t2 - t1))


LOGFMT = None


def logcat_dump(buffers="main,events"):
    """Dump logcat with a monotonic (uptime-like) clock when the TV supports it, else epoch."""
    global LOGFMT
    if LOGFMT is None:
        LOGFMT = "monotonic" if "invalid" not in A.sh("logcat -d -t 1 -v monotonic", quiet=True).lower() else "epoch"
    return A.sh(f"logcat -d -b {buffers} -v {LOGFMT}", timeout=120)


def log_ts(line):
    m = re.match(r"\s*(\d+\.\d+)", line)
    return float(m.group(1)) * 1000 if m else None


# ---------------------------------------------------------------- tests
def t_input_overhead(reps):
    for r in range(reps):
        t0 = time.perf_counter()
        A.sh("input keyevent 0")  # KEYCODE_UNKNOWN: does nothing, measures the `input` tool cost
        row("input_overhead", "input keyevent", r, "roundtrip_ms", round((time.perf_counter() - t0) * 1000), "ms")


def t_home(reps, launcher_pkg):
    """System-reported HOME transition (Settings in front -> HOME intent), `am start -W`.
    A key-press timing via `input keyevent` was dropped: on this TV the `input` tool alone takes ~1.6 s
    to start (see input_overhead), so it would measure the tool, not the launcher."""
    for r in range(reps):
        am_start("-a android.settings.SETTINGS")
        time.sleep(3)
        v, out = am_start("-a android.intent.action.MAIN -c android.intent.category.HOME")
        save_raw(f"home_rep{r}_amstart", out)
        for k in ("TotalTime", "WaitTime"):
            if k in v:
                row("home", "HOME intent", r, k, v[k], "ms")
        time.sleep(2)


def launcher_pkg_short(comp):
    # event log prints the activity as pkg/.Activity or pkg/full.Name; matching on the package is enough
    return comp.split("/")[0]


def t_launcher_cold(reps, comp):
    pkg = comp.split("/")[0]
    for r in range(reps):
        A.sh(f"am force-stop {pkg}")
        time.sleep(2)
        v, out = am_start("-a android.intent.action.MAIN -c android.intent.category.HOME")
        save_raw(f"launcher_cold_rep{r}", out)
        for k in ("TotalTime", "WaitTime"):
            if k in v:
                row("launcher_cold", pkg, r, k, v[k], "ms")
        row("launcher_cold", pkg, r, "LaunchState", v.get("LaunchState", ""), "")
        time.sleep(5)


def t_launch(reps, apps):
    for pkg in apps:
        comp = app_component(pkg)
        if not comp:
            A.note(f"launch: no launcher activity for {pkg}, skipped")
            continue
        for mode in ("cold", "warm"):
            for r in range(reps):
                go_home()
                if mode == "cold":
                    A.sh(f"am force-stop {pkg}")
                    time.sleep(2)
                v, out = am_start(comp)
                save_raw(f"launch_{pkg}_{mode}_rep{r}", out)
                for k in ("TotalTime", "WaitTime"):
                    if k in v:
                        row(f"launch_{mode}", pkg, r, k, v[k], "ms")
                if v.get("timeout"):
                    row(f"launch_{mode}", pkg, r, "timeout_60s", 1, "count")
                time.sleep(5)  # let the app finish its first frames before going home
        A.sh(f"am force-stop {pkg}")
    go_home()


GFX = {
    "frames": r"Total frames rendered: (\d+)",
    "janky": r"Janky frames: (\d+)",
    "janky_pct": r"Janky frames: \d+ \(([\d.]+)%\)",
    "p50_ms": r"50th percentile: (\d+)ms",
    "p90_ms": r"90th percentile: (\d+)ms",
    "p95_ms": r"95th percentile: (\d+)ms",
    "p99_ms": r"99th percentile: (\d+)ms",
    "missed_vsync": r"Number Missed Vsync: (\d+)",
    "slow_ui_thread": r"Number Slow UI thread: (\d+)",
}


def t_scroll(reps, comp):
    pkg = comp.split("/")[0]
    script = "; ".join(f"input keyevent {k}; sleep {KEY_GAP}" for k, n in SCROLL_PATH for _ in range(n))
    for r in range(reps):
        go_home(3)
        A.sh(f"dumpsys gfxinfo {pkg} reset")
        t0 = time.perf_counter()
        A.sh(script, timeout=600)
        row("scroll", pkg, r, "path_seconds", round(time.perf_counter() - t0, 1), "s")
        out = A.sh(f"dumpsys gfxinfo {pkg}")
        save_raw(f"scroll_rep{r}_gfxinfo", out)
        save_raw(f"scroll_rep{r}_framestats", A.sh(f"dumpsys gfxinfo {pkg} framestats"))
        for name, rx in GFX.items():
            m = re.search(rx, out)
            if m:
                row("scroll", pkg, r, name, float(m.group(1)), "%" if name.endswith("pct") else
                    "ms" if name.endswith("_ms") else "count")
    go_home()


def measure_idle(test, r, pkg):
    """one idle sample at home: CPU busy over 30 s, /proc/meminfo, dumpsys meminfo (raw saved), launcher PSS, processes"""
    row(test, "system", r, "cpu_busy_pct_30s", round(cpu_busy(30), 1), "%")
    mi = dict((k, int(v)) for k, v in re.findall(r"^(\w+):\s+(\d+) kB", A.sh("cat /proc/meminfo"), re.M))
    for k in ("MemAvailable", "MemFree", "Cached"):
        if k in mi:
            row(test, "system", r, f"{k}_mb", round(mi[k] / 1024), "MB")
    dm = A.sh("dumpsys meminfo")
    save_raw(f"{test}_rep{r}_meminfo", dm)
    for label, key in (("Free RAM", "free_ram_mb"), ("Used RAM", "used_ram_mb"), ("Lost RAM", "lost_ram_mb")):
        m = re.search(label + r":\s+([\d,]+)K", dm)
        if m:
            row(test, "system", r, key, round(int(m.group(1).replace(",", "")) / 1024), "MB")
    # Android app processes (package-style names; HALs and native daemons excluded) and the memory they hold
    apps = [(int(k.replace(",", "")), n) for k, n in re.findall(r"^\s+([\d,]+)K: (\S+) \(pid", dm.split("Total PSS by OOM")[0], re.M)
            if "." in n and "@" not in n and not n.startswith(("android.hardware", "vendor."))]
    row(test, "system", r, "app_processes", len(apps), "count")
    row(test, "system", r, "app_pss_mb", round(sum(k for k, _ in apps) / 1024), "MB")
    lm = A.sh(f"dumpsys meminfo {pkg}")
    m = re.search(r"TOTAL(?: PSS)?:?\s+(\d+)", lm)
    if m:
        row(test, pkg, r, "launcher_pss_mb", round(int(m.group(1)) / 1024, 1), "MB")
    procs = len([l for l in A.sh("ps -A 2>/dev/null || ps", quiet=True).splitlines()[1:] if l.strip()])
    row(test, "system", r, "process_count", procs, "count")
    save_raw(f"{test}_rep{r}_cpuinfo", A.sh("dumpsys cpuinfo"))
    save_raw(f"{test}_rep{r}_top", A.sh("top -b -n 1 -m 25 2>/dev/null || top -n 1 -m 25"))


def t_idle(reps, comp, settle):
    pkg = comp.split("/")[0]
    go_home()
    A.note(f"idle: settling {settle} s at home")
    time.sleep(settle)
    for r in range(reps):
        measure_idle("idle", r, pkg)
        time.sleep(10)


def t_clean_idle(reps, comp, settle):
    """The TV as a viewer finds it: reboot, wait until the CPU calms down, sit on home for `settle` s with no app
    opened, then one idle sample. Fair across stages (no apps left over from the launch tests)."""
    pkg = comp.split("/")[0]
    for r in range(reps):
        A.note(f"clean_idle rep {r}: rebooting")
        A.adb("reboot", timeout=60)
        time.sleep(20)
        if not reconnect():
            A.note("clean_idle: TV did not come back over ADB within 10 min")
            continue
        under, t_end = 0, time.time() + 300
        while time.time() < t_end and under < 3:
            under = under + 1 if cpu_busy(2) < 40 else 0
        A.note(f"clean_idle rep {r}: calm at uptime {uptime_ms()} ms, settling {settle} s at home")
        time.sleep(settle)
        measure_idle("clean_idle", r, pkg)


def reconnect(timeout=600):
    s = A.serial()
    t_end = time.time() + timeout
    while time.time() < t_end:
        if ":" in s:
            A.subprocess.run([A.ADB, "connect", s], capture_output=True, timeout=30)
        p = A.subprocess.run([A.ADB, "-s", s, "shell", "getprop sys.boot_completed"],
                             capture_output=True, text=True, timeout=30)
        if p.stdout.strip() == "1":
            return True
        time.sleep(2)
    return False


def t_boot(reps, comp):
    pkg = comp.split("/")[0]
    for r in range(reps):
        A.note(f"boot rep {r}: rebooting")
        A.adb("reboot", timeout=60)
        time.sleep(20)
        if not reconnect():
            A.note("boot: TV did not come back over ADB within 10 min")
            continue
        # settled: first moment with 3 consecutive 2-s samples under 40 % busy
        settled = None
        t_end = time.time() + 300
        under = 0
        while time.time() < t_end:
            b = cpu_busy(2)
            under = under + 1 if b < 40 else 0
            if under == 3:
                settled = uptime_ms()
                break
        ev = A.sh("logcat -d -b events", timeout=120)
        save_raw(f"boot_rep{r}_events", ev)
        for name in ("boot_progress_start", "boot_progress_system_run", "boot_progress_ams_ready",
                     "boot_progress_enable_screen"):
            m = re.search(name + r": (\d+)", ev)
            if m:
                row("boot", "uptime", r, name + "_ms", int(m.group(1)), "ms")
        # launcher first frame: am/wm_activity_launch_time, timestamp converted to uptime
        # (monotonic log clock = time since boot; an epoch clock before NTP sync is unusable here)
        log = logcat_dump("events")
        save_raw(f"boot_rep{r}_events_mono", log)
        if LOGFMT == "monotonic":
            hit = next((l for l in log.splitlines()
                        if re.search(r"(wm|am)_activity_launch_time", l) and pkg in l), None)
            if hit:
                row("boot", "uptime", r, "launcher_first_frame_logged_ms", round(log_ts(hit)), "ms")
        if settled:
            row("boot", "uptime", r, "settled_cpu_under_40pct_ms", round(settled), "ms")
        time.sleep(30)


def wait_calm(max_load=2.0, limit_s=1200):
    """Wait until the 1-minute load average is under max_load (max limit_s). Returns (load, waited_s)."""
    t0 = time.time()
    while True:
        # /proc/loadavg is blocked by SELinux on this TV; `uptime` prints the same numbers
        out = A.sh("uptime", quiet=True)
        m = re.search(r"load average:\s*([\d.]+)", out)
        if not m:  # empty answer while ADB reconnects: try again
            time.sleep(5)
            continue
        load = float(m.group(1))
        if load < max_load or time.time() - t0 > limit_s:
            return load, round(time.time() - t0)
        time.sleep(15)


# ---------------------------------------------------------------- summary
def summarise():
    groups = {}
    for x in ROWS:
        if isinstance(x["value"], (int, float)):
            groups.setdefault((x["test"], x["item"], x["metric"], x["unit"]), []).append(x["value"])
    out = []
    for (test, item, metric, unit), v in groups.items():
        v = sorted(v)
        q = st.quantiles(v, n=4) if len(v) >= 2 else [v[0], v[0], v[0]]
        out.append({"test": test, "item": item, "metric": metric, "unit": unit, "n": len(v),
                    "median": st.median(v), "min": v[0], "max": v[-1], "iqr": round(q[2] - q[0], 2),
                    "stdev": round(st.stdev(v), 2) if len(v) > 1 else 0})
    return out


def main():
    global RAW
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="before / after / anything")
    ap.add_argument("--tests", default="input_overhead,home,launcher_cold,launch,scroll,idle")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--apps", default="")
    ap.add_argument("--settle", type=int, default=60)
    ap.add_argument("--allow-reboot", action="store_true")
    ap.add_argument("--into", default="", help="continue an interrupted run: append to this results folder")
    a = ap.parse_args()
    tests = a.tests.split(",")
    if "boot" in tests and not a.allow_reboot:
        raise SystemExit("boot test reboots the TV: add --allow-reboot")

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    res = Path(a.into).resolve() if a.into else A.ROOT / "results" / f"{a.label}_{stamp}"
    RAW = res / "raw"
    RAW.mkdir(parents=True, exist_ok=True)
    old_meta = {}
    if a.into:
        ROWS.extend(json.loads((res / "runs.json").read_text(encoding="utf-8")))
        old_meta = json.loads((res / "meta.json").read_text(encoding="utf-8"))
    wake()
    comp = home_component()
    pkg = comp.split("/")[0]
    ver = re.search(r"versionName=(\S+)", A.sh(f"dumpsys package {pkg} | grep versionName"))
    apps = [p for p in (a.apps.split(",") if a.apps else DEFAULT_APPS) if p and installed(p)]
    meta = {"label": a.label, "start": A.now_iso(), "serial": A.serial(), "args": vars(a),
            "fingerprint": A.getprop("ro.build.fingerprint"), "model": A.getprop("ro.product.model"),
            "home_component": comp, "launcher_version": ver.group(1) if ver else "",
            "apps": apps, "uptime_s_at_start": round(uptime_ms() / 1000),
            "animation_scales": A.sh("settings get global window_animation_scale; settings get global "
                                     "transition_animation_scale; settings get global animator_duration_scale",
                                     quiet=True).split(),
            "scroll_path": SCROLL_PATH, "key_gap_s": KEY_GAP}
    if old_meta:
        meta = {**old_meta, "continued": old_meta.get("continued", []) + [{"start": meta["start"], "args": vars(a)}]}
    A.note(f"bench {a.label} start: tests={tests} reps={a.reps} launcher={comp}")

    for t in tests:
        if t != "boot":
            load, waited = wait_calm()
            meta.setdefault("calm", []).append({"test": t, "load1": load, "waited_s": waited, "uptime_s": round(uptime_ms() / 1000)})
            A.note(f"calm before {t}: load {load} after {waited} s")
        A.note(f"bench test {t}")
        if t == "input_overhead":
            t_input_overhead(a.reps)
        elif t == "home":
            t_home(a.reps, comp)
        elif t == "launcher_cold":
            t_launcher_cold(a.reps, comp)
        elif t == "launch":
            t_launch(a.reps, apps)
        elif t == "scroll":
            t_scroll(a.reps, comp)
        elif t == "idle":
            t_idle(a.reps, comp, a.settle)
        elif t == "clean_idle":
            if not a.allow_reboot:
                raise SystemExit("clean_idle reboots the TV: add --allow-reboot")
            t_clean_idle(a.reps, comp, max(a.settle, 120))
        elif t == "boot":
            t_boot(a.reps, comp)
        else:
            raise SystemExit(f"unknown test {t}")
        # write after every test so a cut run still leaves data
        meta["end"] = A.now_iso()
        (res / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        (res / "runs.json").write_text(json.dumps(ROWS, indent=1), encoding="utf-8")
        with open(res / "runs.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["test", "item", "rep", "metric", "value", "unit"])
            w.writeheader()
            w.writerows(ROWS)
        (res / "summary.json").write_text(json.dumps(summarise(), indent=2), encoding="utf-8")

    A.note(f"bench {a.label} done -> {res.relative_to(A.ROOT)}")
    for s in summarise():
        print(f"{s['test']:15} {s['item'][:32]:32} {s['metric']:28} median {s['median']:>8} {s['unit']:5} "
              f"(min {s['min']}, max {s['max']}, n {s['n']})")


if __name__ == "__main__":
    main()
