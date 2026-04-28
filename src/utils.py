import math
import random
import pygame
from .math_engine import get_forward_from_quat
from .enemy import SuicideDrone, Dogfighter, Sniper, Corvette, Minelayer, StealthInterceptor, Carrier
from .constants import (
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
    return SuicideDrone(*_forward_spawn_pos(player_pos, orientation))


def spawn_dogfighter(player_pos, orientation):
    return Dogfighter(*_forward_spawn_pos(player_pos, orientation))


def spawn_sniper(player_pos, orientation):
    """
    Snipers hang back further than normal enemies so their railgun
    has room to telegraph.  Spawns at 1.4–1.7× the normal distance.
    """
    return Sniper(*_forward_spawn_pos(
        player_pos, orientation,
        dist_min=int(SPAWN_DIST_MIN * 1.4),
        dist_max=int(SPAWN_DIST_MAX * 1.7),
        height_range=SPAWN_HEIGHT_RANGE * 0.6,   # less vertical scatter
    ))


def spawn_corvette(player_pos, orientation):
    """
    Corvettes spawn at standard range but with a tighter yaw cone
    so they appear roughly dead-ahead — hard to miss.
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
    return Minelayer(*pos)


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
    return StealthInterceptor(*pos)


def spawn_carrier(player_pos, orientation):
    """
    Carriers are boss-scale — spawn far ahead and slightly above so
    they dominate the horizon.
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

def draw_damage_overlay(screen, W, H, intensity):
    """Red vignette that fades in when the player is hit."""
    if intensity <= 0:
        return
    alpha = int(min(200, intensity * 200))
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.rect(overlay, (220, 20, 20, alpha), (0, 0, W, H))
    screen.blit(overlay, (0, 0))