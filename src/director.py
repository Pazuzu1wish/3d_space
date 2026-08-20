import random

from src.utils import (
    spawn_drone, spawn_dogfighter, spawn_sniper,
    spawn_corvette, spawn_minelayer, spawn_stealth_interceptor, spawn_carrier,
)

# ── Wave roster ─────────────────────────────────────────────────────────────
# (etype key, spawn_fn, cost, unlock_wave, weight)
#   cost         — how much of a wave's difficulty budget one spawn consumes
#   unlock_wave  — first wave number this type is allowed to appear in
#   weight       — relative pick chance among types currently affordable
#
# Cheap, weak types dominate early waves; expensive, dangerous types only
# become available (and only then compete for a spawn slot) as the wave
# count climbs, which is what makes the run start easy and steadily escalate.
_WAVE_ROSTER = [
    ('drone',     spawn_drone,               1,  1, 5),
    ('fighter',   spawn_dogfighter,          2,  2, 4),
    ('sniper',    spawn_sniper,              2,  3, 2),
    ('stealth',   spawn_stealth_interceptor, 2,  4, 3),
    ('minelayer', spawn_minelayer,           3,  6, 2),
    ('corvette',  spawn_corvette,            5,  8, 1),
    ('carrier',   spawn_carrier,             10, 12, 1),
]


class WaveDirector:
    """
    Owns the endless Arcade Mode wave timeline.

    There is no fixed script and no distant objective to fly to — every
    wave is generated procedurally and spawned around wherever the player
    happens to be the moment the previous wave is cleared, so the action
    always comes to the player instead of the player having to go find it.

    Each wave is tuned to be a little harder than the last: bigger spawn
    budgets, tougher enemy types unlocking as the run goes on, and a
    shrinking rest period between waves (floored so it never disappears).
    """

    INTERMISSION_START = 4.0   # breather before wave 1 spawns
    INTERMISSION_FLOOR = 1.5   # rest period never drops below this

    def __init__(self, script=None):
        # `script` is accepted (and ignored) for backwards compatibility —
        # endless mode has no fixed encounter list to run through.
        self.wave_number = 0
        self.active_enemies = []      # enemies belonging to the current wave
        self.wave_active = False
        self.intermission_timer = self.INTERMISSION_START

        # `pending` / `filler_suppressed` are kept so ShipAI's existing
        # voice-line state machine keeps working unmodified:
        #   - `pending` shrinks the instant a new wave spawns, which is
        #     what triggers the "wave incoming" call-out.
        #   - `filler_suppressed` is True while the current wave's enemies
        #     are still alive, and flips back to False the moment the wave
        #     is cleared, which triggers the "wave cleared" call-out.
        self.pending = [1]
        self.filler_suppressed = False

        self.elapsed = 0.0
        self.kills = []   # list of type name strings, appended in state.py

    # ──────────────────────────────────────────────────────────────
    # PUBLIC
    # ──────────────────────────────────────────────────────────────

    def update(self, dt, player_pos, player_orientation, enemies):
        self.elapsed += dt

        if self.wave_active:
            # Track only the enemies that are still alive from this wave
            self.active_enemies = [e for e in self.active_enemies if e in enemies]
            if not self.active_enemies:
                self._end_wave()
        else:
            self.intermission_timer -= dt
            if self.intermission_timer <= 0:
                self._start_wave(player_pos, player_orientation, enemies)

    # ──────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────

    def _end_wave(self):
        self.wave_active = False
        self.filler_suppressed = False
        self.intermission_timer = self._intermission_for(self.wave_number)
        self.pending = [1]   # queue the next wave back up for the incoming call-out

    def _start_wave(self, player_pos, player_orientation, enemies):
        self.wave_number += 1
        composition = self._build_wave(self.wave_number)

        spawned = []
        for etype, spawn_fn in composition:
            # Every spawn_fn positions its enemy relative to the CURRENT
            # player position/orientation — this is what makes the new
            # wave arrive near wherever the player is right now, rather
            # than at some fixed point on the map.
            e = spawn_fn(player_pos, player_orientation)
            self._maybe_add_shield(e, etype, self.wave_number)
            enemies.append(e)
            spawned.append(e)

        self.active_enemies = spawned
        self.wave_active = True
        self.filler_suppressed = True
        self.pending = []   # the queued wave just triggered

    def _intermission_for(self, wave_number):
        """Rest period between waves — shrinks with wave count, floored."""
        return max(self.INTERMISSION_FLOOR, self.INTERMISSION_START - wave_number * 0.15)

    def _wave_budget(self, wave_number):
        """Total 'threat' this wave is allowed to spend on enemies. Grows every wave."""
        return 2.0 + wave_number * 1.3

    def _max_wave_size(self, wave_number):
        """Hard cap on simultaneous spawns so late waves stay smooth to run."""
        return min(4 + wave_number // 2, 18)

    def _build_wave(self, wave_number):
        """Randomly compose a wave from the roster, spending the wave's budget."""
        budget = self._wave_budget(wave_number)
        max_size = self._max_wave_size(wave_number)
        eligible = [row for row in _WAVE_ROSTER if row[3] <= wave_number]

        composition = []
        while budget > 0 and len(composition) < max_size:
            pool = [row for row in eligible if row[2] <= budget]
            if not pool:
                break
            etype, spawn_fn, cost, _unlock, _weight = random.choices(
                pool, weights=[row[4] for row in pool], k=1
            )[0]
            composition.append((etype, spawn_fn))
            budget -= cost

        if not composition:
            # Safety net — always spawn at least one enemy.
            composition.append(('drone', spawn_drone))

        return composition

    def _maybe_add_shield(self, enemy, etype, wave_number):
        chance = self._shield_chance(wave_number, etype)
        if random.random() >= chance:
            return

        strength = self._shield_strength(enemy, wave_number, etype)
        enemy.set_shielded(strength)

    def _shield_chance(self, wave_number, etype):
        if wave_number < 4:
            return 0.0

        base = min(0.55, (wave_number - 3) * 0.045)
        type_bonus = {
            'drone': -0.12,
            'fighter': 0.00,
            'sniper': 0.05,
            'stealth': 0.08,
            'minelayer': 0.10,
            'corvette': 0.18,
            'carrier': 0.30,
        }.get(etype, 0.0)

        return max(0.0, min(0.85, base + type_bonus))

    def _shield_strength(self, enemy, wave_number, etype):
        base = max(2.0, enemy.max_hp * 0.35 + enemy.hit_radius * 0.025)
        wave_scale = 1.0 + min(1.5, (wave_number - 4) * 0.08)
        type_scale = {
            'drone': 0.75,
            'fighter': 1.0,
            'sniper': 0.8,
            'stealth': 0.9,
            'minelayer': 1.1,
            'corvette': 1.35,
            'carrier': 1.8,
        }.get(etype, 1.0)
        return min(125.0, base * wave_scale * type_scale)
