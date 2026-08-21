"""
src/weapon_system.py

Player weapon firing logic extracted from Player.update().

Two public functions:

    fire_lasers(player, fire_pressed, handler, laser_pool, sound)
    fire_missile(player, missile_fire_pressed, handler, player_missiles, sound)

Both read control state from player, write weapon state back to player,
and interact with the relevant pool/list.  Nothing else changes.

Call both from GameplayState.update() after player_integrate(), or keep
calling from Player.update() by delegating — either works.
"""

import math
import random

from src.math_engine import get_basis_from_quat
from src.constants import (
    PLAYER_LASER_SPEED,
    PLAYER_LASER_FIRE_SHAKE,
    PLAYER_LASER_BASE_SPREAD,
    PLAYER_LASER_MAX_SPREAD,
    PLAYER_MISSILE_SPEED,
    PLAYER_MISSILE_LIFE,
)
from src.missile import HomingMissile, PlayerMissile


# ── laser fire ────────────────────────────────────────────────────────────────

def fire_lasers(player, fire_pressed, handler, laser_pool, sound):
    """
    Fire dual wingtip lasers if conditions are met.
    Writes: player.weapons_cooldown, player.laser_heat, player.overheated,
            player.shake_queued
    """
    if not fire_pressed:
        return
    if player.weapons_cooldown > 0:
        return
    if player.overheated:
        return

    if sound:
        if player.laser_heat > 0.75:
            sound.play_sfx("laser_strained")
        else:
            sound.play_sfx("laser")

    forward, right, up = get_basis_from_quat(player.orientation)
    rfx, rfy, rfz = forward
    rrx, rry, rrz = right
    horizontal_offset = 150
    vertical_offset = -100

    current_spread = PLAYER_LASER_BASE_SPREAD + (player.laser_heat * PLAYER_LASER_MAX_SPREAD)
    laser_color = (255, 50, 50) if player.laser_heat > 0.75 else None

    for side in (-1, 1):
        # Random jitter on forward vector
        jx = (random.random() * 2 - 1) * current_spread
        jy = (random.random() * 2 - 1) * current_spread

        pfx = rfx + rrx * jx + up[0] * jy
        pfy = rfy + rry * jx + up[1] * jy
        pfz = rfz + rrz * jx + up[2] * jy

        mag = math.sqrt(pfx*pfx + pfy*pfy + pfz*pfz)
        pfx, pfy, pfz = pfx/mag, pfy/mag, pfz/mag

        wx = player.pos[0] + rrx * horizontal_offset * side + rfx * 70 + up[0] * vertical_offset
        wy = player.pos[1] + rry * horizontal_offset * side + rfy * 70 + up[1] * vertical_offset
        wz = player.pos[2] + rrz * horizontal_offset * side + rfz * 70 + up[2] * vertical_offset

        laser_pool.fire(
            wx, wy, wz,
            pfx * PLAYER_LASER_SPEED,
            pfy * PLAYER_LASER_SPEED,
            pfz * PLAYER_LASER_SPEED,
            color=laser_color,
        )
        player.shots_fired += 1

    player.weapons_cooldown = player.laser_fire_cooldown
    player.laser_heat = min(1.0, player.laser_heat + player.laser_heat_per_shot)
    if player.laser_heat >= 1.0:
        player.overheated = True

    player.shake_queued += PLAYER_LASER_FIRE_SHAKE
    handler.rumble(0.0, 0.12, 50)


# ── missile fire ──────────────────────────────────────────────────────────────

def fire_missile(player, missile_fire_pressed, handler, player_missiles, sound):
    """
    Launch a homing or dumb-fire missile if conditions are met.
    Writes: player.missile_ammo, player.missile_lock_timer, player.missile_locked
    """
    if not missile_fire_pressed:
        return
    if player.missile_ammo <= 0:
        return

    if sound:
        sound.play_sfx("missile")

    forward, right, _ = get_basis_from_quat(player.orientation)
    rfx, rfy, rfz = forward

    wx = player.pos[0] + rfx * 50
    wy = player.pos[1] + rfy * 50
    wz = player.pos[2] + rfz * 50
    vx = rfx * PLAYER_MISSILE_SPEED
    vy = rfy * PLAYER_MISSILE_SPEED
    vz = rfz * PLAYER_MISSILE_SPEED

    if player.missile_locked and player.active_target:
        m = HomingMissile(
            wx, wy, wz, vx, vy, vz,
            PLAYER_MISSILE_LIFE, player.missile_damage,
            player.active_target,
        )
    else:
        m = PlayerMissile(
            wx, wy, wz, vx, vy, vz,
            PLAYER_MISSILE_LIFE, player.missile_damage,
            homing=False,
        )

    player_missiles.append(m)
    player.missile_ammo -= 1
    player.missile_lock_timer = 0.0
    player.missile_locked = False
    handler.rumble(0.2, 0.2, 100)