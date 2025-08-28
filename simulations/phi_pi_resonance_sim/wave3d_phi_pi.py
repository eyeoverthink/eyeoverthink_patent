#!/usr/bin/env python3
"""
wave3d_phi_pi.py

3D wave simulation to illustrate confinement vs dissipation under φπ-phase drive with
noise/chaos. Compares reflective cavity vs absorbing boundaries (PML-like damping ramp).
Exports CSV summary and an SVG bar plot.

Pure Python, no external deps. Small grid to keep runtime reasonable.
"""
from __future__ import annotations
import os
import math
import random
import statistics
from dataclasses import dataclass
from typing import Tuple, List

PHI = (1.0 + 5.0 ** 0.5) / 2.0
PHI_PI = PHI * math.pi


@dataclass
class P3D:
    N: int = 22          # grid on each axis (interior updated indices 1..N-2)
    c: float = 1.0
    dx: float = 1.0
    dt: float = 0.35     # Courant r = c*dt/dx must be <= 1/sqrt(dim)=~0.577 for 3D explicit scheme
    steps: int = 700

    gamma_interior: float = 2e-3
    pml_len: int = 3
    pml_max: float = 0.06

    # source
    A: float = 0.7
    f_cycles: float = 0.02  # cycles per step

    # noise/chaos
    sigma_amp: float = 0.10
    phase_jitter: float = 0.02

    seed: int = 5


class Wave3D:
    def __init__(self, p: P3D, mode: str):
        assert mode in ("confined", "open")
        self.p = p
        self.mode = mode
        random.seed(p.seed)
        self.r = p.c * p.dt / p.dx
        if self.r > 1.0 / (3 ** 0.5):
            raise ValueError("Courant condition violated for 3D: c*dt/dx must be <= 1/sqrt(3)")
        N = p.N
        M = N*N
        self.N = N
        self.u_prev = [0.0] * (N*N*N)
        self.u = [0.0] * (N*N*N)
        self.u_next = [0.0] * (N*N*N)
        # center source
        self.src = (N//2, N//2, N//2)
        # damping profile
        self.gamma = [p.gamma_interior] * (N*N*N)
        if mode == "open":
            L = p.pml_len
            for k in range(N):
                for j in range(N):
                    for i in range(N):
                        d = min(i, j, k, N-1-i, N-1-j, N-1-k)
                        g = 0.0
                        if d < L:
                            g = p.pml_max * (L - d) / L
                        idx = (k*N + j)*N + i
                        self.gamma[idx] += g
        self.omega = 2.0 * math.pi * p.f_cycles
        self.phase = PHI_PI

    def idx(self, i: int, j: int, k: int) -> int:
        N = self.N
        return (k*N + j)*N + i

    def step(self, n: int):
        p = self.p
        N = self.N
        r2 = self.r * self.r

        # phase update
        self.phase += random.gauss(0.0, p.phase_jitter)
        amp_noise = 1.0 + p.sigma_amp * random.gauss(0.0, 1.0)
        s = p.A * amp_noise * math.sin(self.omega * n + self.phase)
        isrc, jsrc, ksrc = self.src

        # interior update
        for k in range(1, N-1):
            for j in range(1, N-1):
                base = (k*N + j)*N
                for i in range(1, N-1):
                    idx = base + i
                    lap = (self.u[idx-1] + self.u[idx+1] +
                           self.u[idx-N] + self.u[idx+N] +
                           self.u[idx - N*N] + self.u[idx + N*N] - 6.0*self.u[idx])
                    g = self.gamma[idx]
                    self.u_next[idx] = ((2 - 2*g*p.dt) * self.u[idx]
                                         - (1 - g*p.dt) * self.u_prev[idx]
                                         + r2 * lap)
        # source force (additive at center)
        idx0 = self.idx(isrc, jsrc, ksrc)
        self.u_next[idx0] += (p.dt * p.dt) * s

        # boundaries
        if self.mode == "confined":
            # Dirichlet fixed
            for k in (0, N-1):
                basek = k*N*N
                for j in range(N):
                    base = basek + j*N
                    self.u_next[base + 0] = 0.0
                    self.u_next[base + (N-1)] = 0.0
            for k in range(N):
                basek = k*N*N
                for i in range(N):
                    self.u_next[basek + 0*N + i] = 0.0
                    self.u_next[basek + (N-1)*N + i] = 0.0
        else:
            # approximate absorbing: copy neighbor inward
            for k in range(N):
                basek = k*N*N
                for j in range(N):
                    base = basek + j*N
                    self.u_next[base + 0] = self.u[base + 1]
                    self.u_next[base + (N-1)] = self.u[base + (N-2)]
            for k in range(N):
                basek = k*N*N
                for i in range(N):
                    self.u_next[basek + 0*N + i] = self.u[basek + 1*N + i]
                    self.u_next[basek + (N-1)*N + i] = self.u[basek + (N-2)*N + i]

        # rotate
        self.u_prev, self.u, self.u_next = self.u, self.u_next, self.u_prev

    def energy(self) -> float:
        p = self.p
        N = self.N
        v2_sum = 0.0
        ux2_sum = 0.0
        for k in range(1, N-1):
            for j in range(1, N-1):
                for i in range(1, N-1):
                    idx = (k*N + j)*N + i
                    v = (self.u[idx] - self.u_prev[idx]) / p.dt
                    # central diffs for gradient squared
                    ux = 0.5*(self.u[idx+1] - self.u[idx-1]) / p.dx
                    uy = 0.5*(self.u[idx+N] - self.u[idx-N]) / p.dx
                    uz = 0.5*(self.u[idx+N*N] - self.u[idx-N*N]) / p.dx
                    v2_sum += v*v
                    ux2_sum += (ux*ux + uy*uy + uz*uz)
        return 0.5 * (v2_sum + (p.c*p.c) * ux2_sum) * (p.dx ** 3)


def run_once(mode: str, p: P3D) -> Tuple[float, float]:
    sim = Wave3D(p, mode)
    energies: List[float] = []
    for n in range(p.steps):
        sim.step(n)
        if n > p.steps // 2:
            energies.append(sim.energy())
    return statistics.fmean(energies), max(energies) if energies else (0.0, 0.0)


def write_svg_bar(EA: float, EB: float, out_path: str) -> None:
    W, H = 560, 360
    pad = 60
    chart_w = W - 2*pad
    chart_h = H - 2*pad
    ymax = max(EA, EB) * 1.1 if max(EA, EB) > 0 else 1.0
    def y_from(v: float) -> float:
        return pad + chart_h - (v / ymax) * chart_h
    parts: List[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#fff" stroke="#ddd"/>')
    parts.append(f'<text x="{W/2}" y="28" text-anchor="middle" font-family="Helvetica,Arial" font-size="18" fill="#222">3D Confinement vs Dissipation (E_avg)</text>')
    parts.append(f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{pad+chart_h}" stroke="#444"/>')
    parts.append(f'<line x1="{pad}" y1="{pad+chart_h}" x2="{pad+chart_w}" y2="{pad+chart_h}" stroke="#444"/>')
    # y ticks
    for t in range(5):
        v = ymax * t / 4
        y = y_from(v)
        parts.append(f'<line x1="{pad-5}" y1="{y:.1f}" x2="{pad}" y2="{y:.1f}" stroke="#666"/>')
        parts.append(f'<text x="{pad-8}" y="{y+4:.1f}" text-anchor="end" font-size="10" font-family="Helvetica,Arial" fill="#444">{v:.1e}</text>')
    # bars
    group_w = chart_w
    bar_w = group_w * 0.25
    xC = pad + group_w*0.33 - bar_w/2
    xO = pad + group_w*0.66 - bar_w/2
    yC = y_from(EA); hC = pad + chart_h - yC
    yO = y_from(EB); hO = pad + chart_h - yO
    parts.append(f'<rect x="{xC:.1f}" y="{yC:.1f}" width="{bar_w:.1f}" height="{hC:.1f}" fill="#1971c2"/>')
    parts.append(f'<text x="{xC+bar_w/2:.1f}" y="{pad+chart_h+18:.1f}" text-anchor="middle" font-size="11" font-family="Helvetica,Arial" fill="#222">Confined</text>')
    parts.append(f'<rect x="{xO:.1f}" y="{yO:.1f}" width="{bar_w:.1f}" height="{hO:.1f}" fill="#868e96"/>')
    parts.append(f'<text x="{xO+bar_w/2:.1f}" y="{pad+chart_h+18:.1f}" text-anchor="middle" font-size="11" font-family="Helvetica,Arial" fill="#222">Open</text>')
    parts.append('</svg>')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))


def main() -> None:
    p = P3D()
    EA, PA = run_once("confined", p)
    EB, PB = run_once("open", p)
    print("3D E_avg confined=%.3e, open=%.3e, ratio=%.2f x" % (EA, EB, (EA/EB if EB>0 else float('inf'))))
    # write CSV + SVG
    out_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, 'wave3d_results.csv')
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write('scenario,E_avg,E_peak\n')
        f.write(f'confined,{EA:.9e},{PA:.9e}\n')
        f.write(f'open,{EB:.9e},{PB:.9e}\n')
        f.write(f'ratio_confined_over_open,{(EA/EB if EB>0 else float("nan")):.6f},\n')
    svg_path = os.path.join(out_dir, 'wave3d_results.svg')
    write_svg_bar(EA, EB, svg_path)
    print(f"[ok] Wrote {csv_path}\n[ok] Wrote {svg_path}")


if __name__ == '__main__':
    main()
