import math
import random
import pygame
from src.math_engine import get_forward_from_quat
from src.enemy import SuicideDrone, Dogfighter, Sniper, Corvette, Minelayer, StealthInterceptor, Carrier
from src.constants import (
    SPAWN_YAW_SPREAD,
    SPAWN_DIST_MIN,
    SPAWN_DIST_MAX,
    SPAWN_HEIGHT_RANGE,
    PLAYER_MAX_HP
)

# ──────────────────────────────────────────────
# SPAWN HELPERS
# ──────────────────────────────────────────────

def _forward_spawn_pos(player_pos, orientation,
                       dist_min=SPAWN_DIST_MIN, dist_max=SPAWN_DIST_MAX,
                       yaw_spread=SPAWN_YAW_SPREAD,
                       height_range=SPAWN_HEIGHT_RANGE):
    """
    Shared geometry for all forward-arc spawns.
    Returns (x, y, z) — a world position ahead of the player
    within the yaw cone, at a random elevation offset.
    """
    fx, _, fz = get_forward_from_quat(orientation)

    # Flatten to XZ and normalise
    flat_len = math.sqrt(fx * fx + fz * fz) or 1.0
    fx /= flat_len
    fz /= flat_len

    yaw_offset = random.uniform(-yaw_spread, yaw_spread)
    cos_y, sin_y = math.cos(yaw_offset), math.sin(yaw_offset)
    sfx = fx * cos_y - fz * sin_y
    sfz = fx * sin_y + fz * cos_y

    dist          = random.uniform(dist_min, dist_max)
    height_offset = random.uniform(-height_range, height_range)

    return (
        player_pos[0] + sfx * dist,
        player_pos[1] + height_offset,
        player_pos[2] + sfz * dist,
    )


def spawn_drone(player_pos, orientation):
    e = SuicideDrone(*_forward_spawn_pos(player_pos, orientation))
    # Warp-in flash for spawned enemies (fade timer in seconds)
    e.warp_flash_timer = 0.8
    e.warp_flash_total = 0.8
    return e


def spawn_dogfighter(player_pos, orientation):
    e = Dogfighter(*_forward_spawn_pos(player_pos, orientation))
    e.warp_flash_timer = 0.9
    e.warp_flash_total = 0.9
    return e


def spawn_sniper(player_pos, orientation):
    """
    Snipers hang back further than normal enemies so their railgun
    has room to telegraph.  Spawns at 1.4–1.7× the normal distance.
    """
    e = Sniper(*_forward_spawn_pos(
        player_pos, orientation,
        dist_min=int(SPAWN_DIST_MIN * 1.4),
        dist_max=int(SPAWN_DIST_MAX * 1.7),
        height_range=SPAWN_HEIGHT_RANGE * 0.6,   # less vertical scatter
    ))
    e.warp_flash_timer = 1.0
    e.warp_flash_total = 1.0
    return e


def spawn_corvette(player_pos, orientation):
    """
    Corvettes spawn at standard range but with a tighter yaw cone
    so they appear roughly dead-ahead — hard to miss.
    Corvettes intentionally do NOT get the warp flash.
    """
    return Corvette(*_forward_spawn_pos(
        player_pos, orientation,
        yaw_spread=SPAWN_YAW_SPREAD * 0.5,
        height_range=SPAWN_HEIGHT_RANGE * 0.4,
    ))


def spawn_minelayer(player_pos, orientation):
    """
    Minelayers enter from the side (large yaw offset) so they can
    cut across the player's flight path.
    """
    pos = _forward_spawn_pos(
        player_pos, orientation,
        yaw_spread=math.pi * 0.45,              # nearly 90° either side
        height_range=SPAWN_HEIGHT_RANGE * 0.5,
    )
    e = Minelayer(*pos)
    e.warp_flash_timer = 0.7
    e.warp_flash_total = 0.7
    return e


def spawn_stealth_interceptor(player_pos, orientation):
    """
    Stealth Interceptors sneak in from the flanks at close-ish range
    so their de-cloak burst matters.
    """
    pos = _forward_spawn_pos(
        player_pos, orientation,
        dist_min=int(SPAWN_DIST_MIN * 0.8),
        dist_max=int(SPAWN_DIST_MAX * 0.9),
        yaw_spread=math.pi * 0.4,
    )
    e = StealthInterceptor(*pos)
    e.warp_flash_timer = 0.6
    e.warp_flash_total = 0.6
    return e


def spawn_carrier(player_pos, orientation):
    """
    Carriers are boss-scale — spawn far ahead and slightly above so
    they dominate the horizon.
    Carriers do not get the warp flash.
    """
    return Carrier(*_forward_spawn_pos(
        player_pos, orientation,
        dist_min=int(SPAWN_DIST_MAX * 1.8),
        dist_max=int(SPAWN_DIST_MAX * 2.2),
        yaw_spread=SPAWN_YAW_SPREAD * 0.3,
        height_range=SPAWN_HEIGHT_RANGE * 0.3,
    ))


# ──────────────────────────────────────────────
# FACTORY  (used by director for filler spawns)
# ──────────────────────────────────────────────

_SPAWN_FUNCS = {
    'drone':     spawn_drone,
    'fighter':   spawn_dogfighter,
    'sniper':    spawn_sniper,
    'corvette':  spawn_corvette,
    'minelayer': spawn_minelayer,
    'stealth':   spawn_stealth_interceptor,
    'carrier':   spawn_carrier,
}

def spawn_enemy(etype, player_pos, orientation):
    """Generic factory — maps a string type to the right spawn function."""
    fn = _SPAWN_FUNCS.get(etype)
    if fn is None:
        raise ValueError(f"Unknown enemy type: '{etype}'")
    return fn(player_pos, orientation)


# ──────────────────────────────────────────────
# UI HELPERS
# ──────────────────────────────────────────────

_DAMAGE_OVERLAY = None

def draw_damage_overlay(screen, W, H, intensity):
    """Red vignette that fades in when the player is hit."""
    global _DAMAGE_OVERLAY
    if intensity <= 0:
        return
    if _DAMAGE_OVERLAY is None or _DAMAGE_OVERLAY.get_size() != (W, H):
        _DAMAGE_OVERLAY = pygame.Surface((W, H), pygame.SRCALPHA)
    alpha = int(min(200, intensity * 200))
    _DAMAGE_OVERLAY.fill((220, 20, 20, alpha))
    screen.blit(_DAMAGE_OVERLAY, (0, 0))

# ──────────────────────────────────────────────
# Fix winding helper
# ──────────────────────────────────────────────

def fix_winding(verts, faces):
    fixed = []
    for face in faces:
        v0, v1, v2 = [verts[i] for i in face]

        dx1, dy1, dz1 = v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2]
        dx2, dy2, dz2 = v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2]

        nx = dy1 * dz2 - dz1 * dy2
        ny = dz1 * dx2 - dx1 * dz2
        nz = dx1 * dy2 - dy1 * dx2

        # Assume outward normals should point away from origin
        cx = (v0[0] + v1[0] + v2[0]) / 3
        cy = (v0[1] + v1[1] + v2[1]) / 3
        cz = (v0[2] + v1[2] + v2[2]) / 3

        dot = nx * cx + ny * cy + nz * cz

        if dot < 0:
            fixed.append((face[0], face[2], face[1]))  # flip
        else:
            fixed.append(face)

    return fixed


