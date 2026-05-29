from dataclasses import dataclass
from typing import Any, Optional, Sequence

@dataclass
class HUDData:
    W: int
    H: int
    throttle: float
    current_speed: float
    weapons_ready: bool
    orientation: Optional[Any] = None
    player_pos: Optional[Sequence[float]] = None
    player_vel: Optional[Sequence[float]] = None
    enemies: Optional[Any] = None
    radar_enemies: Optional[Any] = None
    player_hp: float = 100
    active_target: Optional[Any] = None
    dodge_charge: float = 1.0
    dodge_ready: bool = True
    dodge_flash: float = 0.0
    shield_charge: float = 1.0
    shield_recharging: bool = False
    laser_heat: float = 0.0
    laser_overheated: bool = False
    waypoints: Optional[Any] = None
    shake_offset: Sequence[float] = (0.0, 0.0)
    hit_flash_ratio: float = 0.0
    explosion_glow: float = 0.0
    missile_lock: bool = False
    alert_active: bool = False
    missile_ammo: int = 0
    missile_lock_timer: float = 0.0
    missile_locked: bool = False
    drift_mode: bool = False
    show_prograde: bool = True
    show_coords: bool = False
    # Debug HUD options
    show_fps: bool = False
    fps: float = 0.0

