#!/usr/bin/env python3
"""
make_svgs.py

Generates simple SVG plots (no external deps) from results CSVs:
- results/parametric_results.csv -> results/parametric_results.svg
- results/wave_cavity_results.csv -> results/wave_cavity_results.svg

Parametric: bar chart of E_avg (locked vs unlocked) across scenarios, plus delta growth text.
Wave cavity: bar chart of E_avg for confined vs open and the ratio.
"""
from __future__ import annotations
import os
import csv
from typing import List, Tuple

HERE = os.path.dirname(__file__)
RES_DIR = os.path.join(HERE, "results")


def _scale(value: float, vmin: float, vmax: float, out_min: float, out_max: float) -> float:
    if vmax <= vmin:
        return out_min
    r = (value - vmin) / (vmax - vmin)
    return out_min + r * (out_max - out_min)


def make_parametric_svg(csv_path: str, out_path: str) -> None:
    rows: List[dict] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    # Expect 4 scenarios
    labels = [r["label"] for r in rows]
    e_locked = [float(r["E_avg_locked"]) for r in rows]
    e_unlocked = [float(r["E_avg_unlocked"]) for r in rows]
    gains = [float(r["Gain_pct"]) for r in rows]
    dgrowth = [float(r["delta_growth"]) for r in rows]

    # Layout
    W, H = 900, 420
    padding = 60
    chart_w = W - 2 * padding
    chart_h = H - 2 * padding

    ymax = max(max(e_locked), max(e_unlocked)) * 1.1 if rows else 1.0

    # Bars per scenario: two bars (locked, unlocked)
    n = len(rows)
    group_w = chart_w / max(n, 1)
    bar_w = group_w * 0.32

    def y_from(v: float) -> float:
        return padding + chart_h - _scale(v, 0.0, ymax, 0, chart_h)

    # SVG header
    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff" stroke="#ddd"/>')
    parts.append(f'<text x="{W/2}" y="28" text-anchor="middle" font-family="Helvetica,Arial" font-size="18" fill="#222">Parametric φπ-Locked vs Unlocked (E_avg)</text>')

    # Axes
    parts.append(f'<line x1="{padding}" y1="{padding}" x2="{padding}" y2="{padding+chart_h}" stroke="#444"/>')
    parts.append(f'<line x1="{padding}" y1="{padding+chart_h}" x2="{padding+chart_w}" y2="{padding+chart_h}" stroke="#444"/>')

    # Y ticks
    for t in range(0, 5):
        v = ymax * t / 4
        y = y_from(v)
        parts.append(f'<line x1="{padding-5}" y1="{y}" x2="{padding}" y2="{y}" stroke="#666"/>')
        parts.append(f'<text x="{padding-8}" y="{y+4}" text-anchor="end" font-size="10" font-family="Helvetica,Arial" fill="#444">{v:.1e}</text>')

    # Bars
    for i, label in enumerate(labels):
        x0 = padding + i * group_w
        # locked
        xL = x0 + group_w*0.25 - bar_w/2
        yL = y_from(e_locked[i])
        hL = padding + chart_h - yL
        parts.append(f'<rect x="{xL:.1f}" y="{yL:.1f}" width="{bar_w:.1f}" height="{hL:.1f}" fill="#2b8a3e"/>')
        # unlocked
        xU = x0 + group_w*0.75 - bar_w/2
        yU = y_from(e_unlocked[i])
        hU = padding + chart_h - yU
        parts.append(f'<rect x="{xU:.1f}" y="{yU:.1f}" width="{bar_w:.1f}" height="{hU:.1f}" fill="#c92a2a"/>')
        # labels
        parts.append(f'<text x="{x0+group_w/2:.1f}" y="{padding+chart_h+18:.1f}" text-anchor="middle" font-size="11" font-family="Helvetica,Arial" fill="#222">{label}</text>')
        parts.append(f'<text x="{x0+group_w/2:.1f}" y="{padding-8:.1f}" text-anchor="middle" font-size="10" font-family="Helvetica,Arial" fill="#222">Δgrowth {dgrowth[i]:+.2f} | Gain {gains[i]:.0f}%</text>')

    # Legend
    parts.append(f'<rect x="{W-270}" y="{padding-12}" width="12" height="12" fill="#2b8a3e"/><text x="{W-250}" y="{padding-2}" font-size="11" font-family="Helvetica,Arial">Locked</text>')
    parts.append(f'<rect x="{W-190}" y="{padding-12}" width="12" height="12" fill="#c92a2a"/><text x="{W-170}" y="{padding-2}" font-size="11" font-family="Helvetica,Arial">Unlocked</text>')

    parts.append('</svg>')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))


def make_wave_svg(csv_path: str, out_path: str) -> None:
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for r in reader:
            rows.append(r)
    # Expect rows: confined, open, ratio
    e_conf = e_open = None
    ratio = None
    for r in rows:
        if r[0] == 'confined':
            e_conf = float(r[1])
        elif r[0] == 'open':
            e_open = float(r[1])
        elif r[0] == 'ratio_confined_over_open':
            try:
                ratio = float(r[1])
            except Exception:
                ratio = None
    if e_conf is None or e_open is None:
        raise RuntimeError('CSV missing expected rows')

    W, H = 600, 360
    padding = 60
    chart_w = W - 2*padding
    chart_h = H - 2*padding
    ymax = max(e_conf, e_open) * 1.1

    def y_from(v: float) -> float:
        return padding + chart_h - _scale(v, 0.0, ymax, 0, chart_h)

    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff" stroke="#ddd"/>')
    parts.append(f'<text x="{W/2}" y="28" text-anchor="middle" font-family="Helvetica,Arial" font-size="18" fill="#222">Confinement vs Dissipation (E_avg)</text>')
    parts.append(f'<line x1="{padding}" y1="{padding}" x2="{padding}" y2="{padding+chart_h}" stroke="#444"/>')
    parts.append(f'<line x1="{padding}" y1="{padding+chart_h}" x2="{padding+chart_w}" y2="{padding+chart_h}" stroke="#444"/>')

    # Y ticks
    for t in range(0, 5):
        v = ymax * t / 4
        y = y_from(v)
        parts.append(f'<line x1="{padding-5}" y1="{y}" x2="{padding}" y2="{y}" stroke="#666"/>')
        parts.append(f'<text x="{padding-8}" y="{y+4}" text-anchor="end" font-size="10" font-family="Helvetica,Arial" fill="#444">{v:.1f}</text>')

    group_w = chart_w
    bar_w = group_w * 0.25
    x0 = padding

    # confined bar
    xC = padding + group_w*0.33 - bar_w/2
    yC = y_from(e_conf)
    hC = padding + chart_h - yC
    parts.append(f'<rect x="{xC:.1f}" y="{yC:.1f}" width="{bar_w:.1f}" height="{hC:.1f}" fill="#1c7ed6"/>')
    parts.append(f'<text x="{xC+bar_w/2:.1f}" y="{padding+chart_h+18:.1f}" text-anchor="middle" font-size="11" font-family="Helvetica,Arial" fill="#222">Confined</text>')

    # open bar
    xO = padding + group_w*0.66 - bar_w/2
    yO = y_from(e_open)
    hO = padding + chart_h - yO
    parts.append(f'<rect x="{xO:.1f}" y="{yO:.1f}" width="{bar_w:.1f}" height="{hO:.1f}" fill="#868e96"/>')
    parts.append(f'<text x="{xO+bar_w/2:.1f}" y="{padding+chart_h+18:.1f}" text-anchor="middle" font-size="11" font-family="Helvetica,Arial" fill="#222">Open</text>')

    # ratio text
    if ratio is not None:
        parts.append(f'<text x="{W/2}" y="{padding-8}" text-anchor="middle" font-size="12" font-family="Helvetica,Arial" fill="#222">Retention ratio (confined/open): {ratio:.1f}×</text>')

    parts.append('</svg>')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))


def main() -> None:
    os.makedirs(RES_DIR, exist_ok=True)
    param_csv = os.path.join(RES_DIR, 'parametric_results.csv')
    param_svg = os.path.join(RES_DIR, 'parametric_results.svg')
    wave_csv = os.path.join(RES_DIR, 'wave_cavity_results.csv')
    wave_svg = os.path.join(RES_DIR, 'wave_cavity_results.svg')

    if os.path.exists(param_csv):
        make_parametric_svg(param_csv, param_svg)
        print(f"[ok] Wrote {param_svg}")
    else:
        print(f"[warn] Missing {param_csv}; run phi_pi_parametric_sim.py first")

    if os.path.exists(wave_csv):
        make_wave_svg(wave_csv, wave_svg)
        print(f"[ok] Wrote {wave_svg}")
    else:
        print(f"[warn] Missing {wave_csv}; run wave_cavity_phi_pi.py first")


if __name__ == '__main__':
    main()
