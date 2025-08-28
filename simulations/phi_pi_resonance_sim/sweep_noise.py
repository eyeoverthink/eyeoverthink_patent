#!/usr/bin/env python3
"""
sweep_noise.py

Sweep static noise amplitude (sigma_drive) to test whether noise/chaos can
magnify energy (stochastic resonance effect) under φπ lock vs unlocked.
"""
from pprint import pprint

from phi_pi_wireless_sim import SimParams, simulate


def run():
    base = SimParams(
        f0=60.0, Q0=1000.0, beta=5e3,
        F0=1.0, omega_drive_ratio=1.0,
        sigma_drive=0.0, chaos_phase_sigma=60.0,
        K_lock=3000.0, C_field=0.7, C_affect_gamma=0.6, C_affect_lock=1.0,
        G_gain=0.0, dt=2e-5, T=0.6,
    )

    noise_levels = [0.0, 0.2, 0.4, 0.7, 1.0, 1.5, 2.0]

    rows = []
    for s in noise_levels:
        p = SimParams(**{**base.__dict__, 'sigma_drive': s})
        lock = simulate(True, p, seed=3)
        unlock = simulate(False, p, seed=3)
        rows.append({
            'sigma': s,
            'E_lock': lock['E_avg'],
            'E_unlock': unlock['E_avg'],
            'eff_lock': lock['eff_proxy'],
            'eff_unlock': unlock['eff_proxy'],
        })

    print("φπ noise sweep (sigma_drive) results:")
    for r in rows:
        print(f"sigma={r['sigma']:.2f} | E_lock={r['E_lock']:.4e}, E_unlock={r['E_unlock']:.4e}, "
              f"eff_lock={r['eff_lock']:.3f}, eff_unlock={r['eff_unlock']:.3f}")

    # Identify maxima
    best_lock = max(rows, key=lambda r: r['E_lock'])
    best_unlock = max(rows, key=lambda r: r['E_unlock'])
    print("\nMax E_avg (locked):", {k: best_lock[k] for k in best_lock})
    print("Max E_avg (unlocked):", {k: best_unlock[k] for k in best_unlock})


if __name__ == '__main__':
    run()
