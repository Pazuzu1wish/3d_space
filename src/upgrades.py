"""
src/upgrades.py

Roguelite in-run upgrade pool.

Each entry is applied once to the live Player instance when picked from the
level-up screen. Deliberately simple: no engine hooks, no per-frame cost —
just a numeric tweak to a Player attribute the combat code already reads
every frame (laser_damage, missile_damage, shield_max, etc). Picking an
upgrade is an event, not something that runs in the hot loop.
"""

import random


def _laser_damage(player):
    player.laser_damage *= 1.25


def _laser_fire_rate(player):
    player.laser_fire_cooldown = max(0.05, player.laser_fire_cooldown * 0.85)


def _laser_cooling(player):
    player.laser_heat_per_shot = max(0.02, player.laser_heat_per_shot * 0.8)


def _missile_damage(player):
    player.missile_damage *= 1.3


def _missile_capacity(player):
    player.missile_ammo_max += 2
    player.missile_ammo += 2


def _reinforced_hull(player):
    player.max_hp += 20
    player.hp = min(player.max_hp, player.hp + 20)


def _overshield(player):
    player.shield_max += 20
    player.shield = min(player.shield_max, player.shield + 20)


def _capacitor_discharge(player):
    player.shield_recharge_rate *= 1.25


def _quick_reflexes(player):
    player.dodge_cooldown_max = max(0.5, player.dodge_cooldown_max * 0.8)


def _emergency_patch(player):
    player.hp = min(player.max_hp, player.hp + 30)


# Each upgrade: id (for save/debug), display name + one-line description,
# an accent color for the level-up card, and an apply(player) callback.
UPGRADE_POOL = [
    {
        "id": "laser_damage",
        "name": "Overcharged Lasers",
        "description": "+25% laser damage per hit.",
        "color": (255, 80, 80),
        "apply": _laser_damage,
    },
    {
        "id": "laser_fire_rate",
        "name": "Rapid Cycler",
        "description": "15% faster laser fire rate.",
        "color": (255, 160, 60),
        "apply": _laser_fire_rate,
    },
    {
        "id": "laser_cooling",
        "name": "Cooling Vents",
        "description": "20% less heat buildup per shot.",
        "color": (100, 220, 255),
        "apply": _laser_cooling,
    },
    {
        "id": "missile_damage",
        "name": "Warhead Upgrade",
        "description": "+30% missile damage.",
        "color": (255, 210, 60),
        "apply": _missile_damage,
    },
    {
        "id": "missile_capacity",
        "name": "Expanded Racks",
        "description": "+2 missile capacity, refilled now.",
        "color": (255, 180, 120),
        "apply": _missile_capacity,
    },
    {
        "id": "reinforced_hull",
        "name": "Reinforced Hull",
        "description": "+20 max hull, healed to match.",
        "color": (220, 60, 60),
        "apply": _reinforced_hull,
    },
    {
        "id": "overshield",
        "name": "Overshield",
        "description": "+20 max shield capacity.",
        "color": (0, 180, 255),
        "apply": _overshield,
    },
    {
        "id": "capacitor_discharge",
        "name": "Capacitor Discharge",
        "description": "25% faster shield recharge.",
        "color": (60, 140, 255),
        "apply": _capacitor_discharge,
    },
    {
        "id": "quick_reflexes",
        "name": "Quick Reflexes",
        "description": "20% shorter dodge cooldown.",
        "color": (180, 255, 140),
        "apply": _quick_reflexes,
    },
    {
        "id": "emergency_patch",
        "name": "Emergency Patch",
        "description": "Instantly repair 30 hull.",
        "color": (120, 255, 120),
        "apply": _emergency_patch,
    },
]


def roll_upgrades(k=3):
    """Return k distinct random upgrade entries from the pool."""
    k = min(k, len(UPGRADE_POOL))
    return random.sample(UPGRADE_POOL, k)
