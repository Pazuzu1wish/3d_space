
import pygame
import math
import random
from src.weapon_system import fire_lasers, fire_missile
from src.physics import player_integrate
from src.math_engine import quat_identity, rotate_pitch, rotate_yaw, rotate_roll, get_forward_from_quat, get_basis_from_quat
from src.constants import (
    PLAYER_MAX_HP, HIT_FLASH_DURATION, PLAYER_MISSILE_MAX_AMMO,
    DODGE_COOLDOWN, DODGE_IMPULSE, DODGE_THRESHOLD, DODGE_FLASH_DURATION,
    TARGETING_FOV, PLAYER_LASER_SPEED,
    PLAYER_LASER_HEAT_PER_SHOT, PLAYER_LASER_COOL_RATE, PLAYER_LASER_FIRE_SHAKE,
    PLAYER_LASER_BASE_SPREAD, PLAYER_LASER_MAX_SPREAD, PLAYER_MISSILE_LOCK_TIME, 
    PLAYER_MISSILE_LOCK_FOV
)

SHIELD_MAX       = 100
SHIELD_RECHARGE  = 25.0   # units per second
SHIELD_DELAY     = 3.0    # seconds after last hit before recharge starts

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
        self.engine_trail = []
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

        # ── PREMIUM SHIP GEOMETRY ─────────────────────────────────────────────────
        # +Z forward, +Y up, +X right.  All faces convex outward.
        self.verts = {
            # Needle nose
            'needle':       (0.0,   0.0,   90.0),

            # Forward fuselage ring
            'fwd_top':      (0.0,   9.0,   55.0),
            'fwd_l':        (-11.0, 2.0,   55.0),
            'fwd_r':        (11.0,  2.0,   55.0),
            'fwd_bot':      (0.0,  -7.0,   55.0),

            # Dorsal spine ridge (accent stripe surface)
            'spine_fwd':    (0.0,  18.0,   35.0),
            'spine_mid':    (0.0,  20.0,    0.0),
            'spine_aft':    (0.0,  16.0,  -28.0),

            # Mid fuselage ring
            'mid_top':      (0.0,  14.0,   15.0),
            'mid_l':        (-16.0, -1.0,  15.0),
            'mid_r':        (16.0,  -1.0,  15.0),
            'mid_bot':      (0.0,  -13.0,  15.0),

            # Aft fuselage ring
            'aft_top':      (0.0,  10.0,  -38.0),
            'aft_l':        (-14.0, -2.0, -38.0),
            'aft_r':        (14.0,  -2.0, -38.0),
            'aft_bot':      (0.0,  -10.0, -38.0),

            # Canards
            'cl_base_f':    (-13.0,  3.0,  48.0),
            'cl_base_r':    (-13.0, -1.0,  36.0),
            'cl_tip':       (-28.0, -2.0,  42.0),
            'cr_base_f':    (13.0,   3.0,  48.0),
            'cr_base_r':    (13.0,  -1.0,  36.0),
            'cr_tip':       (28.0,  -2.0,  42.0),

            # Wing roots
            'wrl_fwd':      (-16.0,  0.0,  10.0),
            'wrr_fwd':      (16.0,   0.0,  10.0),
            'wrl_aft':      (-14.0, -3.0, -30.0),
            'wrr_aft':      (14.0,  -3.0, -30.0),

            # Wing mid panels (dihedral break, swept)
            'wml_le':       (-42.0,  1.0,  20.0),
            'wmr_le':       (42.0,   1.0,  20.0),
            'wml_tip':      (-58.0, -5.0,  -8.0),
            'wmr_tip':      (58.0,  -5.0,  -8.0),
            'wml_te':       (-48.0, -6.0, -28.0),
            'wmr_te':       (48.0,  -6.0, -28.0),

            # Wing outer swept tips
            'wtl':          (-82.0, -10.0, -15.0),
            'wtr':          (82.0,  -10.0, -15.0),
            'wtl_te':       (-68.0, -12.0, -40.0),
            'wtr_te':       (68.0,  -12.0, -40.0),

            # Engine nacelles — left pair
            'enl_top_f':    (-19.0,  1.0,  -30.0),
            'enl_bot_f':    (-19.0, -9.0,  -30.0),
            'enl_out_f':    (-26.0, -4.0,  -30.0),
            'enl_in_f':     (-12.0, -4.0,  -30.0),
            'enl_top_r':    (-19.0,  1.0,  -58.0),
            'enl_bot_r':    (-19.0, -9.0,  -58.0),
            'enl_out_r':    (-26.0, -4.0,  -58.0),
            'enl_in_r':     (-12.0, -4.0,  -58.0),

            # Engine nacelles — right pair
            'enr_top_f':    (19.0,   1.0,  -30.0),
            'enr_bot_f':    (19.0,  -9.0,  -30.0),
            'enr_out_f':    (26.0,  -4.0,  -30.0),
            'enr_in_f':     (12.0,  -4.0,  -30.0),
            'enr_top_r':    (19.0,   1.0,  -58.0),
            'enr_bot_r':    (19.0,  -9.0,  -58.0),
            'enr_out_r':    (26.0,  -4.0,  -58.0),
            'enr_in_r':     (12.0,  -4.0,  -58.0),

            # V-tail (split, canted outward +X)
            'vtl_base':     (-8.0,  10.0, -38.0),
            'vtr_base':     (8.0,   10.0, -38.0),
            'vtl_tip':      (-30.0, 32.0, -60.0),
            'vtr_tip':      (30.0,  32.0, -60.0),
            'vtl_aft':      (-12.0,  8.0, -60.0),
            'vtr_aft':      (12.0,   8.0, -60.0),

            # Legacy aliases — engine_offsets and any code referencing old keys still work
            'eng_l':        (-19.0, -4.0, -58.0),
            'eng_r':        (19.0,  -4.0, -58.0),
            'nose':         (0.0,   0.0,   90.0),   # = needle
            'cockpit':      (0.0,   14.0,  20.0),   # ≈ spine_fwd
            'tail_top':     (0.0,   32.0, -60.0),   # ≈ vtl_tip midpoint
            'tail_base':    (0.0,   10.0, -38.0),
        }

        C_BODY = (200, 200, 210)
        C_DARK = (45, 45, 50)

        accent_color = self.trail_color

        

        self.faces = [
            {'v': ['needle', 'fwd_top', 'fwd_l'], 'color': (200, 200, 210)},  # 0 OK
            {'v': ['needle', 'fwd_r', 'fwd_top'], 'color': (200, 200, 210)},  # 1 OK
            {'v': ['needle', 'fwd_bot', 'fwd_r'], 'color': (45, 45, 50)},  # 2 OK
            {'v': ['needle', 'fwd_l', 'fwd_bot'], 'color': (45, 45, 50)},  # 3 OK
            {'v': ['fwd_top', 'spine_mid', 'spine_fwd'], 'color': (0, 255, 200)},  # 4 EDGE
            {'v': ['spine_fwd', 'spine_mid', 'mid_top'], 'color': (0, 255, 200)},  # 5 EDGE
            {'v': ['spine_mid', 'spine_aft', 'mid_top'], 'color': (0, 255, 200)},  # 6 EDGE
            {'v': ['spine_aft', 'aft_top', 'mid_top'], 'color': (0, 255, 200)},  # 7 EDGE
            {'v': ['fwd_top', 'spine_fwd', 'fwd_l'], 'color': (200, 200, 210)},  # 8 OK
            {'v': ['fwd_top', 'fwd_r', 'spine_fwd'], 'color': (200, 200, 210)},  # 9 OK
            {'v': ['fwd_l', 'mid_l', 'fwd_bot'], 'color': (45, 45, 50)},  # 10 OK
            {'v': ['fwd_r', 'fwd_bot', 'mid_r'], 'color': (45, 45, 50)},  # 11 OK
            {'v': ['fwd_bot', 'mid_bot', 'mid_r'], 'color': (45, 45, 50)},  # 12 OK
            {'v': ['fwd_bot', 'mid_l', 'mid_bot'], 'color': (45, 45, 50)},  # 13 OK
            {'v': ['mid_top', 'aft_top', 'mid_l'], 'color': (200, 200, 210)},  # 14 OK
            {'v': ['aft_top', 'aft_l', 'mid_l'], 'color': (200, 200, 210)},  # 15 OK
            {'v': ['mid_top', 'mid_r', 'aft_top'], 'color': (200, 200, 210)},  # 16 OK
            {'v': ['aft_top', 'mid_r', 'aft_r'], 'color': (200, 200, 210)},  # 17 OK
            {'v': ['mid_l', 'aft_l', 'mid_bot'], 'color': (45, 45, 50)},  # 18 OK
            {'v': ['aft_l', 'aft_bot', 'mid_bot'], 'color': (45, 45, 50)},  # 19 OK
            {'v': ['mid_r', 'mid_bot', 'aft_r'], 'color': (45, 45, 50)},  # 20 OK
            {'v': ['aft_r', 'mid_bot', 'aft_bot'], 'color': (45, 45, 50)},  # 21 OK
            {'v': ['cl_base_f', 'cl_tip', 'cl_base_r'], 'color': (0, 255, 200)},  # 22 OK
            {'v': ['cl_base_r', 'cl_base_f', 'cl_tip'], 'color': (0, 255, 200)},  # 23 OK
            {'v': ['cr_base_f', 'cr_base_r', 'cr_tip'], 'color': (0, 255, 200)},  # 24 OK
            {'v': ['cr_base_r', 'cr_tip', 'cr_base_f'], 'color': (0, 255, 200)},  # 25 OK
            {'v': ['wrl_fwd', 'wml_le', 'wml_tip'], 'color': (200, 200, 210)},  # 26 OK
            {'v': ['wrl_fwd', 'wml_le', 'mid_l'], 'color': (200, 200, 210)},  # 27 OK
            {'v': ['wrl_fwd', 'wml_tip', 'wrl_aft'], 'color': (45, 45, 50)},  # 28 OK
            {'v': ['wrl_aft', 'wml_tip', 'wml_te'], 'color': (45, 45, 50)},  # 29 OK
            {'v': ['wrr_fwd', 'wmr_tip', 'wmr_le'], 'color': (200, 200, 210)},  # 30 OK
            {'v': ['wrr_fwd', 'mid_r', 'wmr_le'], 'color': (200, 200, 210)},  # 31 OK
            {'v': ['wrr_fwd', 'wrr_aft', 'wmr_tip'], 'color': (45, 45, 50)},  # 32 OK
            {'v': ['wrr_aft', 'wmr_te', 'wmr_tip'], 'color': (45, 45, 50)},  # 33 OK
            {'v': ['wml_le', 'wml_tip', 'wtl'], 'color': (0, 255, 200)},  # 34 OK
            {'v': ['wml_tip', 'wtl_te', 'wtl'], 'color': (0, 255, 200)},  # 35 OK
            {'v': ['wml_tip', 'wml_te', 'wtl_te'], 'color': (200, 200, 210)},  # 36 OK
            {'v': ['wmr_le', 'wtr', 'wmr_tip'], 'color': (0, 255, 200)},  # 37 OK
            {'v': ['wmr_tip', 'wtr', 'wtr_te'], 'color': (0, 255, 200)},  # 38 OK
            {'v': ['wmr_tip', 'wtr_te', 'wmr_te'], 'color': (200, 200, 210)},  # 39 OK
            {'v': ['enl_top_f', 'enl_top_r', 'enl_in_f'], 'color': (200, 200, 210)},  # 40 OK
            {'v': ['enl_top_r', 'enl_in_r', 'enl_in_f'], 'color': (200, 200, 210)},  # 41 OK
            {'v': ['enl_out_f', 'enl_top_f', 'enl_out_r'], 'color': (200, 200, 210)},  # 42 OK
            {'v': ['enl_out_r', 'enl_top_f', 'enl_top_r'], 'color': (200, 200, 210)},  # 43 OK
            {'v': ['enl_bot_f', 'enl_out_f', 'enl_bot_r'], 'color': (45, 45, 50)},  # 44 OK
            {'v': ['enl_bot_r', 'enl_out_f', 'enl_out_r'], 'color': (45, 45, 50)},  # 45 OK
            {'v': ['enl_in_f', 'enl_in_r', 'enl_bot_f'], 'color': (45, 45, 50)},  # 46 OK
            {'v': ['enl_in_r', 'enl_bot_r', 'enl_bot_f'], 'color': (45, 45, 50)},  # 47 OK
            {'v': ['enl_top_f', 'enl_in_f', 'enl_bot_f'], 'color': (0, 255, 200)},  # 48 OK
            {'v': ['enl_top_f', 'enl_bot_f', 'enl_out_f'], 'color': (0, 255, 200)},  # 49 OK
            {'v': ['enr_top_f', 'enr_in_f', 'enr_top_r'], 'color': (200, 200, 210)},  # 50 OK
            {'v': ['enr_top_r', 'enr_in_f', 'enr_in_r'], 'color': (200, 200, 210)},  # 51 OK
            {'v': ['enr_out_f', 'enr_out_r', 'enr_top_f'], 'color': (200, 200, 210)},  # 52 OK
            {'v': ['enr_out_r', 'enr_top_r', 'enr_top_f'], 'color': (200, 200, 210)},  # 53 OK
            {'v': ['enr_bot_f', 'enr_bot_r', 'enr_out_f'], 'color': (45, 45, 50)},  # 54 OK
            {'v': ['enr_bot_r', 'enr_out_r', 'enr_out_f'], 'color': (45, 45, 50)},  # 55 OK
            {'v': ['enr_in_f', 'enr_bot_f', 'enr_in_r'], 'color': (45, 45, 50)},  # 56 OK
            {'v': ['enr_in_r', 'enr_bot_f', 'enr_bot_r'], 'color': (45, 45, 50)},  # 57 OK
            {'v': ['enr_top_f', 'enr_bot_f', 'enr_in_f'], 'color': (0, 255, 200)},  # 58 OK
            {'v': ['enr_top_f', 'enr_out_f', 'enr_bot_f'], 'color': (0, 255, 200)},  # 59 OK
            {'v': ['vtl_base', 'vtl_aft', 'vtl_tip'], 'color': (0, 255, 200)},  # 60 OK
            {'v': ['vtl_aft', 'vtl_tip', 'vtl_base'], 'color': (200, 200, 210)},  # 61 OK
            {'v': ['vtr_base', 'vtr_tip', 'vtr_aft'], 'color': (0, 255, 200)},  # 62 OK
            {'v': ['vtr_aft', 'vtr_base', 'vtr_tip'], 'color': (200, 200, 210)},  # 63 OK
        ]
        

    @property
    def trail_color_name(self):
        return self.trail_colors[self.trail_color_index][0]

    @property
    def trail_color(self):
        return self.trail_colors[self.trail_color_index][1]

    def change_trail_color(self, direction):
        self.trail_color_index = (self.trail_color_index + direction) % len(self.trail_colors)
        # Instantly update all frozen trail colors
        new_color = self.trail_color
        for p in self.engine_trail:
            p[7] = new_color

    def _submit_engine_trail(self, renderer):
        for x, y, z, vx, vy, vz, life, color, base_size in self.engine_trail:
            ratio = max(0.0, life / self.trail_life)
            
            # "Sparkling points" effect: 15% chance to flicker to a dim state
            flicker = 1.0 if random.random() > 0.15 else 0.4
            
            # Fade out color as it dies
            r = min(255, max(0, int(color[0] * ratio * flicker)))
            g = min(255, max(0, int(color[1] * ratio * flicker)))
            b = min(255, max(0, int(color[2] * ratio * flicker)))
            
            # Bright white core for sparkling point
            core_color = (
                min(255, r + int((255 - r) * 0.5)),
                min(255, g + int((255 - g) * 0.5)),
                min(255, b + int((255 - b) * 0.5))
            )
            
            renderer.submit_sprite(x, y, z, (r, g, b), base_size * 5 * ratio, layer='alpha')
            renderer.submit_sprite(x, y, z, core_color, base_size * 2 * ratio, layer='alpha')

    def submit_to_renderer(self, renderer):
        # 1. Submit engine trail
        self._submit_engine_trail(renderer)
        
        # 2. Submit ship wireframe mesh
        faces = self.faces  

        # Get player basis vectors
        _, right, up = get_basis_from_quat(self.orientation)
        fx, fy, fz = get_forward_from_quat(self.orientation)
        
        # Submit player ship mesh to the renderer!
        renderer.submit_mesh(
            self.pos,
            right,
            up,
            (fx, fy, fz),
            self.verts,
            faces,
            radius=150.0
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
                self.orientation = rotate_pitch(self.orientation, ly * PITCH_RATE * dt)
            if abs(lx) > 0.01:
                self.orientation = rotate_roll(self.orientation, lx * ROLL_RATE * dt)

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
        
        for ox, oy, oz in self.engine_offsets:
            ex = self.pos[0] + right[0] * ox + up[0] * oy + fx * oz
            ey = self.pos[1] + right[1] * ox + up[1] * oy + fy * oz
            ez = self.pos[2] + right[2] * ox + up[2] * oy + fz * oz
            
            # Drift velocity: backward exhaust force + minor random diffusion
            dvx = -fx * speed * 0.2 + (random.random() - 0.5) * self.trail_drift
            dvy = -fy * speed * 0.2 + (random.random() - 0.5) * self.trail_drift
            dvz = -fz * speed * 0.2 + (random.random() - 0.5) * self.trail_drift
            
            self.engine_trail.append([
                ex, ey, ez, 
                dvx, dvy, dvz, 
                self.trail_life * random.uniform(0.8, 1.2), 
                self.trail_color, 
                self.engine_size
            ])
            
        # Update existing trail points
        for p in self.engine_trail:
            p[0] += p[3] * dt
            p[1] += p[4] * dt
            p[2] += p[5] * dt
            p[6] -= dt
            
        # Recycle dead ones
        self.engine_trail = [p for p in self.engine_trail if p[6] > 0]

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
