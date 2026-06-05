
import pygame
import math
import random
from src.weapon_system import fire_lasers, fire_missile
from src.physics import player_integrate
from src.math_engine import quat_identity, rotate_pitch, rotate_yaw, rotate_roll, get_forward_from_quat, get_basis_from_quat
from src.object_pool import TrailPool
from src.mesh_loader import get_ship_mesh
from src.constants import (
    PLAYER_MAX_HP, HIT_FLASH_DURATION, PLAYER_MISSILE_MAX_AMMO,
    DODGE_COOLDOWN, DODGE_IMPULSE, DODGE_THRESHOLD, DODGE_FLASH_DURATION,
    TARGETING_FOV, PLAYER_LASER_SPEED,
    PLAYER_LASER_HEAT_PER_SHOT, PLAYER_LASER_COOL_RATE, PLAYER_LASER_FIRE_SHAKE,
    PLAYER_LASER_BASE_SPREAD, PLAYER_LASER_MAX_SPREAD, PLAYER_MISSILE_LOCK_TIME,
    PLAYER_MISSILE_LOCK_FOV
)

SHIELD_MAX       = 100
SHIELD_RECHARGE  = 15.0   # units per second
SHIELD_DELAY     = 7.0    # seconds after last hit before recharge starts

class Player:
    def __init__(self, pos=(0.0, 0.0, 0.0)):
        self.pos = list(pos)
        self.vel = [0.0, 0.0, 0.0]
        self.orientation = quat_identity()
        
        self.throttle = 0.0
        self.weapons_cooldown = 0.0
        self.hp = PLAYER_MAX_HP
        self.hit_flash = 0.0

        # Targeting
        self.active_target = None          # the currently locked enemy object
        self._target_key_cd = 0.0         # prevents key repeat on T/Y

        # Dodge system
        self.dodge_cooldown = 0.0
        self.dodge_flash = 0.0

        # Shield system
        self.shield = SHIELD_MAX
        self.shield_regen_timer = 0.0
        self.shield_flash = 0.0
        self.shake_queued = 0.0
        self.rumble_queued = 0.0

        # Laser Heat System
        self.laser_heat = 0.0
        self.overheated = False

        # Missile System
        self.missile_ammo = PLAYER_MISSILE_MAX_AMMO
        self.missile_lock_timer = 0.0
        self.missile_locked = False
        self.drift_mode = False

        # Stats for scoring
        self.shots_fired = 0
        self.shots_hit = 0
        self.damage_taken = 0
        self.max_hp = self.hp

        # Trail & Visual Customization
        self.engine_offsets = [
            (-19.0, -4.0, -62.0),   # left nacelle exhaust
            (19.0,  -4.0, -62.0),   # right nacelle exhaust
        ]
        # TrailPool: 2 engines × 30 slots = 60 capacity
        self._trail_pool = TrailPool(capacity=60)
        self.trail_life = 1.0       # trail lasts 1 second
        self.trail_drift = 25.0
        self.engine_size = 2.5
        
        # 8 Premium neon colors
        self.trail_colors = [
            ("HYPER CYAN", (0, 255, 200)),
            ("SOLAR ORANGE", (255, 100, 0)),
            ("VOID PURPLE", (170, 0, 255)),
            ("PLAGUE GREEN", (50, 255, 50)),
            ("LASER RED", (255, 0, 50)),
            ("SUPERNOVA YELLOW", (255, 220, 0)),
            ("PRISM PINK", (255, 50, 180)),
            ("GLACIER WHITE", (220, 240, 255)),
        ]
        self.trail_color_index = 0

        # ── SHIP MESH (loaded from assets/player.obj + player.mtl) ──────────
        self.baked_mesh = get_ship_mesh('player')

        # Backwards-compat shim: rebuild verts dict and faces list from the
        # BakedMesh so the 3D viewer and any other tool that reads .verts/.faces
        # continues to work without modification.
        accent_color = self.trail_color
        self.verts = {f'v{i}': tuple(row) for i, row in enumerate(self.baked_mesh.v_data)}
        self.faces = [
            {'v': [f'v{self.baked_mesh.f_idx[i, 0]}',
                   f'v{self.baked_mesh.f_idx[i, 1]}',
                   f'v{self.baked_mesh.f_idx[i, 2]}'],
             'color': tuple(self.baked_mesh.f_col[i])}
            for i in range(len(self.baked_mesh.f_idx))
        ]

    @property
    def trail_color_name(self):
        return self.trail_colors[self.trail_color_index][0]

    @property
    def trail_color(self):
        return self.trail_colors[self.trail_color_index][1]

    def change_trail_color(self, direction):
        self.trail_color_index = (self.trail_color_index + direction) % len(self.trail_colors)
        # New particles spawned after this call will use the new trail_color.
        # In-flight TrailPool slots keep their current colour (barely noticeable
        # given trail_life = 1 s).  No list iteration needed.

    def _submit_engine_trail(self, renderer):
        self._trail_pool.submit_to_renderer(renderer, self.trail_life)

    def submit_to_renderer(self, renderer):
        # 1. Submit engine trail
        self._submit_engine_trail(renderer)

        # 2. Submit ship mesh via the fast baked-mesh path
        _, right, up = get_basis_from_quat(self.orientation)
        fx, fy, fz = get_forward_from_quat(self.orientation)

        renderer.submit_baked_mesh(
            self.pos,
            right,
            up,
            (fx, fy, fz),
            self.baked_mesh,
        )


    @property
    def shield_charge(self):
        """0.0 = depleted, 1.0 = full."""
        return self.shield / SHIELD_MAX

    @property
    def shield_recharging(self):
        return self.shield_regen_timer <= 0 and self.shield < SHIELD_MAX

    @property
    def current_speed(self):
        return math.sqrt(self.vel[0]**2 + self.vel[1]**2 + self.vel[2]**2)

    def update(self, dt, handler, keys, lasers, particles, enemy_projectiles, player_missiles, sound=None):
        # ── INPUT ─────────────────────────────────
        lx, ly = handler.stick_left()
        rx, _  = handler.stick_right()
        fire_r = handler.trigger_right() > 0.5
        fire_pressed = fire_r

        if keys[pygame.K_w]:     ly = -1.0
        if keys[pygame.K_s]:     ly =  1.0
        if keys[pygame.K_a]:     lx = -1.0
        if keys[pygame.K_d]:     lx =  1.0
        if keys[pygame.K_LEFT]:  rx = -1.0
        if keys[pygame.K_RIGHT]: rx =  1.0
        if keys[pygame.K_UP]:    self.throttle = min(1.0, self.throttle + dt)
        if keys[pygame.K_DOWN]:  self.throttle = max(-1.0, self.throttle - dt)
        if keys[pygame.K_SPACE]: fire_pressed = True
        missile_fire_pressed = handler.just_pressed('Square') or keys[pygame.K_x]

        # ── TARGETING KEYS ────────────────────────
        # Resolved later via target_closest() / cycle_targets()
        # (called from game.py after enemies list is available)
        dpad_up_pressed = handler.just_pressed('DPad Up')

        self._key_target_closest = keys[pygame.K_t] and self._target_key_cd <= 0
        self._key_cycle_target   = (keys[pygame.K_y] or dpad_up_pressed) and self._target_key_cd <= 0
        if keys[pygame.K_t] or keys[pygame.K_y] or dpad_up_pressed:
            if self._target_key_cd <= 0:
                self._target_key_cd = 0.25   # 250 ms debounce

        # ── THROTTLE INPUT & DRIFT MODE ───────────
        if keys[pygame.K_UP] or keys[pygame.K_DOWN] or handler.held('R1') or handler.held('L1'):
            self.drift_mode = False

        if handler.held('R1'): self.throttle = min(1.0, self.throttle + dt * 3.8)
        if handler.held('L1'): self.throttle = max(-1.0, self.throttle - dt * 3.8)

        if handler.just_pressed('R3') or keys[pygame.K_f]:
            self.drift_mode = not self.drift_mode
            if self.drift_mode:
                self.throttle = 0.0

        # ── DODGE ─────────────────────────────────
        self.dodge_cooldown = max(0.0, self.dodge_cooldown - dt)
        self.dodge_flash = max(0.0, self.dodge_flash - dt)

        # ── SHIELD RECHARGE ───────────────────────
        self.shield_regen_timer = max(0.0, self.shield_regen_timer - dt)
        if self.shield_regen_timer <= 0 and self.shield < SHIELD_MAX:
            self.shield = min(SHIELD_MAX, self.shield + SHIELD_RECHARGE * dt)

        if handler.held('Circle') and self.dodge_cooldown <= 0:
            dlx, dly = handler.stick_left()
            if abs(dlx) > DODGE_THRESHOLD or abs(dly) > DODGE_THRESHOLD:
                _, right, up = get_basis_from_quat(self.orientation)
                # ly negative = stick up = toward cockpit ceiling
                self.vel[0] += (right[0] * dlx - up[0] * dly) * DODGE_IMPULSE
                self.vel[1] += (right[1] * dlx - up[1] * dly) * DODGE_IMPULSE
                self.vel[2] += (right[2] * dlx - up[2] * dly) * DODGE_IMPULSE
                self.dodge_cooldown = DODGE_COOLDOWN
                self.dodge_flash = DODGE_FLASH_DURATION

        # ── ROTATION ──────────────────────────────
        PITCH_RATE = 4.0
        YAW_RATE   = 3.5
        ROLL_RATE  = 4.0

        dodge_mode = handler.held('Circle')

        if not dodge_mode:
            if abs(ly) > 0.01:
                self.orientation = rotate_pitch(self.orientation, -ly * PITCH_RATE * dt)
            if abs(lx) > 0.01:
                self.orientation = rotate_roll(self.orientation, -lx * ROLL_RATE * dt)

        if abs(rx) > 0.01:
            self.orientation = rotate_yaw(self.orientation, rx * YAW_RATE * dt)

        self.weapons_cooldown = max(0.0, self.weapons_cooldown - dt)
        self.hit_flash        = max(0.0, self.hit_flash - dt)
        self._target_key_cd   = max(0.0, self._target_key_cd  - dt)

        # ── MISSILE LOCK-ON LOGIC ──────────────────
        if self.active_target and getattr(self.active_target, 'hp', 0) > 0 and not getattr(self.active_target, 'stealthed', False):
            fx, fy, fz = get_forward_from_quat(self.orientation)
            dx = self.active_target.x - self.pos[0]
            dy = self.active_target.y - self.pos[1]
            dz = self.active_target.z - self.pos[2]
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            if dist > 0:
                dx, dy, dz = dx/dist, dy/dist, dz/dist
                dot = fx*dx + fy*dy + fz*dz
                if dot >= PLAYER_MISSILE_LOCK_FOV:
                    self.missile_lock_timer += dt
                    if self.missile_lock_timer >= PLAYER_MISSILE_LOCK_TIME:
                        self.missile_locked = True
                else:
                    self.missile_lock_timer = 0.0
                    self.missile_locked = False
        else:
            self.missile_lock_timer = 0.0
            self.missile_locked = False

        # ── HEAT MANAGEMENT ────────────────────────
        self.laser_heat = max(0.0, self.laser_heat - PLAYER_LASER_COOL_RATE * dt)
        if self.overheated and self.laser_heat <= 0:
            self.overheated = False

        # ── MOVEMENT ──────────────────────────────
        player_integrate(self, dt)
        
        # ── WEAPONS ───────────────────────────────
        fire_lasers(self, fire_pressed, handler, lasers, sound)
        fire_missile(self, missile_fire_pressed, handler, player_missiles, sound)
        
        
        # ── ENGINE TRAIL SPAWNING & UPDATING ──────────
        fx, fy, fz = get_forward_from_quat(self.orientation)
        _, right, up = get_basis_from_quat(self.orientation)
        speed = self.current_speed
        trail_color = self.trail_color

        for ox, oy, oz in self.engine_offsets:
            ex = self.pos[0] + right[0]*ox + up[0]*oy + fx*oz
            ey = self.pos[1] + right[1]*ox + up[1]*oy + fy*oz
            ez = self.pos[2] + right[2]*ox + up[2]*oy + fz*oz

            # Drift velocity: backward exhaust + random diffusion
            dvx = -fx * speed * 0.2 + (random.random() - 0.5) * self.trail_drift
            dvy = -fy * speed * 0.2 + (random.random() - 0.5) * self.trail_drift
            dvz = -fz * speed * 0.2 + (random.random() - 0.5) * self.trail_drift
            life = self.trail_life * random.uniform(0.8, 1.2)

            self._trail_pool.spawn(ex, ey, ez, dvx, dvy, dvz, life, trail_color, self.engine_size)

        # Advance all trail particles (vectorised, zero allocation)
        self._trail_pool.update(dt)

        # ── RUMBLE FEEDBACK ───────────────────────────
        if self.rumble_queued > 0:
            intensity = min(1.0, self.rumble_queued / 30.0)
            handler.rumble(intensity, intensity * 0.5, 200)
            self.rumble_queued = 0.0

        # ── DYNAMIC ENGINE HUM ────────────────────────
        if sound and hasattr(sound, 'update_engine_hum'):
            sound.update_engine_hum(self.throttle, rx, lx, ly)

    def take_damage(self, amount):
        self.damage_taken += amount
        self.shield_regen_timer = SHIELD_DELAY
        self.hit_flash = HIT_FLASH_DURATION
        self.shake_queued += amount
        self.rumble_queued += amount
        if self.shield > 0:
            if hasattr(self, 'sound') and self.sound:
                self.sound.play_sfx("shield_hit")
            absorbed = min(self.shield, amount)
            self.shield -= absorbed
            amount -= absorbed
        else:
            if hasattr(self, 'sound') and self.sound:
                self.sound.play_sfx("armor_hit")
        if amount > 0:
            self.hp = max(0, self.hp - amount)

    # ── TARGETING METHODS ────────────────────────────────────────────

    def target_closest(self, enemies):
        """Lock onto the nearest living, non-stealthed enemy within field of view."""
        visible = [e for e in enemies if not getattr(e, 'stealthed', False)]
        if not visible:
            self.active_target = None
            return

        # Get forward direction and FOV threshold
        fx, fy, fz = get_forward_from_quat(self.orientation)
        fov_threshold = math.cos(math.radians(TARGETING_FOV / 2.0))

        # Filter to only enemies within FOV
        in_fov = []
        for e in visible:
            ex, ey, ez = e.x, e.y, e.z
            # Direction from player to enemy
            dx = ex - self.pos[0]
            dy = ey - self.pos[1]
            dz = ez - self.pos[2]
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)

            if dist > 0:
                # Normalize direction vector
                dx, dy, dz = dx/dist, dy/dist, dz/dist
                # Dot product with forward direction
                dot = fx*dx + fy*dy + fz*dz
                if dot >= fov_threshold:
                    in_fov.append(e)

        # Lock onto the nearest enemy in FOV
        if in_fov:
            self.active_target = min(
                in_fov,
                key=lambda e: math.dist(self.pos, (e.x, e.y, e.z))
            )
        else:
            self.active_target = None

    def cycle_targets(self, enemies):
        """Advance to the next non-stealthed enemy in FOV (wraps around)."""
        visible = [e for e in enemies if not getattr(e, 'stealthed', False)]
        if not visible:
            self.active_target = None
            return

        # Get forward direction and FOV threshold
        fx, fy, fz = get_forward_from_quat(self.orientation)
        fov_threshold = math.cos(math.radians(TARGETING_FOV / 2.0))

        # Filter to only enemies within FOV
        in_fov = []
        for e in visible:
            ex, ey, ez = e.x, e.y, e.z
            # Direction from player to enemy
            dx = ex - self.pos[0]
            dy = ey - self.pos[1]
            dz = ez - self.pos[2]
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)

            if dist > 0:
                # Normalize direction vector
                dx, dy, dz = dx/dist, dy/dist, dz/dist
                # Dot product with forward direction
                dot = fx*dx + fy*dy + fz*dz
                if dot >= fov_threshold:
                    in_fov.append(e)

        # Cycle through enemies in FOV
        if not in_fov:
            self.active_target = None
            return
        if self.active_target not in in_fov:
            self.active_target = in_fov[0]
            return
        idx = in_fov.index(self.active_target)
        self.active_target = in_fov[(idx + 1) % len(in_fov)]

    def clear_dead_target(self, enemies):
        """Nullify the active target if it has been destroyed."""
        if self.active_target is not None and self.active_target not in enemies:
            self.active_target = None

    @property
    def dodge_charge(self):
        """0.0 = just fired, 1.0 = fully ready."""
        return 1.0 - (self.dodge_cooldown / DODGE_COOLDOWN)

    @property
    def dodge_ready(self):
        return self.dodge_cooldown <= 0
