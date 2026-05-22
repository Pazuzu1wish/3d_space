"""
src/physics.py

Shared flight model functions.  Both take an object with the right fields
and write back to it — no subclassing required.

  newtonian_integrate  — AI flight model (enemy ships, future friendly ships)
  player_integrate     — Player flight model (proportional speed controller)

Any ship that has the right attribute set can use either model.

newtonian_integrate requires:
    forward, right, up  (tuple basis vectors, written back each call)
    vx, vy, vz          (velocity components, written back each call)
    x, y, z             (position, written back each call)
    thrust, drag, max_speed, turn_rate  (physics params, read-only)

player_integrate requires:
    vel   (list [vx, vy, vz], written back each call)
    pos   (list [x, y, z], written back each call)
    throttle, drift_mode  (control state, read-only)
    — constants MAX_THRUST, MAX_RETRO_THRUST, DRAG, MAX_SPEED read from
      src.constants so they stay in one place
"""

import math

from src.constants import (
    MAX_THRUST,
    MAX_RETRO_THRUST,
    DRAG,
    MAX_SPEED,
)
from src.math_engine import get_forward_from_quat, basis_from_forward


# ── AI / newtonian flight model ───────────────────────────────────────────────

def newtonian_integrate(ship, desired_heading, dt, lateral_force=None):
    """
    Rotate nose toward desired_heading at ship.turn_rate, fire main thrust,
    apply optional world-space lateral_force, drag, speed cap, integrate.

    Writes back: ship.forward, ship.right, ship.up, ship.vx/vy/vz, ship.x/y/z
    """
    hx, hy, hz = desired_heading
    fx, fy, fz = ship.forward

    # 1. Rotate forward toward desired heading (clamped by turn_rate)
    dot = max(-1.0, min(1.0, hx*fx + hy*fy + hz*fz))
    angle = math.acos(dot)
    max_turn = ship.turn_rate * dt
    if angle > 1e-4:
        t = min(1.0, max_turn / angle)
        nx = fx + (hx - fx) * t
        ny = fy + (hy - fy) * t
        nz = fz + (hz - fz) * t
        n = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
        fx, fy, fz = nx/n, ny/n, nz/n
    ship.forward = (fx, fy, fz)

    # 2. Rebuild right / up from new forward
    temp_up = (0, 1, 0) if abs(fy) < 0.99 else (1, 0, 0)
    rx = fy * temp_up[2] - fz * temp_up[1]
    ry = fz * temp_up[0] - fx * temp_up[2]
    rz = fx * temp_up[1] - fy * temp_up[0]
    rlen = math.sqrt(rx*rx + ry*ry + rz*rz) or 1.0
    ship.right = (rx/rlen, ry/rlen, rz/rlen)
    ship.up = (
        ship.right[1]*fz - ship.right[2]*fy,
        ship.right[2]*fx - ship.right[0]*fz,
        ship.right[0]*fy - ship.right[1]*fx,
    )

    # 3. Main thrust along current (rotated) forward
    accel = ship.thrust * dt
    ship.vx += fx * accel
    ship.vy += fy * accel
    ship.vz += fz * accel

    # 4. Optional world-space lateral force (pattern impulses, circling, etc.)
    if lateral_force is not None:
        ship.vx += lateral_force[0] * dt
        ship.vy += lateral_force[1] * dt
        ship.vz += lateral_force[2] * dt

    # 5. Drag
    d = max(0.0, 1.0 - ship.drag * dt)
    ship.vx *= d
    ship.vy *= d
    ship.vz *= d

    # 6. Speed cap
    spd_sq = ship.vx**2 + ship.vy**2 + ship.vz**2
    if spd_sq > ship.max_speed**2:
        s = ship.max_speed / math.sqrt(spd_sq)
        ship.vx *= s
        ship.vy *= s
        ship.vz *= s

    # 7. Integrate position
    ship.x += ship.vx * dt
    ship.y += ship.vy * dt
    ship.z += ship.vz * dt


# ── Player flight model ───────────────────────────────────────────────────────

def player_integrate(ship, dt):
    """
    Proportional speed controller on the ship's forward axis.
    Drift mode bypasses thrust entirely — only drag and inertia apply.

    Reads:  ship.orientation (quat), ship.throttle, ship.drift_mode,
            ship.vel (list), ship.pos (list)
    Writes: ship.vel, ship.pos
    """
    fx, fy, fz = get_forward_from_quat(ship.orientation)

    if ship.drift_mode:
        accel = 0.0
    else:
        target_fwd_speed  = ship.throttle * MAX_SPEED
        current_fwd_speed = ship.vel[0]*fx + ship.vel[1]*fy + ship.vel[2]*fz

        # Proportional controller — 250 ms time constant with drag compensation
        time_constant  = 0.25
        required_accel = (
            (target_fwd_speed - current_fwd_speed) / time_constant
            + current_fwd_speed * DRAG
        )

        # Clamp to engine capability
        if required_accel >= 0:
            accel = min(required_accel, MAX_THRUST)
        else:
            accel = max(required_accel, -MAX_RETRO_THRUST)

    # Thrust
    ship.vel[0] += fx * accel * dt
    ship.vel[1] += fy * accel * dt
    ship.vel[2] += fz * accel * dt

    # Drag (isotropic — affects all axes so lateral velocity bleeds off)
    ship.vel[0] -= ship.vel[0] * DRAG * dt
    ship.vel[1] -= ship.vel[1] * DRAG * dt
    ship.vel[2] -= ship.vel[2] * DRAG * dt

    # Speed cap
    speed_sq = ship.vel[0]**2 + ship.vel[1]**2 + ship.vel[2]**2
    if speed_sq > MAX_SPEED**2:
        speed = math.sqrt(speed_sq)
        ship.vel[0] = (ship.vel[0] / speed) * MAX_SPEED
        ship.vel[1] = (ship.vel[1] / speed) * MAX_SPEED
        ship.vel[2] = (ship.vel[2] / speed) * MAX_SPEED

    # Integrate position
    ship.pos[0] += ship.vel[0] * dt
    ship.pos[1] += ship.vel[1] * dt
    ship.pos[2] += ship.vel[2] * dt


# ── Shared helpers ────────────────────────────────────────────────────────────

def approaching_too_fast(ship, target_pos, brake_threshold=600.0):
    """
    True when close to target and still closing fast.
    Used by AI to decide when to flip and brake.
    Kept here so it travels with the physics module rather than living on Enemy.
    """
    dx = target_pos[0] - ship.x
    dy = target_pos[1] - ship.y
    dz = target_pos[2] - ship.z
    dist = math.sqrt(dx*dx + dy*dy + dz*dz) or 1.0
    approach_rate = (ship.vx*dx + ship.vy*dy + ship.vz*dz) / dist
    return dist < brake_threshold and approach_rate > 60.0


def update_orientation_from_velocity(ship):
    """
    Rebuild forward/right/up basis from current velocity vector.
    Used by ships that don't actively steer (kinematic, cinematic).
    """
    spd = math.sqrt(ship.vx**2 + ship.vy**2 + ship.vz**2)
    if spd > 1e-3:
        ship.forward, ship.right, ship.up = basis_from_forward(
            (ship.vx, ship.vy, ship.vz)
        )