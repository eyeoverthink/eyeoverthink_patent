#!/usr/bin/env python3
"""
sweep_phi_pi.py

Runs a small parameter sweep to compare φπ-locked vs unlocked resonator
under noise/chaos, with optional active gain relative to damping.
"""
from math import pi
from pprint import pprint

from phi_pi_wireless_sim import SimParams, simulate, _gamma_from_Q


def compute_gamma(p: SimParams) -> float:
    omega0 = 2.0 * pi * p.f0
    gamma0 = _gamma_from_Q(omega0, p.Q0)
    gamma = max(1e-8, gamma0 * (1.0 - p.C_affect_gamma * p.C_field))
    return gamma


def run_pair(name: str, base: SimParams):
    locked = simulate(True, base, seed=2)
    unlocked = simulate(False, base, seed=2)
    def fmt(d):
        return {
            'E_avg': d['E_avg'], 'E_peak': d['E_peak'], 'x_rms': d['x_rms'],
            'P_in_avg': d['P_in_avg'], 'P_diss_avg': d['P_diss_avg'], 'eff_proxy': d['eff_proxy']
        }
    print(f"\n=== {name} ===")
    print("Locked:")
    pprint(fmt(locked))
    print("Unlocked:")
    pprint(fmt(unlocked))
    impr_E = (locked['E_avg'] - unlocked['E_avg']) / max(unlocked['E_avg'], 1e-12)
    impr_eff = locked['eff_proxy'] - unlocked['eff_proxy']
    print(f"Improvement E_avg: {impr_E*100:.2f}%  |  Δeff: {impr_eff:+.3f}")


def main():
    # Baseline (passive)
    p_base = SimParams(
        f0=60.0, Q0=300.0, beta=5e3,
        F0=1.0, omega_drive_ratio=1.0,
        sigma_drive=0.5, chaos_phase_sigma=40.0,
        K_lock=1000.0, C_field=0.7, C_affect_gamma=0.6, C_affect_lock=1.0,
        G_gain=0.0, dt=2e-5, T=0.6,
    )
    run_pair("Passive baseline", p_base)

    # Passive high-Q, stronger lock
    p_highQ = SimParams(**{**p_base.__dict__, 'Q0': 2000.0, 'K_lock': 4000.0})
    run_pair("Passive high-Q strong lock", p_highQ)

    # Active: set G_gain > 2*gamma to demonstrate growth then saturation
    gamma_highQ = compute_gamma(p_highQ)
    p_active22 = SimParams(**{**p_highQ.__dict__, 'G_gain': 2.2*gamma_highQ})
    run_pair("Active gain 2.2*gamma (saturating)", p_active22)

    p_active30 = SimParams(**{**p_highQ.__dict__, 'G_gain': 3.0*gamma_highQ})
    run_pair("Active gain 3.0*gamma (saturating)", p_active30)

    # Detuned drive: lock should mitigate phase noise sensitivity
    p_detune = SimParams(**{**p_base.__dict__,
                            'omega_drive_ratio': 0.98,
                            'K_lock': 2000.0,
                            'Q0': 1000.0,
                            'sigma_drive': 1.0,
                            'chaos_phase_sigma': 120.0})
    run_pair("Detuned drive (ω_d=0.98 ω0), high noise", p_detune)


if __name__ == "__main__":
    main()
