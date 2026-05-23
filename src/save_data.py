"""
src/save_data.py

Single source of truth for anything that persists between sessions.
Serialize to / deserialize from a single JSON file.

Phase 1: score mode high scores only.
Phase 2+: credits, reputation, ship loadout, visited systems — add fields here.
"""

import json
import os
from dataclasses import dataclass, field, asdict


# ── RunResult ─────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    """
    Everything needed to compute and display a score for one session.
    Populated at game over, passed to SaveData.record_run().
    """
    kills:          list    # list of type name strings e.g. ['SuicideDrone', 'Dogfighter']
    survival_time:  float   # seconds, from director.elapsed
    shots_fired:    int
    shots_hit:      int
    damage_taken:   float   # cumulative hp lost
    max_hp:         float   # player starting hp, for damage pct calc

    # ── base kill points ──────────────────────────────────────────────────
    KILL_POINTS = {
        'SuicideDrone':       100,
        'Dogfighter':         250,
        'Sniper':             400,
        'StealthInterceptor': 450,
        'Minelayer':          350,
        'Corvette':           750,
        'Carrier':           2000,
    }

    def base_kill_score(self):
        return sum(self.KILL_POINTS.get(k, 100) for k in self.kills)

    def kill_count(self):
        return len(self.kills)

    def accuracy(self):
        if self.shots_fired == 0:
            return 0.0
        return self.shots_hit / self.shots_fired

    def accuracy_modifier(self):
        """0.5x at 0% accuracy, 2.0x at 100% accuracy."""
        return 0.5 + self.accuracy() * 1.5

    def time_modifier(self):
        """1.0x at 0 min survival, 2.0x cap at 10 min."""
        minutes = self.survival_time / 60.0
        return min(2.0, 1.0 + minutes * 0.1)

    def damage_modifier(self):
        """2.0x for no damage taken, 1.0x for full hp lost."""
        pct_taken = min(1.0, self.damage_taken / max(1.0, self.max_hp))
        return 1.0 + (1.0 - pct_taken)

    def final_score(self):
        base = self.base_kill_score()
        return int(base * self.accuracy_modifier() * self.time_modifier() * self.damage_modifier())

    def to_dict(self):
        return {
            'kills':         self.kills,
            'survival_time': round(self.survival_time, 1),
            'shots_fired':   self.shots_fired,
            'shots_hit':     self.shots_hit,
            'damage_taken':  round(self.damage_taken, 1),
            'max_hp':        self.max_hp,
            'final_score':   self.final_score(),
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            kills          = d['kills'],
            survival_time  = d['survival_time'],
            shots_fired    = d['shots_fired'],
            shots_hit      = d['shots_hit'],
            damage_taken   = d['damage_taken'],
            max_hp         = d['max_hp'],
        )


# ── SaveData ──────────────────────────────────────────────────────────────────

@dataclass
class SaveData:
    """
    Persistent game state.  Load once at startup, save on game over / exit.

    Phase 1 fields: high scores only.
    Phase 2+ fields (commented stubs): credits, reputation, loadout, etc.
    """
    high_scores: list = field(default_factory=list)  # list of RunResult dicts, sorted desc

    # Phase 2 stubs — uncomment and add defaults when ready:
    # commander_name:    str  = "CMDR"
    # credits:           int  = 1000
    # reputation:        dict = field(default_factory=dict)   # faction -> float
    # unlocked_ships:    list = field(default_factory=lambda: ['starter'])
    # unlocked_weapons:  list = field(default_factory=list)
    # visited_systems:   list = field(default_factory=list)
    # ship_id:           str  = 'starter'
    # hardpoints:        dict = field(default_factory=dict)

    MAX_SCORES = 10

    def record_run(self, result: RunResult):
        """Insert result, keep top MAX_SCORES by final_score."""
        self.high_scores.append(result.to_dict())
        self.high_scores.sort(key=lambda r: r['final_score'], reverse=True)
        self.high_scores = self.high_scores[:self.MAX_SCORES]

    def save(self, path='save.json'):
        with open(path, 'w') as f:
            json.dump({'high_scores': self.high_scores}, f, indent=2)

    @classmethod
    def load(cls, path='save.json'):
        if not os.path.exists(path):
            return cls()
        try:
            with open(path) as f:
                data = json.load(f)
            return cls(high_scores=data.get('high_scores', []))
        except (json.JSONDecodeError, KeyError):
            # Corrupted save — start fresh rather than crashing
            return cls()