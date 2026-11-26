"""Background load per stage, parsed from the raw `dumpsys meminfo` that tv_bench.py saved in every idle run.

    py -3.13 bg_procs.py results/before_* results/debloat_* results/after_*

The video's objective (director, 2026-11-18) is a lighter TV, so this counts what runs at idle on the home screen:
- app_processes: Android app processes (Java, package-style names; native daemons and HAL services excluded)
- app_pss_mb: memory those app processes hold (PSS), and PSS by Android's own OOM groups
- which app processes disappeared / appeared between the first and the last stage (present in a majority of reps)
Writes bg_procs.md (for the script) and bg_procs.json (for overlays). Nothing is measured again here.
"""
import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROC = re.compile(r"^\s+([\d,]+)K: (\S+) \(pid \d+")
OOM = re.compile(r"^\s+([\d,]+)K: ([A-Z][A-Za-z ]+)$")
GROUPS = ["Native", "System", "Persistent", "Persistent Service", "Foreground", "Visible", "Perceptible",
          "A Services", "Home", "B Services", "Cached"]


def is_app(name):
    # app processes are package names (com.x.y, android.process.x, com.x:service); HALs are android.hardware.*@x
    return "." in name and "@" not in name and not name.startswith("android.hardware") and not name.startswith("vendor.")


def parse(path):
    txt = path.read_text(encoding="utf-8", errors="replace")
    a = txt.index("Total PSS by process:")
    b = txt.index("Total PSS by OOM adjustment:")
    c = txt.index("Total PSS by category:")
    procs = {}
    for line in txt[a:b].splitlines():
        m = PROC.match(line)
        if m:
            procs[m.group(2)] = int(m.group(1).replace(",", "")) / 1024
    groups = {}
    for line in txt[b:c].splitlines():
        m = OOM.match(line)
        if m and m.group(2).strip() in GROUPS:
            groups[m.group(2).strip()] = int(m.group(1).replace(",", "")) / 1024
    return procs, groups


def stage(d):
    d = Path(d)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    reps = [parse(p) for p in sorted((d / "raw").glob("idle_rep*_meminfo.txt"))]
    if not reps:
        raise SystemExit(f"no idle meminfo in {d}")
    apps = [{k: v for k, v in p.items() if is_app(k)} for p, _ in reps]
    n = len(reps)
    seen = {}
    for a in apps:
        for k, v in a.items():
            seen.setdefault(k, []).append(v)
    common = {k: st.median(v) for k, v in seen.items() if len(v) > n / 2}   # present in most reps
    med = lambda xs: round(st.median(xs), 1)
    return {"label": meta["label"], "dir": str(d), "reps": n,
            "app_processes": med([len(a) for a in apps]),
            "app_processes_range": [min(len(a) for a in apps), max(len(a) for a in apps)],
            "app_pss_mb": med([sum(a.values()) for a in apps]),
            "app_pss_range": [round(min(sum(a.values()) for a in apps), 1), round(max(sum(a.values()) for a in apps), 1)],
            "groups_mb": {g: med([gr.get(g, 0) for _, gr in reps]) for g in GROUPS},
            "apps": dict(sorted(((k, round(v, 1)) for k, v in common.items()), key=lambda kv: -kv[1]))}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    stages = [stage(d) for d in sys.argv[1:]]
    first, last = stages[0], stages[-1]
    gone = {k: v for k, v in first["apps"].items() if k not in last["apps"]}
    new = {k: v for k, v in last["apps"].items() if k not in first["apps"]}
    out = {"stages": stages, "gone_first_to_last": gone, "new_first_to_last": new,
           "note": "idle on the home screen, median of the idle reps; PSS in MB (1024 KB)"}
    (ROOT / "bg_procs.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    L = lambda s: s["label"]
    md = ["# Background load at idle (from the raw dumpsys meminfo of every idle run)", "",
          "Median of the idle reps, [min–max]. App processes = Android app processes (package names); native daemons and "
          "hardware services are left out (they don't change).", "",
          "| | " + " | ".join(L(s) for s in stages) + " |", "|---|" + "---|" * len(stages),
          "| App processes running | " + " | ".join(f"{s['app_processes']:.0f} [{s['app_processes_range'][0]}–{s['app_processes_range'][1]}]" for s in stages) + " |",
          "| Memory held by app processes (MB) | " + " | ".join(f"{s['app_pss_mb']:.0f} [{s['app_pss_range'][0]:.0f}–{s['app_pss_range'][1]:.0f}]" for s in stages) + " |"]
    for g in GROUPS:
        md.append(f"| &nbsp;&nbsp;{g} (MB) | " + " | ".join(f"{s['groups_mb'][g]:.0f}" for s in stages) + " |")
    md += ["", f"## Gone between {L(first)} and {L(last)} ({len(gone)} processes, {sum(gone.values()):.0f} MB in {L(first)})", ""]
    md += [f"- {k}: {v:.1f} MB" for k, v in gone.items()]
    md += ["", f"## New in {L(last)} ({len(new)})", ""] + [f"- {k}: {v:.1f} MB" for k, v in new.items()]
    md += ["", f"## Biggest app processes still running in {L(last)}", ""]
    md += [f"- {k}: {v:.1f} MB" for k, v in list(last["apps"].items())[:20]]
    (ROOT / "bg_procs.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
