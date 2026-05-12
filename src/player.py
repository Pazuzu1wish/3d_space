import pygame
import math
import random
from src.math_engine import quat_identity, rotate_pitch, rotate_yaw, rotate_roll, get_forward_from_quat, get_basis_from_quat
from src.constants import (
    PLAYER_MAX_HP, MAX_THRUST, MAX_RETRO_THRUST, DRAG, MAX_SPEED,
    HIT_FLASH_DURATION, PLAYER_COLLISION_RADIUS,
    DODGE_COOLDOWN, DODGE_IMPULSE, DODGE_THRESHOLD, DODGE_FLASH_DURATION,
    TARGETING_FOV, PLAYER_LASER_SPEED,
    PLAYER_LASER_HEAT_PER_SHOT, PLAYER_LASER_COOL_RATE, PLAYER_LASER_FIRE_SHAKE,
    PLAYER_LASER_BASE_SPREAD, PLAYER_LASER_MAX_SPREAD
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
        self._prev_dpad = (0, 0)          # track previous dpad state for just_pressed detection

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

    def update(self, dt, handler, keys, lasers, particles, enemy_projectiles):
        # ── INPUT ─────────────────────────────────
        lx, ly = handler.stick_left()
        rx, _  = handler.stick_right()
        #fire_l = handler.trigger_left()  > 0.5
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

        # ── TARGETING KEYS ────────────────────────
        # Resolved later via target_closest() / cycle_targets()
        # (called from game.py after enemies list is available)
        current_dpad = handler.dpad()
        dpad_up_pressed = current_dpad[1] == 1 and self._prev_dpad[1] != 1

        self._key_target_closest = keys[pygame.K_t] and self._target_key_cd <= 0
        self._key_cycle_target   = (keys[pygame.K_y] or dpad_up_pressed) and self._target_key_cd <= 0
        if keys[pygame.K_t] or keys[pygame.K_y] or dpad_up_pressed:
            if self._target_key_cd <= 0:
                self._target_key_cd = 0.25   # 250 ms debounce

        self._prev_dpad = current_dpad

        if handler.held('R1'): self.throttle = min(1.0, self.throttle + dt * 2.8)
        if handler.held('L1'): self.throttle = max(-1.0, self.throttle - dt * 2.8)
        if handler.just_pressed('R3'): self.throttle = 0.0

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

        # ── HEAT MANAGEMENT ────────────────────────
        self.laser_heat = max(0.0, self.laser_heat - PLAYER_LASER_COOL_RATE * dt)
        if self.overheated and self.laser_heat <= 0:
            self.overheated = False

        # ── MOVEMENT ──────────────────────────────
        fx, fy, fz = get_forward_from_quat(self.orientation)
        
        if self.throttle > 0:
            thrust = self.throttle * MAX_THRUST
        else:
            thrust = self.throttle * MAX_RETRO_THRUST
            
        self.vel[0] += fx * thrust * dt
        self.vel[1] += fy * thrust * dt
        self.vel[2] += fz * thrust * dt
        
        self.vel[0] -= self.vel[0] * DRAG * dt
        self.vel[1] -= self.vel[1] * DRAG * dt
        self.vel[2] -= self.vel[2] * DRAG * dt
        
        # Cap max speed
        speed_sq = self.vel[0]**2 + self.vel[1]**2 + self.vel[2]**2
        if speed_sq > MAX_SPEED**2:
            speed = math.sqrt(speed_sq)
            self.vel[0] = (self.vel[0] / speed) * MAX_SPEED
            self.vel[1] = (self.vel[1] / speed) * MAX_SPEED
            self.vel[2] = (self.vel[2] / speed) * MAX_SPEED
        
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt
        self.pos[2] += self.vel[2] * dt
        
        # ── WEAPONS ───────────────────────────────
        if fire_pressed and self.weapons_cooldown <= 0 and not self.overheated:
            forward, right, _ = get_basis_from_quat(self.orientation)
            rfx, rfy, rfz = forward
            rrx, rry, rrz = right
            LASER_SPEED = PLAYER_LASER_SPEED
            offset = 40
            
            # Calculate current spread based on heat
            current_spread = PLAYER_LASER_BASE_SPREAD + (self.laser_heat * PLAYER_LASER_MAX_SPREAD)
            
            for side in (-1, 1):
                # Apply random jitter to the forward vector
                jx = (random.random() * 2 - 1) * current_spread
                jy = (random.random() * 2 - 1) * current_spread
                
                # Perturb the forward vector
                _, _, up = get_basis_from_quat(self.orientation)
                pfx = rfx + rrx * jx + up[0] * jy
                pfy = rfy + rry * jx + up[1] * jy
                pfz = rfz + rrz * jx + up[2] * jy
                
                # Re-normalize direction
                mag = math.sqrt(pfx*pfx + pfy*pfy + pfz*pfz)
                pfx, pfy, pfz = pfx/mag, pfy/mag, pfz/mag
                
                wx = self.pos[0] + rrx * offset * side + rfx * 70
                wy = self.pos[1] + rry * offset * side + rfy * 70
                wz = self.pos[2] + rrz * offset * side + rfz * 70
                
                lasers.fire(
                    wx, wy, wz,
                    pfx * LASER_SPEED, pfy * LASER_SPEED, pfz * LASER_SPEED
                )
            
            # Update cooldown, heat and shake
            self.weapons_cooldown = 0.15
            self.laser_heat = min(1.0, self.laser_heat + PLAYER_LASER_HEAT_PER_SHOT)
            if self.laser_heat >= 1.0:
                self.overheated = True
            
            self.shake_queued += PLAYER_LASER_FIRE_SHAKE
            handler.rumble(0.0, 0.12, 50)
            
        # ── RUMBLE FEEDBACK ───────────────────────────
        if self.rumble_queued > 0:
            intensity = min(1.0, self.rumble_queued / 30.0)
            handler.rumble(intensity, intensity * 0.5, 200)
            self.rumble_queued = 0.0

        # ── CHECK PROJECTILE HITS ─────────────────────
        for bolt in enemy_projectiles[:]:
            if bolt.check_player_collision(self, particles):
                if bolt in enemy_projectiles:
                    enemy_projectiles.remove(bolt)

    def take_damage(self, amount):
        self.shield_regen_timer = SHIELD_DELAY
        self.hit_flash = HIT_FLASH_DURATION
        self.shake_queued += amount
        self.rumble_queued += amount
        if self.shield > 0:
            absorbed = min(self.shield, amount)
            self.shield -= absorbed
            amount -= absorbed
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
