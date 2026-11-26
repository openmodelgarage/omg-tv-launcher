"""Before / debloat / after charts, read from compare.json (written by compare.py). No numbers typed by hand.

    py -3.13 compare.py results/before_* results/debloat_* results/after_*
    py -3.13 charts.py

Writes charts/<metric>.svg (one panel each, 1600x900, dark, for overlays / Resolve) and charts/charts.html (all panels,
hover shows median and [min-max]). Colour = emphasis: the last stage (ours) is the accent red, earlier stages are greys
(context). Every bar carries its value as text, so identity never rests on colour alone; COMPARE.md is the table view.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "charts"

BG, TEXT, TEXT2, GRID = "#141416", "#F5F5F7", "#8E8E93", "#2A2A2C"
STAGE_COL = ["#8E8E93", "#5C5C61", "#FF453A"]   # before, debloat (context greys), after (accent)
FONT = "'Space Grotesk', 'Segoe UI', sans-serif"

# (file, title, test, item, metric, scale, unit shown, note)
# Order = the video's objective (director, 2026-11-18): a lighter TV (background processes, memory, idle CPU, no lag) and a fast
# home screen first; app launch times are a side note (last, and optional in the cut).
PANELS = [
    ("free_memory", "Memory available at idle", "idle", "system", "MemAvailable_mb", 1, "MB", "higher is better"),
    ("used_memory", "Memory in use at idle", "idle", "system", "used_ram_mb", 1, "MB", "lower is better"),
    ("idle_cpu", "CPU busy at idle on home", "idle", "system", "cpu_busy_pct_30s", 1, "%", "lower is better"),
    ("home_memory", "Home screen memory (PSS)", "idle", "(launcher)", "launcher_pss_mb", 1, "MB", "lower is better"),
    ("scroll_jank", "Janky frames while moving around home", "scroll", "(launcher)", "janky_pct", 1, "%", "lower is better"),
    ("scroll_p99", "Slowest 1 % of frames (p99)", "scroll", "(launcher)", "p99_ms", 1, "ms", "lower is better"),
    ("home_button", "Home button to home screen", "home", "HOME intent", "TotalTime", 1, "ms", "lower is better"),
    ("home_cold_start", "Home screen, cold start", "launcher_cold", "(launcher)", "TotalTime", 0.001, "s", "lower is better"),
    ("boot_home_frame", "Power-on to first home frame", "boot", "uptime", "launcher_first_frame_logged_ms", 0.001, "s", "lower is better"),
    ("boot_settled", "Power-on until the TV calms down (CPU < 40 %)", "boot", "uptime", "settled_cpu_under_40pct_ms", 0.001, "s", "lower is better"),
]
APP_NAMES = {"com.android.tv.settings": "Settings", "com.google.android.youtube.tv": "YouTube",
             "com.amazon.amazonvideo.livingroom": "Prime Video", "in.startv.hotstar": "JioHotstar"}


def fmt(v, unit):
    if unit == "s":
        return f"{v:.1f} s"
    if unit in ("%",):
        return f"{v:.1f} %"
    return f"{v:,.0f} {unit}".strip()


def nice_max(v):
    """round axis end and tick step (1, 2, 2.5, 5 x 10^k), about 4-5 ticks"""
    import math
    raw = v / 4
    k = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    step = next(m * k for m in (1, 2, 2.5, 5, 10) if m * k >= raw)
    return step * math.ceil(v / step), step


def panel_svg(title, note, groups, labels, unit, w=1600, h=900):
    """groups = [(group label, [(median, min, max) per stage])]; horizontal bars, one value axis from 0."""
    left, right, top = 300, 260, 170
    # scale to the medians (an outlier run must not shrink every bar); a whisker past the edge is clipped and labelled
    vmax, step = nice_max(max(r[0] for _, rs in groups for r in rs) * 1.35)
    plot_w = w - left - right
    gh = (h - top - 80) / len(groups)
    bar_h = min(110 if len(groups) == 1 else 56, (gh - 30) / len(labels) - 2)
    if len(groups) == 1:   # centre a lone group vertically
        top += (gh - len(labels) * (bar_h + 2)) / 2 - 20
    X = lambda v: left + plot_w * min(v, vmax) / vmax
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="{FONT}">',
         f'<rect width="{w}" height="{h}" fill="{BG}"/>',
         f'<text x="{left}" y="80" fill="{TEXT}" font-size="44" font-weight="500">{html.escape(title)}</text>',
         f'<text x="{left}" y="122" fill="{TEXT2}" font-size="24">Median of 5 runs · bar end = median · thin line = min–max · {note}</text>']
    t = 0.0
    while t <= vmax + 1e-9:   # recessive grid at round values
        x = X(t)
        s.append(f'<line x1="{x:.0f}" y1="150" x2="{x:.0f}" y2="{h - 70}" stroke="{GRID}" stroke-width="1"/>')
        s.append(f'<text x="{x:.0f}" y="{h - 40}" fill="{TEXT2}" font-size="20" text-anchor="middle">{fmt(t, unit)}</text>')
        t += step
    for gi, (glabel, rs) in enumerate(groups):
        y0 = top + gi * gh
        if len(groups) > 1:
            s.append(f'<text x="{left - 24}" y="{y0 + (gh - 30) / 2 + 8:.0f}" fill="{TEXT}" font-size="28" text-anchor="end">{html.escape(glabel)}</text>')
        for si, (med, lo, hi) in enumerate(rs):
            y = y0 + si * (bar_h + 2)   # 2px surface gap between adjacent bars
            bw = max(2, X(med) - left)
            r = min(4, bw / 2)
            tip = f"{labels[si]}: {fmt(med, unit)} (median), range {fmt(lo, unit)}–{fmt(hi, unit)}"
            clipped = hi > vmax
            lx = (X(med) if clipped else max(X(med), X(hi))) + 14
            lab = fmt(med, unit)
            s.append(f'<g><title>{html.escape(tip)}</title>'
                     f'<path d="M{left},{y:.1f} h{bw - r:.1f} a{r},{r} 0 0 1 {r},{r} v{bar_h - 2 * r:.1f} a{r},{r} 0 0 1 -{r},{r} h-{bw - r:.1f} z" fill="{STAGE_COL[si % 3]}"/>'
                     f'<line x1="{X(lo):.1f}" x2="{X(hi):.1f}" y1="{y + bar_h / 2:.1f}" y2="{y + bar_h / 2:.1f}" stroke="{TEXT}" stroke-opacity="0.55" stroke-width="2"/>'
                     + (f'<rect x="{lx - 6:.1f}" y="{y + bar_h / 2 - 18:.1f}" width="{15 * len(lab) + 12}" height="34" fill="{BG}"/>' if clipped else "")
                     + f'<text x="{lx:.1f}" y="{y + bar_h / 2 + 9:.1f}" fill="{TEXT}" font-size="26">{lab}</text>'
                     + (f'<text x="{X(vmax) + 10:.1f}" y="{y + bar_h / 2 + 7:.1f}" fill="{TEXT2}" font-size="20">→ max {fmt(hi, unit)}</text>' if clipped else "")
                     + '</g>')
            if len(groups) == 1:   # single group: name each stage on the axis
                s.append(f'<text x="{left - 24}" y="{y + bar_h / 2 + 9:.1f}" fill="{TEXT2}" font-size="26" text-anchor="end">{html.escape(labels[si])}</text>')
    # legend (always present for >= 2 series)
    lx = left
    for si, lab in enumerate(labels):
        s.append(f'<rect x="{lx}" y="{h - 26}" width="18" height="18" rx="4" fill="{STAGE_COL[si % 3]}"/>'
                 f'<text x="{lx + 28}" y="{h - 11}" fill="{TEXT2}" font-size="20">{html.escape(lab)}</text>')
        lx += 60 + 12 * len(lab)
    s.append("</svg>")
    return "\n".join(s)


def main():
    data = json.loads((ROOT / "compare.json").read_text(encoding="utf-8"))
    labels = [st["label"] for st in data["stages"]]
    rows = {(r["test"], r["item"], r["metric"]): r for r in data["rows"]}
    OUT.mkdir(exist_ok=True)
    made, missing = [], []

    def trip(r, scale):
        return [(r[f"{l}_median"] * scale, r[f"{l}_min"] * scale, r[f"{l}_max"] * scale) for l in labels]

    for fn, title, test, item, metric, scale, unit, note in PANELS:
        r = rows.get((test, item, metric))
        if not r:
            missing.append(fn)
            continue
        (OUT / f"{fn}.svg").write_text(panel_svg(title, note, [("", trip(r, scale))], labels, unit), encoding="utf-8")
        made.append((fn, title))
    bp = ROOT / "bg_procs.json"   # memory held by Android app processes at idle (bg_procs.py, raw meminfo)
    if bp.exists():
        bj = {x["label"]: x for x in json.loads(bp.read_text(encoding="utf-8"))["stages"]}
        if all(l in bj for l in labels):
            (OUT / "app_memory.svg").write_text(panel_svg(
                "Memory held by apps running in the background", "lower is better",
                [("", [(bj[l]["app_pss_mb"], *bj[l]["app_pss_range"]) for l in labels])], labels, "MB"), encoding="utf-8")
            made.insert(0, ("app_memory", "Memory held by apps at idle"))
    groups = [(APP_NAMES.get(p, p), trip(rows[("launch_cold", p, "TotalTime")], 0.001))
              for p in APP_NAMES if ("launch_cold", p, "TotalTime") in rows]
    if groups:
        (OUT / "app_cold_launch.svg").write_text(
            panel_svg("Opening apps from cold (side note) (am start -W, TotalTime)", "lower is better", groups, labels, "s"), encoding="utf-8")
        made.append(("app_cold_launch", "Opening apps from cold"))

    page = ["<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
            "<title>TV launcher charts</title><style>body{background:#141416;color:#F5F5F7;font-family:'Segoe UI',sans-serif;margin:0;padding:16px}"
            "img,object{width:100%;max-width:1600px;display:block;margin:0 auto 24px}</style></head><body>",
            f"<p>Stages: {' → '.join(html.escape(l) for l in labels)} · data: compare.json · table: COMPARE.md</p>"]
    page += [f"<object type='image/svg+xml' data='{fn}.svg' aria-label='{html.escape(t)}'></object>" for fn, t in made]
    page.append("</body></html>")
    (OUT / "charts.html").write_text("\n".join(page), encoding="utf-8")
    print("charts:", ", ".join(f for f, _ in made))
    if missing:
        print("not in every stage (skipped):", ", ".join(missing))


if __name__ == "__main__":
    main()
