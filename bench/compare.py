"""Compare benchmark runs (stages) metric by metric: medians, spread, change vs the first stage.

    py -3.13 compare.py results/before_* results/debloat_* results/after_*

Writes COMPARE.md (table for the script/QA) and compare.csv / compare.json (overlay data).
Only metrics measured in every stage are compared; nothing is typed by hand.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOWER_IS_BETTER = {"TotalTime", "WaitTime", "janky", "janky_pct", "p50_ms", "p90_ms", "p95_ms", "p99_ms",
                   "missed_vsync", "slow_ui_thread", "cpu_busy_pct_30s", "used_ram_mb", "lost_ram_mb",
                   "launcher_pss_mb", "process_count", "roundtrip_ms", "path_seconds",
                   "boot_progress_enable_screen_ms", "launcher_first_frame_logged_ms",
                   "settled_cpu_under_40pct_ms", "boot_progress_start_ms", "boot_progress_system_run_ms",
                   "boot_progress_ams_ready_ms"}
HIGHER_IS_BETTER = {"MemAvailable_mb", "MemFree_mb", "free_ram_mb", "Cached_mb", "frames"}


def load(d):
    d = Path(d)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    summ = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    home_pkg = meta["home_component"].split("/")[0]
    # the launcher's own rows (cold start, scroll, PSS) carry its package name: stock and ours differ,
    # so they are matched as "(launcher)"
    return meta, {(s["test"], "(launcher)" if s["item"] == home_pkg else s["item"], s["metric"]): s for s in summ}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    dirs = [Path(p) for p in sys.argv[1:]]
    if len(dirs) < 2:
        raise SystemExit("give at least two result folders, first = baseline")
    runs = [load(d) for d in dirs]
    labels = [m["label"] for m, _ in runs]
    keys = [k for k in runs[0][1] if all(k in s for _, s in runs)]
    rows = []
    for k in keys:
        test, item, metric = k
        base = runs[0][1][k]
        r = {"test": test, "item": item, "metric": metric, "unit": base["unit"]}
        for lab, (_, s) in zip(labels, runs):
            x = s[k]
            r[f"{lab}_median"] = x["median"]
            r[f"{lab}_min"], r[f"{lab}_max"], r[f"{lab}_n"] = x["min"], x["max"], x["n"]
        last = runs[-1][1][k]["median"]
        r["change_pct"] = round(100 * (last - base["median"]) / base["median"], 1) if base["median"] else None
        better = (metric in LOWER_IS_BETTER and last < base["median"]) or \
                 (metric in HIGHER_IS_BETTER and last > base["median"])
        worse = (metric in LOWER_IS_BETTER and last > base["median"]) or \
                (metric in HIGHER_IS_BETTER and last < base["median"])
        r["verdict"] = "better" if better else "worse" if worse else "same/neutral"
        # overlap of ranges = the difference may be noise
        b, l = runs[0][1][k], runs[-1][1][k]
        r["ranges_overlap"] = not (l["max"] < b["min"] or l["min"] > b["max"])
        rows.append(r)

    out_json = {"stages": [{"label": m["label"], "dir": str(d), "home": m["home_component"],
                            "start": m["start"]} for (m, _), d in zip(runs, dirs)], "rows": rows}
    (ROOT / "compare.json").write_text(json.dumps(out_json, indent=2), encoding="utf-8")
    with open(ROOT / "compare.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    md = ["# Before / after comparison", "", "Stages: " + " → ".join(
        f"**{m['label']}** ({m['start'][:16]}, home {m['home_component'].split('/')[0]})" for m, _ in runs), "",
        "Median of the repetitions; [min–max] in brackets. 'overlap' = the first and last ranges overlap, "
        "so the difference may be noise. Lower is better for times, jank, CPU and used RAM.", "",
        "| Test | Item | Metric | " + " | ".join(labels) + " | Change | Verdict |",
        "|---|---|---|" + "---|" * len(labels) + "---|---|"]
    for r in rows:
        cells = [f"{r[f'{l}_median']} [{r[f'{l}_min']}–{r[f'{l}_max']}]" for l in labels]
        ch = f"{r['change_pct']:+}%" if r["change_pct"] is not None else "–"
        md.append(f"| {r['test']} | {r['item']} | {r['metric']} ({r['unit']}) | " + " | ".join(cells) +
                  f" | {ch} | {r['verdict']}{' (overlap)' if r['ranges_overlap'] else ''} |")
    (ROOT / "COMPARE.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
