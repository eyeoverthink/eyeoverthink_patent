#!/usr/bin/env python3
"""
wave_absorption_sweep.py

Sweeps boundary absorption in the 1D wave cavity model by varying PML max damping (pml_max),
quantifying how average energy and retention ratio change.

Outputs:
- results/wave_absorption_sweep.csv
- results/wave_absorption_sweep.svg (retention ratio vs pml_max)

No external dependencies.
"""
from __future__ import annotations
import os
import csv
import statistics
from typing import List, Tuple

from wave_cavity_phi_pi import CavityParams, run_once

HERE = os.path.dirname(__file__)
RES_DIR = os.path.join(HERE, "results")


def run_sweep() -> List[dict]:
    os.makedirs(RES_DIR, exist_ok=True)
    # Sweep values (0 means minimal absorption at boundary; larger = more open)
    pml_max_values = [0.0, 0.005, 0.01, 0.02, 0.03, 0.05]
    seeds = [3, 7, 11]

    # Fixed base params; reduce steps to keep runtime moderate, keeping stats credible
    base = CavityParams(steps=6000)

    # Compute confined baseline once per seed (does not depend on pml_max in confined mode)
    confined_avgs: List[float] = []
    confined_peaks: List[float] = []
    for s in seeds:
        p_conf = CavityParams(**{**base.__dict__, 'seed': s})
        Eavg_c, Epk_c = run_once("confined", p_conf)
        confined_avgs.append(Eavg_c)
        confined_peaks.append(Epk_c)
    conf_mean = statistics.fmean(confined_avgs)
    conf_std = statistics.pstdev(confined_avgs) if len(confined_avgs) > 1 else 0.0

    rows: List[dict] = []
    for pml_max in pml_max_values:
        open_avgs: List[float] = []
        open_peaks: List[float] = []
        for s in seeds:
            p_open = CavityParams(**{**base.__dict__, 'seed': s, 'pml_max': pml_max})
            Eavg_o, Epk_o = run_once("open", p_open)
            open_avgs.append(Eavg_o)
            open_peaks.append(Epk_o)
        open_mean = statistics.fmean(open_avgs)
        open_std = statistics.pstdev(open_avgs) if len(open_avgs) > 1 else 0.0
        ratio = conf_mean / open_mean if open_mean > 0 else float('inf')
        rows.append({
            'pml_max': pml_max,
            'E_avg_confined_mean': conf_mean,
            'E_avg_confined_std': conf_std,
            'E_avg_open_mean': open_mean,
            'E_avg_open_std': open_std,
            'retention_ratio_mean': ratio,
        })
    return rows


def write_csv(rows: List[dict], path: str) -> None:
    cols = ['pml_max', 'E_avg_confined_mean', 'E_avg_confined_std', 'E_avg_open_mean', 'E_avg_open_std', 'retention_ratio_mean']
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def make_svg(rows: List[dict], out_path: str) -> None:
    # Simple line plot retention_ratio_mean vs pml_max
    W, H = 680, 360
    pad = 60
    chart_w = W - 2 * pad
    chart_h = H - 2 * pad

    xs = [r['pml_max'] for r in rows]
    ys = [r['retention_ratio_mean'] for r in rows]
    if not xs:
        return
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    # clamp ymax for visibility if extreme
    ymax = max(ymax, 1.0)

    def x_map(x):
        if xmax == xmin:
            return pad
        return pad + (x - xmin) / (xmax - xmin) * chart_w

    def y_map(y):
        # higher y -> lower on screen
        return pad + chart_h - (y - 0.0) / (ymax - 0.0) * chart_h if ymax > 0 else pad + chart_h

    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#fff" stroke="#ddd"/>')
    parts.append(f'<text x="{W/2}" y="28" text-anchor="middle" font-family="Helvetica,Arial" font-size="18" fill="#222">Retention vs Boundary Absorption (PML max damping)</text>')
    parts.append(f'<text x="{W/2}" y="{H-10}" text-anchor="middle" font-family="Helvetica,Arial" font-size="12" fill="#444">x: pml_max | y: E_avg(confined)/E_avg(open)</text>')

    # Axes
    parts.append(f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{pad+chart_h}" stroke="#444"/>')
    parts.append(f'<line x1="{pad}" y1="{pad+chart_h}" x2="{pad+chart_w}" y2="{pad+chart_h}" stroke="#444"/>')

    # Y ticks (5)
    for t in range(0, 5):
        v = (ymax) * t / 4
        y = y_map(v)
        parts.append(f'<line x1="{pad-5}" y1="{y:.1f}" x2="{pad}" y2="{y:.1f}" stroke="#666"/>')
        parts.append(f'<text x="{pad-8}" y="{y+4:.1f}" text-anchor="end" font-size="10" font-family="Helvetica,Arial" fill="#444">{v:.1f}</text>')

    # X ticks for each pml_max
    for x in xs:
        X = x_map(x)
        parts.append(f'<line x1="{X:.1f}" y1="{pad+chart_h}" x2="{X:.1f}" y2="{pad+chart_h+5}" stroke="#666"/>')
        parts.append(f'<text x="{X:.1f}" y="{pad+chart_h+18:.1f}" text-anchor="middle" font-size="10" font-family="Helvetica,Arial" fill="#444">{x:.3f}</text>')

    # Polyline
    if len(xs) >= 2:
        pts = ' '.join(f"{x_map(x):.1f},{y_map(y):.1f}" for x, y in zip(xs, ys))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#1c7ed6" stroke-width="2.5"/>')
    # Markers
    for x, y in zip(xs, ys):
        parts.append(f'<circle cx="{x_map(x):.1f}" cy="{y_map(y):.1f}" r="3" fill="#1c7ed6"/>')

    parts.append('</svg>')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))


def main() -> None:
    rows = run_sweep()
    csv_path = os.path.join(RES_DIR, 'wave_absorption_sweep.csv')
    write_csv(rows, csv_path)
    print(f"[ok] Wrote {csv_path}")
    svg_path = os.path.join(RES_DIR, 'wave_absorption_sweep.svg')
    make_svg(rows, svg_path)
    print(f"[ok] Wrote {svg_path}")


if __name__ == '__main__':
    main()
