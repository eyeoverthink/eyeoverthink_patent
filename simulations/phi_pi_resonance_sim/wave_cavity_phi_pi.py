#!/usr/bin/env python3
"""
wave_cavity_phi_pi.py

1D wave (transmission line / acoustic string) simulation to illustrate:
- Confinement (reflective cavity) vs dissipation (absorbing boundaries)
- φπ-phase drive with additive noise ("static") and phase jitter ("chaos")

We compare two scenarios under identical drive:
  (A) Confined cavity (reflective boundaries) -> standing wave builds energy
  (B) Open line (absorbing boundaries/PML)    -> energy exits, little accumulation

Metrics: domain energy over time, average steady-state energy, and ratio (A/B).
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
import os
from typing import Tuple

PHI = (1.0 + 5.0 ** 0.5) / 2.0
PHI_PI = PHI * math.pi


@dataclass
class CavityParams:
    N: int = 600           # grid points
    c: float = 1.0         # wave speed
    dx: float = 1.0
    dt: float = 0.5        # must satisfy c*dt/dx <= 1 for stability (Courant)
    steps: int = 9000

    # Damping (interior baseline)
    gamma_interior: float = 1e-3

    # PML parameters for absorbing boundaries
    pml_len: int = 80                  # cells on each side
    pml_max: float = 0.02              # max added damping at the edge

    # Drive source
    i_src: int = 60                    # source index
    A: float = 0.6                     # amplitude
    f_cycles: float = 0.02             # drive freq in cycles per dt step (dimensionless)

    # Noise / chaos
    sigma_amp: float = 0.10            # amplitude noise fraction (static)
    phase_jitter: float = 0.02         # random walk per step (rad)

    # Random seed
    seed: int = 4


class WaveCavity:
    def __init__(self, p: CavityParams, mode: str):
        assert mode in ("confined", "open")
        self.p = p
        self.mode = mode
        random.seed(p.seed)
        self.r = p.c * p.dt / p.dx
        if self.r > 1.0:
            raise ValueError("Courant condition violated: c*dt/dx must be <= 1")
        # State arrays
        N = p.N
        self.u_prev = [0.0] * N
        self.u = [0.0] * N
        self.u_next = [0.0] * N
        # Spatial damping profile
        self.gamma = [p.gamma_interior] * N
        if mode == "open":
            # Add PML on both ends (linearly ramped)
            L = p.pml_len
            for i in range(L):
                g = p.pml_max * (i + 1) / L
                self.gamma[i] += g
                self.gamma[N - 1 - i] += g
        # Precompute drive omega
        self.omega = 2.0 * math.pi * p.f_cycles
        self.phase = PHI_PI  # drive phase offset (φπ)

    def step(self, n: int):
        p = self.p
        N = p.N
        r2 = self.r * self.r

        # Update phase with jitter (chaos)
        self.phase += random.gauss(0.0, p.phase_jitter)

        # Drive at source index
        amp_noise = 1.0 + p.sigma_amp * random.gauss(0.0, 1.0)
        s = p.A * amp_noise * math.sin(self.omega * n + self.phase)

        # Update interior points
        for i in range(1, N - 1):
            lap = self.u[i + 1] - 2 * self.u[i] + self.u[i - 1]
            # Damping term (discretized as scaling of u and u_prev)
            g = self.gamma[i]
            self.u_next[i] = (
                (2 - 2 * g * p.dt) * self.u[i]
                - (1 - g * p.dt) * self.u_prev[i]
                + r2 * lap
            )
        # Apply drive as force at i_src (additive)
        i0 = max(1, min(N - 2, p.i_src))
        self.u_next[i0] += (p.dt * p.dt) * s

        # Boundaries
        if self.mode == "confined":
            # Reflective Dirichlet (fixed ends)
            self.u_next[0] = 0.0
            self.u_next[N - 1] = 0.0
        else:
            # Open: first-order absorbing (approximate) + PML already applied via gamma
            self.u_next[0] = self.u[1]
            self.u_next[N - 1] = self.u[N - 2]

        # Rotate buffers
        self.u_prev, self.u, self.u_next = self.u, self.u_next, self.u_prev

    def energy(self) -> float:
        # Approximate discrete energy: sum[ 1/2 (u_t^2 + c^2 u_x^2) ] dx
        p = self.p
        v2_sum = 0.0
        ux2_sum = 0.0
        for i in range(1, p.N - 1):
            v = (self.u[i] - self.u_prev[i]) / p.dt
            ux = 0.5 * (self.u[i + 1] - self.u[i - 1]) / p.dx
            v2_sum += v * v
            ux2_sum += ux * ux
        return 0.5 * (v2_sum + (p.c * p.c) * ux2_sum) * p.dx


def run_once(mode: str, p: CavityParams) -> Tuple[float, float]:
    cav = WaveCavity(p, mode=mode)
    energies = []
    for n in range(p.steps):
        cav.step(n)
        if n > p.steps // 2:
            energies.append(cav.energy())
    return statistics.fmean(energies), max(energies) if energies else (0.0, 0.0)


def main():
    p = CavityParams()
    # Scenario A: confined cavity
    Eavg_A, Epk_A = run_once("confined", p)
    # Scenario B: open line
    Eavg_B, Epk_B = run_once("open", p)

    print("=" * 80)
    print("1D Wave: Confinement vs Dissipation with φπ drive (noise + chaos)")
    print(f"PHI=%.6f, PHI*PI=%.6f | N={p.N}, c={p.c}, dt={p.dt}, steps={p.steps}, r={p.c*p.dt/p.dx:.3f}" % (PHI, PHI_PI))
    print(f"Drive: A={p.A}, f_cycles={p.f_cycles:.4f}/step, amp_noise={p.sigma_amp}, phase_jitter={p.phase_jitter}")
    print(f"Damping: interior γ={p.gamma_interior}, PML_len={p.pml_len}, PML_max={p.pml_max}")
    print("\n-- Confined (reflective cavity) --")
    print(f"E_avg={Eavg_A:.6e}, E_peak={Epk_A:.6e}")
    print("\n-- Open (absorbing boundaries) --")
    print(f"E_avg={Eavg_B:.6e}, E_peak={Epk_B:.6e}")
    if Eavg_B > 0:
        print("\nEnergy retention ratio (confined/open): %.1f x" % (Eavg_A / Eavg_B))

    # Write CSV summary
    try:
        out_dir = os.path.join(os.path.dirname(__file__), "results")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "wave_cavity_results.csv")
        ratio = (Eavg_A / Eavg_B) if Eavg_B > 0 else float('nan')
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("scenario,E_avg,E_peak\n")
            f.write(f"confined,{Eavg_A:.9e},{Epk_A:.9e}\n")
            f.write(f"open,{Eavg_B:.9e},{Epk_B:.9e}\n")
            f.write(f"ratio_confined_over_open,{ratio:.6f},\n")
    except Exception as e:
        print(f"[warn] Failed to write CSV: {e}")


if __name__ == "__main__":
    main()
