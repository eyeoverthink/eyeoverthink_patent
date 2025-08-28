#!/usr/bin/env python3
"""
ascii_phi_pi.py

Interactive ASCII φπ resonance demo (terminal, curses-based, stdlib only).
- Simulates a small 2D wave grid with φπ-phase drive and noise/chaos.
- Toggle lock, adjust detuning, amplitude, and damping.
- Visualizes confinement vs open boundary by toggling mode.

Controls:
  q        quit
  l        toggle φπ lock on/off
  b        toggle boundary mode (confined/open)
  + / -    adjust detuning (ωd/ω0)
  a / z    increase/decrease drive amplitude A
  d / s    increase/decrease interior damping γ
  h        show help

Notes:
- Rendering uses coarse ASCII with intensity mapped to characters.
- Keep terminal reasonably large (e.g., 100x35) for best view.
"""
from __future__ import annotations
import curses
import math
import random
import time

PHI = (1.0 + 5.0 ** 0.5) / 2.0
PHI_PI = PHI * math.pi

class Sim2D:
    def __init__(self, W=60, H=24):
        self.W = W
        self.H = H
        self.dx = 1.0
        self.dt = 0.45
        self.c = 1.0
        self.r = self.c * self.dt / self.dx
        # state
        self.u_prev = [[0.0]*W for _ in range(H)]
        self.u = [[0.0]*W for _ in range(H)]
        self.u_next = [[0.0]*W for _ in range(H)]
        # params
        self.A = 0.8
        self.f_cycles = 0.02
        self.omega = 2.0*math.pi*self.f_cycles
        self.phase = PHI_PI
        self.sigma_amp = 0.10
        self.phase_jitter = 0.02
        self.gamma_interior = 1.5e-3
        self.lock_on = True
        self.detune = 1.00  # ωd/ω0
        self.boundary = 'confined'  # or 'open'
        # source location
        self.sy = H//2
        self.sx = W//2
        random.seed(7)

    def step(self, n):
        # phase update; emulate lock by reducing random walk toward 0 phase error
        jitter = self.phase_jitter * random.gauss(0, 1)
        if self.lock_on:
            self.phase += -0.15*math.sin(self.phase - PHI_PI) + jitter
        else:
            self.phase += jitter
        amp_noise = 1.0 + self.sigma_amp * random.gauss(0, 1)
        s = self.A * amp_noise * math.sin(self.detune*self.omega * n + self.phase)
        r2 = self.r*self.r
        H, W = self.H, self.W
        # update interior
        for y in range(1, H-1):
            up = self.u[y-1]
            uc = self.u[y]
            dn = self.u[y+1]
            nx = self.u_next[y]
            pv = self.u_prev[y]
            for x in range(1, W-1):
                lap = (uc[x-1] + uc[x+1] + up[x] + dn[x] - 4.0*uc[x])
                g = self.gamma_interior
                nx[x] = ((2 - 2*g*self.dt)*uc[x] - (1 - g*self.dt)*pv[x] + r2*lap)
        # source
        self.u_next[self.sy][self.sx] += (self.dt*self.dt) * s
        # boundaries
        if self.boundary == 'confined':
            for x in range(W):
                self.u_next[0][x] = 0.0
                self.u_next[H-1][x] = 0.0
            for y in range(H):
                self.u_next[y][0] = 0.0
                self.u_next[y][W-1] = 0.0
        else:
            # simple absorbing: copy neighbor inward
            for x in range(W):
                self.u_next[0][x] = self.u[1][x]
                self.u_next[H-1][x] = self.u[H-2][x]
            for y in range(H):
                self.u_next[y][0] = self.u[y][1]
                self.u_next[y][W-1] = self.u[y][W-2]
        # rotate
        self.u_prev, self.u, self.u_next = self.u, self.u_next, self.u_prev

    def snapshot(self):
        # return grid for rendering
        return self.u

CHARS = " .:-=+*#%@"

def render_ascii(stdscr, grid, info: str):
    H = len(grid)
    W = len(grid[0]) if H else 0
    # compute scale
    vmax = 1e-9
    for y in range(1, H-1):
        for x in range(1, W-1):
            vmax = max(vmax, abs(grid[y][x]))
    vmax = max(vmax, 1e-6)
    # draw
    for y in range(H):
        line = []
        for x in range(W):
            v = grid[y][x]
            a = min(1.0, abs(v)/vmax)
            idx = int(a * (len(CHARS)-1))
            ch = CHARS[idx]
            line.append(ch)
        stdscr.addstr(y, 0, ''.join(line))
    stdscr.addstr(min(H, 28), 0, info[:max(0, W-1)])

HELP = "l:lock b:boundary +/-:detune a/z:A d/s:gamma q:quit h:help"

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    maxy, maxx = stdscr.getmaxyx()
    H = min(24, maxy-6)
    W = min(80, maxx-1)
    sim = Sim2D(W=W, H=H)
    last_help = 0
    n = 0
    while True:
        # input
        try:
            ch = stdscr.getch()
        except Exception:
            ch = -1
        if ch != -1:
            if ch in (ord('q'), 27):
                break
            elif ch == ord('l'):
                sim.lock_on = not sim.lock_on
            elif ch == ord('b'):
                sim.boundary = 'open' if sim.boundary == 'confined' else 'confined'
            elif ch == ord('+'):
                sim.detune += 0.01
            elif ch == ord('-'):
                sim.detune -= 0.01
            elif ch == ord('a'):
                sim.A *= 1.05
            elif ch == ord('z'):
                sim.A /= 1.05
            elif ch == ord('d'):
                sim.gamma_interior *= 1.1
            elif ch == ord('s'):
                sim.gamma_interior /= 1.1
            elif ch == ord('h'):
                last_help = time.time()
        # step and render
        sim.step(n)
        grid = sim.snapshot()
        info = f"lock={'ON' if sim.lock_on else 'off'}  boundary={sim.boundary}  detune={sim.detune:.3f}  A={sim.A:.2f}  gamma={sim.gamma_interior:.2e}  {HELP}"
        render_ascii(stdscr, grid, info)
        if time.time() - last_help < 2.0:
            stdscr.addstr(sim.H+1, 0, HELP)
        stdscr.refresh()
        n += 1
        time.sleep(0.01)

if __name__ == '__main__':
    curses.wrapper(main)
