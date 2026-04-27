import math
import random

from .enemy import SuicideDrone, Dogfighter
from .utils import spawn_drone, spawn_dogfighter
from .constants import (
    SPAWNS_PER_SECOND, MAX_SUICIDE_DRONES, MAX_DOGFIGHTERS,
)


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
        self.script   = script
        self.pending  = list(script)    # encounters not yet triggered
        self.active   = []              # list of sets-of-enemies still alive
        self.filler_suppressed = False

        # Procedural filler state
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
            dist = math.sqrt((ox-px)**2 + (oy-py)**2 + (oz-pz)**2)

            if dist < enc['trigger_dist']:
                spawned = self._spawn_encounter(enc, player_pos, enemies)
                self.pending.remove(enc)

                if not enc.get('filler', True):
                    # Track this group so we know when it is cleared
                    self.active.append({'enemies': spawned, 'filler_ok': False})
                    self.filler_suppressed = True

        # ── EXPIRE COMPLETED SCRIPTED ENCOUNTERS ─────────────────
        if self.active:
            still_alive = []
            for group in self.active:
                # Keep enemies that are still in the global enemies list
                surviving = [e for e in group['enemies'] if e in enemies]
                if surviving:
                    group['enemies'] = surviving
                    still_alive.append(group)
                # else: all dead — group is done

            self.active = still_alive

            # Re-evaluate suppression — suppress only while any
            # non-filler group is still alive
            self.filler_suppressed = any(
                not g['filler_ok'] for g in self.active
            )

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
        """Spawn all enemies in an encounter; return list of spawned objects."""
        ox, oy, oz = enc['origin']
        px, py, pz = player_pos
        spawned = []

        for (etype, (rx, ry, rz)) in enc['enemies']:
            pos = (ox + rx, oy + ry, oz + rz)

            if etype == 'drone':
                e = SuicideDrone(*pos)
                # Assign pattern based on where the drone sits relative to
                # the encounter origin vs. the player's approach direction.
                # Drones off to the sides get weave; those directly ahead get
                # a more aggressive direct approach.
                lateral = math.sqrt(rx*rx + ry*ry)
                if lateral > 300:
                    e.set_pattern('weave')
                elif rz > 0:
                    # Behind the player's expected approach — intercept
                    e.set_pattern('direct')
                else:
                    e.set_pattern('wobble')

            elif etype == 'fighter':
                e = Dogfighter(*pos)
            else:
                continue

            enemies.append(e)
            spawned.append(e)

        return spawned

    def _spawn_filler(self, player_pos, player_orientation, enemies):
        """Procedural background spawning — mirrors the old game.py logic."""
        num_drones   = sum(1 for e in enemies if isinstance(e, SuicideDrone))
        num_fighters = sum(1 for e in enemies if isinstance(e, Dogfighter))

        can_drone   = num_drones   < MAX_SUICIDE_DRONES
        can_fighter = num_fighters < MAX_DOGFIGHTERS

        if can_drone and can_fighter:
            if random.random() < 0.5:
                enemies.append(spawn_drone(player_pos, player_orientation))
            else:
                enemies.append(spawn_dogfighter(player_pos, player_orientation))
        elif can_drone:
            enemies.append(spawn_drone(player_pos, player_orientation))
        elif can_fighter:
            enemies.append(spawn_dogfighter(player_pos, player_orientation))
