import pygame
import math
from .math_engine import quat_identity, rotate_pitch, rotate_yaw, rotate_roll, get_forward_from_quat, get_basis_from_quat
from .constants import PLAYER_MAX_HP, MAX_THRUST, MAX_RETRO_THRUST, DRAG, MAX_SPEED, HIT_FLASH_DURATION, PLAYER_COLLISION_RADIUS
from .laser import Laser
from .particle import Particle

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

    @property
    def current_speed(self):
        return math.sqrt(self.vel[0]**2 + self.vel[1]**2 + self.vel[2]**2)

    def update(self, dt, handler, keys, lasers, particles, enemy_projectiles):
        # ── INPUT ─────────────────────────────────
        lx, ly = handler.stick_left()
        rx, _  = handler.stick_right()
        fire_l = handler.trigger_left()  > 0.5
        fire_r = handler.trigger_right() > 0.5
        fire_pressed = fire_l or fire_r

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
        self._key_target_closest = keys[pygame.K_t] and self._target_key_cd <= 0
        self._key_cycle_target   = keys[pygame.K_y] and self._target_key_cd <= 0
        if keys[pygame.K_t] or keys[pygame.K_y]:
            if self._target_key_cd <= 0:
                self._target_key_cd = 0.25   # 250 ms debounce

        if handler.held('R1'): self.throttle = min(1.0, self.throttle + dt * 2.8)
        if handler.held('L1'): self.throttle = max(-1.0, self.throttle - dt * 2.8)
        if handler.just_pressed('R3'): self.throttle = 0.0

        # ── ROTATION ──────────────────────────────
        PITCH_RATE = 3.0
        YAW_RATE   = 2.5
        ROLL_RATE  = 3.0

        if abs(ly) > 0.01:
            self.orientation = rotate_pitch(self.orientation,  ly * PITCH_RATE * dt)
        if abs(rx) > 0.01:
            self.orientation = rotate_yaw  (self.orientation,  rx * YAW_RATE   * dt)
        if abs(lx) > 0.01:
            self.orientation = rotate_roll (self.orientation,  lx * ROLL_RATE  * dt)

        self.weapons_cooldown = max(0.0, self.weapons_cooldown - dt)
        self.hit_flash        = max(0.0, self.hit_flash - dt)
        self._target_key_cd   = max(0.0, self._target_key_cd  - dt)

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
        if fire_pressed and self.weapons_cooldown <= 0:
            forward, right, _ = get_basis_from_quat(self.orientation)
            rfx, rfy, rfz = forward
            rrx, rry, rrz = right
            offset = 40
            for side in (-1, 1):
                wing_pos = [
                    self.pos[0] + rrx * offset * side + rfx * 20,
                    self.pos[1] + rry * offset * side + rfy * 20,
                    self.pos[2] + rrz * offset * side + rfz * 20,
                ]
                lasers.append(Laser(wing_pos, self.orientation))
            self.weapons_cooldown = 0.25
            
        # ── CHECK PROJECTILE HITS ─────────────────────
        for bolt in enemy_projectiles[:]:
            if math.dist((bolt['x'], bolt['y'], bolt['z']), self.pos) < PLAYER_COLLISION_RADIUS:
                self.take_damage(15)
                enemy_projectiles.remove(bolt)
                for _ in range(12):
                    particles.append(Particle(self.pos[0], self.pos[1], self.pos[2]))
                    
    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
        self.hit_flash = HIT_FLASH_DURATION

    # ── TARGETING METHODS ────────────────────────────────────────────

    def target_closest(self, enemies):
        """Lock onto the nearest living enemy."""
        if not enemies:
            self.active_target = None
            return
        self.active_target = min(
            enemies,
            key=lambda e: math.dist(self.pos, (e.x, e.y, e.z))
        )

    def cycle_targets(self, enemies):
        """Advance to the next enemy in the list (wraps around)."""
        if not enemies:
            self.active_target = None
            return
        if self.active_target not in enemies:
            self.active_target = enemies[0]
            return
        idx = enemies.index(self.active_target)
        self.active_target = enemies[(idx + 1) % len(enemies)]

    def clear_dead_target(self, enemies):
        """Nullify the active target if it has been destroyed."""
        if self.active_target is not None and self.active_target not in enemies:
            self.active_target = None
