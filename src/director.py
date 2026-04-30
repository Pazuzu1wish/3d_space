import math
import random

from src.enemy import SuicideDrone, Dogfighter, Sniper, Corvette, Minelayer, StealthInterceptor, Carrier
from src.utils import (
    spawn_drone, spawn_dogfighter, spawn_sniper,
    spawn_corvette, spawn_minelayer, spawn_stealth_interceptor,
)
from src.constants import (
    SPAWNS_PER_SECOND, MAX_SUICIDE_DRONES, MAX_DOGFIGHTERS,
)

# ── Per-type population caps ───────────────────────────────────────────────
MAX_SNIPERS     = 2
MAX_CORVETTES   = 1
MAX_MINELAYERS  = 2
MAX_STEALTH     = 2
# Carriers are scripted-only — no filler cap needed

# ── Filler spawn table ────────────────────────────────────────────────────
# (enemy_class, spawn_fn, cap_attr, weight)
# Weight controls relative probability when multiple types are eligible.
# Higher = more likely.  Exotic types get lower weight so they feel special.
_FILLER_TABLE = [
    (SuicideDrone,       spawn_drone,                 'MAX_SUICIDE_DRONES', 3),
    (Dogfighter,         spawn_dogfighter,             'MAX_DOGFIGHTERS',    3),
    (Sniper,             spawn_sniper,                 'MAX_SNIPERS',        1),
    (Corvette,           spawn_corvette,               'MAX_CORVETTES',      1),
    (Minelayer,          spawn_minelayer,              'MAX_MINELAYERS',     1),
    (StealthInterceptor, spawn_stealth_interceptor,    'MAX_STEALTH',        2),
]

_CAPS = {
    SuicideDrone:       MAX_SUICIDE_DRONES,
    Dogfighter:         MAX_DOGFIGHTERS,
    Sniper:             MAX_SNIPERS,
    Corvette:           MAX_CORVETTES,
    Minelayer:          MAX_MINELAYERS,
    StealthInterceptor: MAX_STEALTH,
}

# ── Encounter etype → class map (for _spawn_encounter) ───────────────────
from .enemy import SuicideDrone, Dogfighter, Sniper, Corvette, Minelayer, StealthInterceptor, Carrier

_ETYPE_MAP = {
    'drone':    SuicideDrone,
    'fighter':  Dogfighter,
    'sniper':   Sniper,
    'corvette': Corvette,
    'minelayer':Minelayer,
    'stealth':  StealthInterceptor,
    'carrier':  Carrier,
}


class WaveDirector:
    """
    Owns the enemy-spawn timeline for a session.

    Scripted encounters are placed at absolute world positions; when the
    player flies within trigger_dist the encounter fires.  Between scripted
    beats the director produces procedural 'filler' at a gradually
    tightening rate.  While an encounter whose 'filler' flag is False is
    still alive, filler is suppressed so the set-piece has room to breathe.
    """

    def __init__(self, script):
        self.script  = script
        self.pending = list(script)   # encounters not yet triggered
        self.active  = []             # list of in-flight scripted groups
        self.filler_suppressed = False

        self.spawn_timer = 0.0
        self.elapsed     = 0.0

    # ──────────────────────────────────────────────────────────────
    # PUBLIC
    # ──────────────────────────────────────────────────────────────

    def update(self, dt, player_pos, player_orientation, enemies):
        self.elapsed += dt

        # ── CHECK SCRIPTED TRIGGERS ───────────────────────────────
        for enc in self.pending[:]:
            ox, oy, oz = enc['origin']
            px, py, pz = player_pos
            dist = math.sqrt((ox - px) ** 2 + (oy - py) ** 2 + (oz - pz) ** 2)

            if dist < enc['trigger_dist']:
                spawned = self._spawn_encounter(enc, player_pos, enemies)
                self.pending.remove(enc)

                if not enc.get('filler', True):
                    self.active.append({'enemies': spawned, 'filler_ok': False})
                    self.filler_suppressed = True

        # ── EXPIRE COMPLETED SCRIPTED ENCOUNTERS ──────────────────
        if self.active:
            still_alive = []
            for group in self.active:
                surviving = [e for e in group['enemies'] if e in enemies]
                if surviving:
                    group['enemies'] = surviving
                    still_alive.append(group)
            self.active = still_alive
            self.filler_suppressed = any(not g['filler_ok'] for g in self.active)

        # ── PROCEDURAL FILLER ─────────────────────────────────────
        if not self.filler_suppressed:
            self.spawn_timer += dt
            if self.spawn_timer >= self._filler_interval():
                self.spawn_timer = 0.0
                self._spawn_filler(player_pos, player_orientation, enemies)

    # ──────────────────────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────────────────────

    def _filler_interval(self):
        """Gradually tighten spawn rate over time (6 s → 2 s floor)."""
        return max(2.0, 6.0 - self.elapsed * 0.02)

    def _spawn_encounter(self, enc, player_pos, enemies):
        """Instantiate all enemies in a scripted encounter."""
        ox, oy, oz = enc['origin']
        spawned = []

        for etype, (rx, ry, rz) in enc['enemies']:
            cls = _ETYPE_MAP.get(etype)
            if cls is None:
                print(f"[WaveDirector] Unknown etype '{etype}' — skipped")
                continue

            e = cls(ox + rx, oy + ry, oz + rz)

            # Give scripted drones a sensible movement pattern
            if cls is SuicideDrone:
                lateral = math.sqrt(rx * rx + ry * ry)
                if lateral > 300:
                    e.set_pattern('weave')
                elif rz > 0:
                    e.set_pattern('direct')
                else:
                    e.set_pattern('wobble')

            enemies.append(e)
            spawned.append(e)

        return spawned

    def _spawn_filler(self, player_pos, player_orientation, enemies):
        """Weighted random filler spawn, respecting per-type caps."""
        # Count current enemies by type
        counts = {}
        for e in enemies:
            counts[type(e)] = counts.get(type(e), 0) + 1

        # Build eligible pool
        pool = []
        for cls, fn, _cap_name, weight in _FILLER_TABLE:
            cap = _CAPS.get(cls, 0)
            if counts.get(cls, 0) < cap:
                pool.extend([(cls, fn)] * weight)

        if not pool:
            return   # all caps reached

        _, spawn_fn = random.choice(pool)
        enemies.append(spawn_fn(player_pos, player_orientation))