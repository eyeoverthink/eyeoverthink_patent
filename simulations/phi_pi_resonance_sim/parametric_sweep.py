#!/usr/bin/env python3
"""
parametric_sweep.py

Runs a robustness sweep of the φπ-locked parametric simulation over:
- detuning (omega_drive_ratio around 1.0)
- Q0 values
- pump depth m expressed as multiples of threshold m_thr ≈ 1/Q0
- random seeds

Outputs:
- results/parametric_sweep.csv (aggregated across seeds: mean/std of gain and Δgrowth)
- results/parametric_sweep_Q{Q0}.svg heatmaps for each Q0 (x=m/m_thr, y=detuning), color-coded by mean Gain_pct

No external dependencies; uses basic SVG generation.
"""
from __future__ import annotations
import os
import csv
import math
from typing import List, Dict

from phi_pi_parametric_sim import ParamParams, simulate_parametric

HERE = os.path.dirname(__file__)
RES_DIR = os.path.join(HERE, "results")


def run_sweep() -> List[Dict[str, float]]:
    # Sweep parameters
    Q_list = [150.0, 300.0, 600.0]
    detune_list = [0.98, 1.00, 1.02]
    m_over_thr_list = [0.7, 0.9, 1.1, 1.4, 1.8, 2.2]
    seeds = [7, 11]  # keep runtime practical while averaging randomness

    base = ParamParams(
        f0=60.0,
        beta=3e4,
        F0=0.0,
        sigma_gamma=0.0,
        sigma_add=1e-6,
        chaos_phase_sigma=5.0,
        K_lock=3000.0,
        C_field=0.7,
        C_affect_gamma=0.6,
        C_affect_lock=1.0,
        G_gain=0.0,
        dt=2e-5,
        T=2.0,  # shorter horizon for sweep
        seed=7,
    )

    results: List[Dict[str, float]] = []

    for Q0 in Q_list:
        m_thr = 1.0 / Q0
        for det in detune_list:
            for mom in m_over_thr_list:
                m = mom * m_thr
                gains = []
                dgrowths = []
                for s in seeds:
                    p = ParamParams(**{**base.__dict__, 'Q0': Q0, 'omega_drive_ratio': det, 'm_param': m})
                    locked = simulate_parametric(True, p, seed=s)
                    unlocked = simulate_parametric(False, p, seed=s)
                    dE = (locked['E_avg'] - unlocked['E_avg']) / max(unlocked['E_avg'], 1e-12)
                    dG = locked['growth_ratio'] - unlocked['growth_ratio']
                    gains.append(100.0 * dE)
                    dgrowths.append(dG)
                gain_mean = sum(gains) / len(gains)
                gain_std = (sum((g - gain_mean) ** 2 for g in gains) / len(gains)) ** 0.5
                dgrowth_mean = sum(dgrowths) / len(dgrowths)
                dgrowth_std = (sum((g - dgrowth_mean) ** 2 for g in dgrowths) / len(dgrowths)) ** 0.5
                results.append({
                    'Q0': Q0,
                    'detune': det,
                    'm_over_thr': mom,
                    'm': m,
                    'gain_pct_mean': gain_mean,
                    'gain_pct_std': gain_std,
                    'delta_growth_mean': dgrowth_mean,
                    'delta_growth_std': dgrowth_std,
                })
    return results


def write_csv(rows: List[Dict[str, float]], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cols = ['Q0', 'detune', 'm_over_thr', 'm', 'gain_pct_mean', 'gain_pct_std', 'delta_growth_mean', 'delta_growth_std']
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _scale(value: float, vmin: float, vmax: float) -> float:
    if vmax <= vmin:
        return 0.0
    return max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))


def make_heatmap_svgs(rows: List[Dict[str, float]]) -> None:
    # Build per-Q grids
    by_q: Dict[float, List[Dict[str, float]]] = {}
    for r in rows:
        by_q.setdefault(r['Q0'], []).append(r)

    dets = sorted({r['detune'] for r in rows})
    moms = sorted({r['m_over_thr'] for r in rows})

    for Q0, sub in by_q.items():
        # Create a map for access
        key = {(r['detune'], r['m_over_thr']): r for r in sub}
        W, H = 840, 420
        pad = 60
        chart_w = W - 2 * pad
        chart_h = H - 2 * pad
        cell_w = chart_w / max(1, len(moms))
        cell_h = chart_h / max(1, len(dets))

        # Color scale based on gain mean; clamp 0..5000%
        vmin, vmax = 0.0, 5000.0

        parts: List[str] = []
        parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
        parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#fff" stroke="#ddd"/>')
        parts.append(f'<text x="{W/2}" y="28" text-anchor="middle" font-family="Helvetica,Arial" font-size="18" fill="#222">Parametric Gain Heatmap (Q0={Q0:.0f})</text>')
        parts.append(f'<text x="{W/2}" y="{H-10}" text-anchor="middle" font-family="Helvetica,Arial" font-size="12" fill="#444">x: m/m_thr | y: detuning (ω_d/ω0) | color: mean Gain % (clamped to 0..5000)</text>')

        # Axes
        parts.append(f'<rect x="{pad}" y="{pad}" width="{chart_w}" height="{chart_h}" fill="#f8f9fa" stroke="#ccc"/>')

        for yi, det in enumerate(dets):
            for xi, mom in enumerate(moms):
                r = key.get((det, mom))
                if not r:
                    continue
                g = r['gain_pct_mean']
                a = _scale(g, vmin, vmax)
                # Color ramp: gray -> blue -> red
                # Interpolate from #dee2e6 to #1c7ed6 to #c92a2a
                def lerp(c1, c2, t):
                    return tuple(int(c1[i] + (c2[i]-c1[i]) * t) for i in range(3))
                gray = (222, 226, 230)
                blue = (28, 126, 214)
                red = (201, 42, 42)
                if a < 0.5:
                    col = lerp(gray, blue, a/0.5)
                else:
                    col = lerp(blue, red, (a-0.5)/0.5)
                fill = f'rgb({col[0]},{col[1]},{col[2]})'
                x = pad + xi * cell_w
                y = pad + yi * cell_h
                parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" fill="{fill}" stroke="#fff" stroke-width="1"/>')
                parts.append(f'<title>detune={det:.3f}, m/m_thr={mom:.2f}, gain={g:.1f}%</title>')

        # x labels (m/m_thr)
        for xi, mom in enumerate(moms):
            cx = pad + (xi + 0.5) * cell_w
            parts.append(f'<text x="{cx:.1f}" y="{pad+chart_h+16:.1f}" text-anchor="middle" font-family="Helvetica,Arial" font-size="11" fill="#333">{mom:.2f}</text>')
        # y labels (detune)
        for yi, det in enumerate(dets):
            cy = pad + (yi + 0.5) * cell_h
            parts.append(f'<text x="{pad-8}" y="{cy:.1f}" text-anchor="end" font-family="Helvetica,Arial" font-size="11" fill="#333">{det:.2f}</text>')

        parts.append('</svg>')
        out_svg = os.path.join(RES_DIR, f'parametric_sweep_Q{int(Q0)}.svg')
        with open(out_svg, 'w', encoding='utf-8') as f:
            f.write('\n'.join(parts))
        print(f"[ok] Wrote {out_svg}")


def main() -> None:
    os.makedirs(RES_DIR, exist_ok=True)
    rows = run_sweep()
    csv_path = os.path.join(RES_DIR, 'parametric_sweep.csv')
    write_csv(rows, csv_path)
    print(f"[ok] Wrote {csv_path}")
    make_heatmap_svgs(rows)


if __name__ == '__main__':
    main()
