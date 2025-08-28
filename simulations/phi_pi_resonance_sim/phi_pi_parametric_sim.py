#!/usr/bin/env python3
"""
phi_pi_parametric_sim.py

Parametrically-driven nonlinear resonator (Duffing) with φπ phase locking.
Demonstrates multiplicative/parametric pumping using a time-referenced pump near 2ω0
(Mathieu setup):

  x¨ + (2γ0 - G_gain + σ_γ ξ(t)) x˙ + [ω0² + k_mod(t)] x + β x³ = F0 cos(ω_d t + θ)

with k_mod(t) = ω0² m cos(2 ω_d t + θ_pump), θ_pump = φπ + δ(t) + φ_align.
Locked: δ̇ = -K sin δ + jitter (δ → 0). Unlocked: δ is a random walk (large jitter).

Outputs: average energy, peak energy, RMS displacement, and a simple growth ratio.
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Dict, Tuple
import os

PHI = (1.0 + 5.0 ** 0.5) / 2.0
PHI_PI = PHI * math.pi


@dataclass
class ParamParams:
    # Resonator
    f0: float = 60.0            # Hz
    Q0: float = 100.0           # dimensionless
    beta: float = 3.0e4         # Duffing cubic coefficient (saturation)

    # Parametric drive
    omega_drive_ratio: float = 1.0      # ω_d / ω0 (pump frequency is 2*ω_d)
    m_param: float = 0.012              # modulation depth on stiffness (dimensionless)

    # Direct drive (can be zero — param pumping is main energy source here)
    F0: float = 0.0

    # Noise / chaos
    sigma_gamma: float = 0.0     # multiplicative damping fluctuations
    sigma_add: float = 1e-4      # additive acceleration noise (seed)
    chaos_phase_sigma: float = 30.0  # rad / sqrt(s)

    # Locking
    K_lock: float = 1500.0
    C_field: float = 0.7
    C_affect_gamma: float = 0.6
    C_affect_lock: float = 1.0

    # Pump phase alignment: θ_pump = 2θ_osc + (φπ + δ + φ_align)
    # Set φ_align = π - φπ so that when locked (δ→0), θ_pump ≈ 2θ_osc + π (optimal softening at displacement peaks)
    phi_align: float = math.pi - PHI_PI

    # Optional active negative damping
    G_gain: float = 0.0

    # Integration
    dt: float = 2e-5
    T: float = 3.0

    seed: int = 2

    # Small initial seed to break symmetry
    x0_seed: float = 1e-6
    v0_seed: float = 0.0


def simulate_parametric(locked: bool, p: ParamParams, seed: int = 1) -> Dict[str, float]:
    random.seed(seed)
    # Base frequencies
    omega0 = 2.0 * math.pi * p.f0
    omega_d = p.omega_drive_ratio * omega0

    # Base damping with C-field effect
    gamma0 = omega0 / (2.0 * p.Q0)
    gamma0 = max(0.0, gamma0 * (1.0 - p.C_field * p.C_affect_gamma))

    # Locking strength
    K_eff = p.K_lock * (1.0 + p.C_field * p.C_affect_lock) if locked else 0.0

    # State variables
    x = p.x0_seed
    v = p.v0_seed
    delta = 0.0  # phase error

    # Time
    dt = p.dt
    steps = int(p.T / dt)
    t = 0.0

    # Pre-calc noise scales
    phase_jitter_scale = p.chaos_phase_sigma * math.sqrt(dt)

    # Buffers for metrics
    E_vals = []
    x2_vals = []

    # Helper: energy (using base ω0 for a consistent measure)
    def energy(x: float, v: float) -> float:
        return 0.5 * v * v + 0.5 * omega0 * omega0 * x * x + 0.25 * p.beta * x * x * x * x

    # Derivative
    def acc(t_local: float, x_local: float, v_local: float, k_mod: float, gamma_eff: float, delta_phase: float) -> float:
        # Direct drive phase uses same φπ + δ for coherence
        theta = PHI_PI + delta_phase
        drive = p.F0 * math.cos(omega_d * t_local + theta)
        # Additive acceleration noise
        a_noise = p.sigma_add * random.gauss(0.0, 1.0)
        return -2.0 * gamma_eff * v_local - (omega0 * omega0 + k_mod) * x_local - p.beta * (x_local ** 3) + drive + a_noise

    # Main loop
    for n in range(steps):
        # Phase dynamics (lock vs random walk)
        if K_eff > 0.0:
            delta += (-K_eff * math.sin(delta)) * dt + phase_jitter_scale * random.gauss(0.0, 1.0)
        else:
            delta += phase_jitter_scale * random.gauss(0.0, 1.0)

        # Effective damping with optional negative gain and multiplicative fluctuations
        gamma_eff = max(0.0, gamma0 - p.G_gain) + p.sigma_gamma * random.gauss(0.0, 1.0)

        # Parametric stiffness modulation at ~2*ω_d, with φπ+δ alignment
        theta_pump = PHI_PI + delta + p.phi_align
        k_mod = omega0 * omega0 * p.m_param * math.cos(2.0 * omega_d * t + theta_pump)

        # RK4 integration for x and v (freeze noise within this dt)
        a1 = acc(t, x, v, k_mod, gamma_eff, delta)
        k1x, k1v = v, a1

        a2 = acc(t + 0.5 * dt, x + 0.5 * dt * k1x, v + 0.5 * dt * k1v, k_mod, gamma_eff, delta)
        k2x, k2v = v + 0.5 * dt * k1v, a2

        a3 = acc(t + 0.5 * dt, x + 0.5 * dt * k2x, v + 0.5 * dt * k2v, k_mod, gamma_eff, delta)
        k3x, k3v = v + 0.5 * dt * k2v, a3

        a4 = acc(t + dt, x + dt * k3x, v + dt * k3v, k_mod, gamma_eff, delta)
        k4x, k4v = v + dt * k3v, a4

        x += (dt / 6.0) * (k1x + 2.0 * k2x + 2.0 * k3x + k4x)
        v += (dt / 6.0) * (k1v + 2.0 * k2v + 2.0 * k3v + k4v)
        t += dt

        # Collect metrics after burn-in
        if n > steps // 2:
            E_vals.append(energy(x, v))
            x2_vals.append(x * x)

    E_avg = statistics.fmean(E_vals) if E_vals else 0.0
    E_peak = max(E_vals) if E_vals else 0.0
    x_rms = math.sqrt(statistics.fmean(x2_vals)) if x2_vals else 0.0

    # Simple growth indicator: avg of last tenth vs first tenth of the collection window
    if len(E_vals) >= 20:
        m = len(E_vals)
        E_head = statistics.fmean(E_vals[: m // 10])
        E_tail = statistics.fmean(E_vals[- m // 10 :])
        growth_ratio = (E_tail / E_head) if E_head > 0 else float('inf')
    else:
        growth_ratio = 1.0

    return {
        'E_avg': E_avg,
        'E_peak': E_peak,
        'x_rms': x_rms,
        'growth_ratio': growth_ratio,
    }


def run_demo():
    # Choose Q to set a visible parametric threshold: m_thr ≈ 2γ0/ω0 = 1/Q0
    base = ParamParams(
        f0=60.0, Q0=300.0, beta=3e4,
        omega_drive_ratio=1.0,
        F0=0.0,
        sigma_gamma=0.0,   # remove multiplicative damping noise to isolate parametric effect
        sigma_add=1e-6,    # small additive seed
        chaos_phase_sigma=5.0,
        K_lock=3000.0, C_field=0.7, C_affect_gamma=0.6, C_affect_lock=1.0,
        G_gain=0.0,
        dt=2e-5, T=5.0,
        seed=7,
    )

    # Threshold estimate for parametric excitation near 2ω0
    m_thr = 1.0 / base.Q0  # using canonical approximation

    scenarios = [
        (0.8 * m_thr, 'Below threshold (0.8× m_thr)'),
        (1.1 * m_thr, 'Just above threshold (1.1× m_thr)'),
        (1.6 * m_thr, 'Moderately above threshold (1.6× m_thr)'),
        (2.2 * m_thr, 'Well above threshold (2.2× m_thr)'),
    ]

    # Prepare CSV output
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "parametric_results.csv")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("label,m,m_thr,E_avg_locked,E_avg_unlocked,Gain_pct,x_rms_locked,x_rms_unlocked,growth_locked,growth_unlocked,delta_growth\n")

        for m, label in scenarios:
            p = ParamParams(**{**base.__dict__, 'm_param': m})
            locked = simulate_parametric(True, p, seed=11)
            unlocked = simulate_parametric(False, p, seed=11)
            print(f"\n=== Parametric: {label}, m={m:.5f} (m_thr≈{m_thr:.5f}) ===")
            print("Locked:", locked)
            print("Unlocked:", unlocked)
            print(f"E_avg_locked={locked['E_avg']:.3e}, E_avg_unlocked={unlocked['E_avg']:.3e}, "
                  f"x_rms_locked={locked['x_rms']:.3e}, x_rms_unlocked={unlocked['x_rms']:.3e}, "
                  f"growth_locked={locked['growth_ratio']:.3f}, growth_unlocked={unlocked['growth_ratio']:.3f}")
            dE = (locked['E_avg'] - unlocked['E_avg']) / max(unlocked['E_avg'], 1e-12)
            dGrowth = locked['growth_ratio'] - unlocked['growth_ratio']
            print(f"Improvement E_avg (locked vs unlocked): {dE*100:.2f}% | growth_ratio Δ: {dGrowth:+.3f}")

            f.write(
                f"{label},{m:.9e},{m_thr:.9e},{locked['E_avg']:.9e},{unlocked['E_avg']:.9e},{dE*100:.3f},{locked['x_rms']:.9e},{unlocked['x_rms']:.9e},{locked['growth_ratio']:.6f},{unlocked['growth_ratio']:.6f},{dGrowth:.6f}\n"
            )


if __name__ == '__main__':
    run_demo()
