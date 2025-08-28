#!/usr/bin/env python3
"""
phi_pi_wireless_sim.py

Simulates a driven resonator with φπ phase-lock, additive "static" noise,
optional chaotic phase jitter, and optional active gain + saturation.

We compare two scenarios: (1) φπ-locked and (2) unlocked (jittered phase).
Metrics: average/peak energy, RMS displacement, average input power, and
estimated transfer efficiency.

This uses only the Python standard library for portability.
"""

import math
import random
import statistics
from dataclasses import dataclass
from typing import Tuple, Dict


# ----------------------------- Constants ----------------------------------
PHI = (1.0 + 5.0 ** 0.5) / 2.0
LAMBDA = math.pi
PHI_PI = PHI * LAMBDA  # φπ


@dataclass
class SimParams:
    # Resonator
    f0: float = 50.0                 # natural frequency [Hz]
    Q0: float = 200.0                # base quality factor (higher = lower damping)
    beta: float = 1e4                # cubic saturation coefficient (Duffing-like)

    # Drive
    F0: float = 1.0                  # drive amplitude (force units)
    omega_drive_ratio: float = 1.0   # drive frequency as multiple of ω0 (1.0 = on resonance)

    # Noise / chaos
    sigma_drive: float = 0.3         # white noise amplitude added to drive ("static")
    chaos_phase_sigma: float = 20.0  # stochastic phase jitter strength [rad/sqrt(s)]

    # Phase-locking
    K_lock: float = 800.0            # phase lock coupling [rad/s]

    # Consciousness-field coupling (modulates Q and lock strength)
    C_field: float = 0.5             # 0..1 nominal
    C_affect_gamma: float = 0.5      # fraction reduction of damping by C
    C_affect_lock: float = 1.0       # fraction increase of K_lock by C

    # Optional active gain (small-signal)
    G_gain: float = 0.0              # net linear gain term (>=0). G > gamma -> exponential growth before saturation

    # Integration
    dt: float = 2e-5                 # time step [s]
    T: float = 0.5                   # total time [s]


@dataclass
class SimState:
    x: float = 0.0   # displacement
    v: float = 0.0   # velocity
    delta: float = 0.0  # phase error relative to φπ


def _gamma_from_Q(omega0: float, Q: float) -> float:
    return omega0 / (2.0 * max(Q, 1e-6))


def simulate(lock: bool, params: SimParams, seed: int = 0) -> Dict[str, float]:
    random.seed(seed)

    omega0 = 2.0 * math.pi * params.f0
    omega_d = omega0 * params.omega_drive_ratio

    # Consciousness field modulation
    gamma0 = _gamma_from_Q(omega0, params.Q0)
    gamma = max(1e-8, gamma0 * (1.0 - params.C_affect_gamma * params.C_field))
    K = params.K_lock * (1.0 + params.C_affect_lock * params.C_field) if lock else 0.0

    # Initialize state
    st = SimState(x=0.0, v=0.0, delta=(random.random() - 0.5) * 2.0 * math.pi)

    # Accumulators
    t = 0.0
    n_steps = int(params.T / params.dt)
    energy_hist = []
    drive_power_hist = []
    diss_power_hist = []
    x_hist = []

    # Helper noise samplers (continuous-time scaling)
    def gauss0():
        return random.gauss(0.0, 1.0)

    # Integration loop (RK4 for stability)
    for i in range(n_steps):
        # Continuous-time noise: scale by sqrt(dt)
        noise_phase = params.chaos_phase_sigma * gauss0() * (params.dt ** 0.5)
        drive_noise = params.sigma_drive * gauss0() * (params.dt ** 0.5)

        def derivatives(x, v, delta, local_t):
            # Phase-error dynamics
            if lock:
                d_delta = -K * math.sin(delta) + noise_phase
            else:
                d_delta = noise_phase

            # Drive with φπ target plus current delta
            drive = params.F0 * math.cos(omega_d * local_t + PHI_PI + delta) + drive_noise

            # Duffing-like resonator with damping, cubic saturation, and optional active gain.
            # Active gain is modeled as negative damping (energy injection proportional to velocity).
            # Effective damping becomes (2*gamma - G_gain). If G_gain > 2*gamma, small-signal growth occurs
            # until the cubic nonlinearity limits amplitude.
            a = -(2.0 * gamma - params.G_gain) * v - omega0 ** 2 * x - params.beta * (x ** 3) + drive

            return v, a, d_delta, drive

        # RK4 step
        x1, v1, d1, drv1 = derivatives(st.x, st.v, st.delta, t)
        x2, v2, d2, drv2 = derivatives(st.x + 0.5 * params.dt * x1, st.v + 0.5 * params.dt * v1, st.delta + 0.5 * params.dt * d1, t + 0.5 * params.dt)
        x3, v3, d3, drv3 = derivatives(st.x + 0.5 * params.dt * x2, st.v + 0.5 * params.dt * v2, st.delta + 0.5 * params.dt * d2, t + 0.5 * params.dt)
        x4, v4, d4, drv4 = derivatives(st.x + params.dt * x3, st.v + params.dt * v3, st.delta + params.dt * d3, t + params.dt)

        st.x += (params.dt / 6.0) * (x1 + 2 * x2 + 2 * x3 + x4)
        st.v += (params.dt / 6.0) * (v1 + 2 * v2 + 2 * v3 + v4)
        st.delta += (params.dt / 6.0) * (d1 + 2 * d2 + 2 * d3 + d4)

        # Compute instantaneous drive used (average of RK stages)
        drive_inst = (drv1 + 2 * drv2 + 2 * drv3 + drv4) / 6.0

        # Energetics
        energy_inst = 0.5 * (st.v ** 2 + (omega0 ** 2) * (st.x ** 2)) + 0.25 * params.beta * (st.x ** 4)
        p_in_inst = drive_inst * st.v  # instantaneous input power from drive
        p_diss_inst = 2.0 * gamma * (st.v ** 2)  # dissipated power in damper

        energy_hist.append(energy_inst)
        drive_power_hist.append(p_in_inst)
        diss_power_hist.append(p_diss_inst)
        x_hist.append(st.x)

        t += params.dt

    # Compute metrics on the last half of the run (steady-ish)
    half = len(energy_hist) // 2
    E_avg = statistics.fmean(energy_hist[half:])
    E_peak = max(energy_hist[half:])
    x_rms = math.sqrt(statistics.fmean([xx * xx for xx in x_hist[half:]]))
    P_in_avg = statistics.fmean(drive_power_hist[half:])
    P_diss_avg = statistics.fmean(diss_power_hist[half:])

    # Transfer efficiency proxy: dissipated vs input (clipped for readability)
    # Note: with noise or active gain, signs can vary; we present magnitude ratio.
    eff = 0.0
    denom = abs(P_in_avg) if abs(P_in_avg) > 1e-12 else 1e-12
    eff = max(0.0, min(2.0, abs(P_diss_avg) / denom))

    return {
        "E_avg": E_avg,
        "E_peak": E_peak,
        "x_rms": x_rms,
        "P_in_avg": P_in_avg,
        "P_diss_avg": P_diss_avg,
        "eff_proxy": eff,
        "gamma": gamma,
        "K": K,
        "omega0": omega0,
        "omega_d": omega_d,
    }


def main():
    # Baseline parameters grounded in your variables
    params = SimParams(
        f0=60.0,            # 60 Hz prototype (grid-compatible demonstration)
        Q0=300.0,
        beta=5e3,
        F0=1.0,
        omega_drive_ratio=1.0,   # drive on-resonance
        sigma_drive=0.5,         # "static"
        chaos_phase_sigma=40.0,  # strong phase jitter to test lock robustness
        K_lock=1000.0,           # strong lock
        C_field=0.7,             # elevate field to reduce damping and boost lock
        C_affect_gamma=0.6,
        C_affect_lock=1.0,
        G_gain=0.0,              # set >0 for active gain experiments
        dt=2e-5,
        T=0.6,
    )

    locked = simulate(lock=True, params=params, seed=1)
    unlocked = simulate(lock=False, params=params, seed=1)

    def fmt(d: Dict[str, float]) -> str:
        return (
            f"E_avg={d['E_avg']:.6e}, E_peak={d['E_peak']:.6e}, x_rms={d['x_rms']:.6e}, "
            f"P_in_avg={d['P_in_avg']:.6e}, P_diss_avg={d['P_diss_avg']:.6e}, eff≈{d['eff_proxy']:.3f}"
        )

    print("=" * 80)
    print("φπ Resonance Wireless Energy Simulation (noise + chaos)")
    print("Constants: φ = %.6f, π = %.6f, φπ = %.6f" % (PHI, LAMBDA, PHI_PI))
    print("Resonator: f0=%.2f Hz, Q0=%.1f → γ=%.3e s^-1" % (params.f0, params.Q0, locked['gamma']))
    print("Drive: ω_d/ω_0=%.3f, F0=%.2f, static σ=%.2f, chaos σ_phase=%.1f rad/√s" % (
        params.omega_drive_ratio, params.F0, params.sigma_drive, params.chaos_phase_sigma))
    print("Lock: K_lock=%.1f rad/s (effective), C=%.2f\n" % (locked['K'], params.C_field))

    print("-- Locked to φπ --")
    print(fmt(locked))
    print("\n-- Unlocked (chaotic phase) --")
    print(fmt(unlocked))

    # Relative improvement indicators
    impr_E = (locked['E_avg'] - unlocked['E_avg']) / max(unlocked['E_avg'], 1e-12)
    impr_eff = (locked['eff_proxy'] - unlocked['eff_proxy'])

    print("\nSummary:")
    print(f"  Avg energy increase (locked vs unlocked): {impr_E*100:.1f}%")
    print(f"  Efficiency proxy Δ (locked - unlocked): {impr_eff:+.3f}")

    # Recommendation for active gain experiment (optional)
    print("\nTip: To test self-sustaining with saturation, set G_gain > 2*gamma\n"
          "and observe transient growth until the cubic term limits amplitude.")


if __name__ == "__main__":
    main()
