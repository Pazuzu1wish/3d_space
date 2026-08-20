# TODO: rename to ship so these could have alignments (friendly, neutral, hostile)

import math
import random
import pygame

from src.math_engine import (
    ray_sphere_intersection,
    world_to_camera,
    get_forward_from_quat,
    calculate_lead_position
)
from src.constants import (
    MG_COOLDOWN, WEAPON_SPREAD, TRAIL_LIFE_DIVISOR,
    DRONE_DETONATION_RANGE, DRONE_EXPLOSION_RADIUS, DRONE_MAX_DAMAGE,
    BARREL_ROLL_DURATION, PLAYER_COLLISION_RADIUS, SNIPER_ACCURACY,
    PLAYER_COLLISION_RADIUS
)

from src.projectile import (
    MachineGunBolt, HomingBolt, SniperBeam,
    CorvetteTurret, StealthShotgun
)
from src.physics import (newtonian_integrate, approaching_too_fast,
update_orientation_from_velocity)
from src.object_pool import TrailPool
from src.mesh_loader import get_ship_mesh


# ──────────────────────────────────────────────
#  BASE ENEMY
# ──────────────────────────────────────────────

class Enemy:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.hp = 1

        self.vx = self.vy = self.vz = 0.0

        self.forward = (0, 0, 1)
        self.right = (1, 0, 0)
        self.up = (0, 1, 0)

        # --- ADD THIS: Default hit radius for small enemies ---
        self.hit_radius = 50.0
        
        # --- Spawn immunity timer (prevents collision damage right after spawning) ---
        self.spawn_immunity_timer = 10.0

        # ... existing code ...
        self.base_color = (255, 255, 255)
        self.shielded = False
        self.shield = 0.0
        self.max_shield = 0.0
        self.shield_hit_flash_until = 0
        self.shield_break_flash_until = 0
        # engine_trail kept as empty list for legacy compatibility;
        # the live TrailPool is created after subclass sets engine_offsets
        self.engine_trail = []  # legacy — do not use directly

        # Engine customization (override in subclasses)
        self.engine_offsets = [(0, 0, -35)]  # Local (x, y, z) offsets for thrusters
        self.engine_color = (200, 200, 255)
        self.engine_size = 4.0
        self.trail_life = 0.5
        self.engine_pulse_rate = 8.0
        self.engine_time = random.uniform(0, 100)
        self._last_dist = 0.0
        self.trail_drift = 50.0

        # TrailPool is initialised in _init_trail_pool(), called by subclasses
        # after they have set engine_offsets / trail_life.
        self._trail_pool: TrailPool | None = None

        # ── Newtonian physics (override per subclass) ──────────────
        self.max_speed      = 1500.0   # terminal velocity cap (u/s)
        self.thrust         = 5000.0   # main engine force (u/s²)
        self.lateral_thrust = 0.35     # fraction of thrust for lateral/retro burns
        self.turn_rate      = 3.0      # max heading rotation (rad/s)
        self.drag           = 0.3      # linear drag coefficient

    def get_mesh(self):
        return self.verts, self.faces

    def apply_scale(self, factor):
        self.mesh_scale = factor
        self.hit_radius *= factor
        
        # Scale engine placement, size, and trail spread
        self.engine_offsets = [(ox * factor, oy * factor, oz * factor) for ox, oy, oz in self.engine_offsets]
        self.engine_size *= factor
        self.trail_drift *= factor

        # If any legacy rendering code relies on the vertex dictionary directly:
        if hasattr(self, 'verts'):
            for k, v in self.verts.items():
                self.verts[k] = (v[0] * factor, v[1] * factor, v[2] * factor)


    def _camera_z(self, player_pos, player_orientation):
        px, py, pz = player_pos
        _, _, cz = world_to_camera(
            self.x, self.y, self.z,
            px, py, pz,
            player_orientation
        )
        return cz

    def _apply_banking(self, target_v, dt):
        ax = target_v[0] - self.vx
        ay = target_v[1] - self.vy
        az = target_v[2] - self.vz

        roll_signal = (
                ax * self.right[0] +
                ay * self.right[1] +
                az * self.right[2]
        )

        roll = max(-1.5, min(1.5, roll_signal * 0.002))

        ux, uy, uz = self.up
        rx, ry, rz = self.right

        ux += rx * roll
        uy += ry * roll
        uz += rz * roll

        ulen = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
        ux, uy, uz = ux / ulen, uy / ulen, uz / ulen

        fx, fy, fz = self.forward
        rx = fy * uz - fz * uy
        ry = fz * ux - fx * uz
        rz = fx * uy - fy * ux

        self.up = (ux, uy, uz)
        self.right = (rx, ry, rz)

    # ── BARREL ROLL ────────────────────────────────────────────────

    def _barrel_roll(self, dt, roll_speed=1.0):
        """Rapid roll maneuver – useful for dodging shots and evading pursuit.

        To trigger:
            roll_speed = random.choice([-1.0, 1.0])  # left or right
            self._roll_direction = roll_speed
            self._roll_timer = BARREL_ROLL_DURATION

        Call this at the top of update(), right after self.engine_time += dt
        """

        if not hasattr(self, "_roll_timer"):
            self._roll_timer = 0.0
            self._roll_direction = 0.0

        if self._roll_timer > 0:
            self._roll_timer -= dt * roll_speed

            # Roll speed should curve so it doesn’t zip to full rotation instantly
            roll_amount = 0.0
            if self._roll_timer > BARREL_ROLL_DURATION - 0.25:
                # smooth ease-in
                roll_amount = (1.0 - (self._roll_timer / BARREL_ROLL_DURATION))**2
            else:
                # easy-out (constant roll for middle portion, not used in this version)
                roll_amount = 1.0

            roll = math.sin(math.radians(180.0 * roll_amount)) * self._roll_direction

            ux, uy, uz = self.up
            rx, ry, rz = self.right

            # Apply rotation around forward axis (roll)
            new_ux = ux * math.cos(roll) - rx * math.sin(roll)
            new_uy = uy * math.cos(roll) - ry * math.sin(roll)
            new_uz = uz * math.cos(roll) - rz * math.sin(roll)

            new_rx = rx * math.cos(roll) + ux * math.sin(roll)
            new_ry = ry * math.cos(roll) + uy * math.sin(roll)
            new_rz = rz * math.cos(roll) + uz * math.sin(roll)

            self.up = (new_ux, new_uy, new_uz)
            self.right = (new_rx, new_ry, new_rz)

    # ── CINEMATIC UPDATE ──────────────────────────────────────────

    def cinematic_update(self, dt):
        """Drive this enemy from a scripted sequence instead of AI.
        Call from the cinematic instead of update().
        Scripts are set via enemy.cinematic_script = CinematicScript(...)
        """
        if not hasattr(self, 'cinematic_script') or self.cinematic_script is None:
            # fallback: pure kinematic, no orientation update
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.z += self.vz * dt
            return

        self.engine_time += dt
        self.cinematic_script.step(self, dt)
        self._spawn_engine_trail()
        self._update_engine_trail(dt)


    # ── NEWTONIAN PHYSICS ──────────────────────────────────────────

    def _apply_newtonian(self, desired_heading, dt, lateral_force=None):
        newtonian_integrate(self, desired_heading, dt, lateral_force)

    def _approaching_too_fast(self, target_pos, brake_threshold=600.0):
        return approaching_too_fast(self, target_pos, brake_threshold)

    def _update_orientation(self):
        update_orientation_from_velocity(self)

    # Max trail particles per engine hardpoint (kept for reference)
    _TRAIL_CAP_PER_ENGINE = 20

    def _init_trail_pool(self):
        """Create the TrailPool sized for this enemy's engine layout.
        Must be called by subclasses after setting engine_offsets and trail_life.
        """
        cap = self._TRAIL_CAP_PER_ENGINE * max(1, len(self.engine_offsets))
        self._trail_pool = TrailPool(capacity=cap)

    def _spawn_engine_trail(self):
        """Emit one trail particle per engine hardpoint into the TrailPool."""
        # Cull particles if too far
        if self._last_dist > 15000:
            return
        if self._trail_pool is None:
            self._init_trail_pool()

        for ox, oy, oz in self.engine_offsets:
            ex = self.x + self.right[0]*ox + self.up[0]*oy + self.forward[0]*oz
            ey = self.y + self.right[1]*ox + self.up[1]*oy + self.forward[1]*oz
            ez = self.z + self.right[2]*ox + self.up[2]*oy + self.forward[2]*oz
            dvx = (random.random() - 0.5) * self.trail_drift
            dvy = (random.random() - 0.5) * self.trail_drift
            dvz = (random.random() - 0.5) * self.trail_drift
            self._trail_pool.spawn(
                ex, ey, ez,
                dvx, dvy, dvz,
                self.trail_life,
                self.engine_color,
                self.engine_size,
            )

    def _update_engine_trail(self, dt):
        """Advance the TrailPool (fully vectorised, zero allocation)."""
        if self._trail_pool is not None:
            self._trail_pool.update(dt)

    def _submit_engine_trail(self, renderer):
        """Submit live trail particles to the renderer."""
        if self._trail_pool is not None:
            self._trail_pool.submit_to_renderer(renderer, self.trail_life)

    def _submit_engine_glow(self, renderer):
        pulse = (math.sin(self.engine_time * self.engine_pulse_rate) + 1.0) * 0.5
        
        for ox, oy, oz in self.engine_offsets:
            ex = self.x + self.right[0] * ox + self.up[0] * oy + self.forward[0] * oz
            ey = self.y + self.right[1] * ox + self.up[1] * oy + self.forward[1] * oz
            ez = self.z + self.right[2] * ox + self.up[2] * oy + self.forward[2] * oz

            if self._last_dist > 5000:
                # Beacon mode (far away) — single sprite instead of 3
                renderer.submit_sprite(ex, ey, ez, self.engine_color, self.engine_size * 4, is_glow=True, layer='alpha')
            else:
                # Multi-layer bloom (close up)
                core_size = self.engine_size * (1.0 + 0.5 * pulse)
                mid_size = self.engine_size * 2.5 * (1.0 + 0.3 * pulse)
                outer_size = self.engine_size * 5.0 * (1.0 + 0.1 * pulse)

                # Outer soft halo
                r, g, b = self.engine_color
                renderer.submit_sprite(ex, ey, ez, (int(r*0.4), int(g*0.4), int(b*0.4)), outer_size, is_glow=True, layer='alpha')
                # Mid colored layer
                renderer.submit_sprite(ex, ey, ez, self.engine_color, mid_size, is_glow=True, layer='alpha')
                # Bright white core
                renderer.submit_sprite(ex, ey, ez, (255, 255, 255), core_size, is_glow=True, layer='alpha')

    def dist_to_player(self, player_pos):
        dx = self.x - player_pos[0]
        dy = self.y - player_pos[1]
        dz = self.z - player_pos[2]
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def dist_sq_to_player(self, player_pos):
        dx = self.x - player_pos[0]
        dy = self.y - player_pos[1]
        dz = self.z - player_pos[2]
        return dx * dx + dy * dy + dz * dz

    # --- ADD THIS: Default spherical hit detection ---
    def is_hit(self, px, py, pz):
        """Check if a projectile at (px, py, pz) hits this enemy using spherical collision."""
        dx, dy, dz = self.x - px, self.y - py, self.z - pz
        return (dx * dx + dy * dy + dz * dz) < (self.hit_radius ** 2)

    def set_shielded(self, shield_hp=None):
        self.shielded = True
        if shield_hp is None:
            shield_hp = max(2.0, min(50.0, self.max_hp * 0.35 + self.hit_radius * 0.025))
        self.max_shield = float(shield_hp)
        self.shield = self.max_shield
        return self

    def _apply_damage(self, damage=1, shield_damage_mult=1.0, hull_damage_mult=1.0):
        damage = float(damage)
        if damage <= 0:
            return 0.0

        if self.shielded and self.shield > 0:
            shield_damage = damage * shield_damage_mult
            absorbed = min(self.shield, shield_damage)
            self.shield -= absorbed
            now = pygame.time.get_ticks()
            self.shield_hit_flash_until = now + 160

            leftover = max(0.0, damage - (absorbed / max(0.001, shield_damage_mult)))
            if self.shield <= 0:
                self.shield = 0.0
                self.shielded = False
                self.shield_break_flash_until = now + 420

            if leftover <= 0:
                return 0.0
            damage = leftover

        hull_damage = damage * hull_damage_mult
        self.hp -= hull_damage
        return hull_damage

    def on_hit(self, damage=1):
        return self._apply_damage(damage)



    def compute_avoidance_force(self, spatial, player_pos, avoid_player=True, max_range=2000.0):
        """
        Compute a lateral avoidance force to dodge asteroids, enemies, and optionally the player.

        Returns a (vx, vy, vz) force vector pointing away from nearby obstacles,
        scaled by thrust, or None if no avoidance is needed.
        """
        if spatial is None:
            return None

        obstacles_data = []

        # 1. Gather obstacles from the spatial partition
        for obj in spatial.query_nearby((self.x, self.y, self.z), max_range):
            if obj is self:
                continue

            # Check if the object is an asteroid or enemy
            is_asteroid = hasattr(obj, 'split')
            is_enemy = hasattr(obj, 'on_hit') and hasattr(obj, 'hit_radius')

            if is_asteroid or is_enemy:
                try:
                    # EAFP (Easier to Ask for Forgiveness than Permission)
                    # Faster than 3 hasattr checks (x, y, z) for objects we know are valid
                    radius = getattr(obj, 'hit_radius', 100.0)
                    obstacles_data.append((obj.x, obj.y, obj.z, radius))
                except AttributeError:
                    continue

        # 2. Add the player to avoidance (Fixes the issue noted in the original docstring)
        if avoid_player and player_pos is not None:
            # Assuming player has a standard hit radius (e.g., 100.0)
            obstacles_data.append((player_pos[0], player_pos[1], player_pos[2], 100.0))

        avoidance_x = avoidance_y = avoidance_z = 0.0

        # 3. Calculate forces
        for ox, oy, oz, other_radius in obstacles_data:
            dx = self.x - ox
            dy = self.y - oy
            dz = self.z - oz

            dist_sq = dx * dx + dy * dy + dz * dz

            # Skip if perfectly overlapping to avoid division by zero
            if dist_sq < 1.0:
                continue

            # Maximum distance at which we react to this obstacle
            max_dist = (self.hit_radius + other_radius + 200.0) * 1.5

            # Fast Rejection: Use squared distance to skip expensive math.sqrt()
            if dist_sq > max_dist * max_dist:
                continue

            dist = math.sqrt(dist_sq)

            # Inverse distance weighting with quadratic falloff.
            # Because we filtered with max_dist above, dist/max_dist is guaranteed <= 1.0,
            # so we safely removed the max(0.0, ...) check.
            strength = (1.0 - (dist / max_dist)) ** 2

            # Optimization: Group the division to perform 1 division instead of 3
            factor = strength / dist
            avoidance_x += dx * factor
            avoidance_y += dy * factor
            avoidance_z += dz * factor

        # 4. Normalize and scale final vector
        avoid_sq = avoidance_x ** 2 + avoidance_y ** 2 + avoidance_z ** 2

        # Check against a small epsilon rather than exact 0.0 for floating point safety
        if avoid_sq < 1e-8:
            return None

        # Apply thrust scaling (sqrt only computed once for the final vector)
        scale = (self.thrust * 0.6) / math.sqrt(avoid_sq)

        return (
            avoidance_x * scale,
            avoidance_y * scale,
            avoidance_z * scale
        )

    def submit_to_renderer(self, renderer):
        self._submit_engine_trail(renderer)
        self._submit_engine_glow(renderer)
        
        # Warp-in flash (soft puff) if present — fades over warp_flash_timer
        if getattr(self, 'warp_flash_timer', 0) > 0:
            total = getattr(self, 'warp_flash_total', self.warp_flash_timer)
            if total > 0:
                ratio = max(0.0, min(1.0, self.warp_flash_timer / total))
            else:
                ratio = 0.0
            # Size derived from hit radius for reasonable world scale
            size = max(150.0, getattr(self, 'hit_radius', 100.0) * 3.0)
            alpha = int(255 * ratio)
            # Bright white core with high alpha; submit as nebula so it soft-fades and scales with distance
            renderer.submit_nebula(self.x, self.y, self.z, (255, 255, 255), size, alpha=alpha, layer='alpha')

        self._submit_shield_visual(renderer)

        scale = getattr(self, 'mesh_scale', 1.0)
        
        # Multiply the orientation vectors by the scale factor
        s_right = (self.right[0] * scale, self.right[1] * scale, self.right[2] * scale)
        s_up    = (self.up[0] * scale, self.up[1] * scale, self.up[2] * scale)
        s_fwd   = (self.forward[0] * scale, self.forward[1] * scale, self.forward[2] * scale)

        renderer.submit_baked_mesh(
            (self.x, self.y, self.z), s_right, s_up, s_fwd, self.baked_mesh
        )

    def _submit_shield_visual(self, renderer):
        now = pygame.time.get_ticks()
        hit_flash = max(0.0, (self.shield_hit_flash_until - now) / 160.0)
        break_flash = max(0.0, (self.shield_break_flash_until - now) / 420.0)

        if not self.shielded and break_flash <= 0:
            return

        shield_ratio = (self.shield / self.max_shield) if self.max_shield > 0 else 0.0
        radius = getattr(self, 'hit_radius', 80.0)
        alpha = int(min(220, (28 if self.shielded else 0) + hit_flash * 170 + break_flash * 210))
        if alpha <= 0:
            return

        pulse = (math.sin(now * 0.018) + 1.0) * 0.5
        size = radius * (2.6 + pulse * 0.12 + hit_flash * 0.55 + break_flash * 1.0)
        color = (
            int(40 + 70 * (1.0 - shield_ratio)),
            int(185 + 45 * hit_flash),
            255,
        ) if self.shielded else (255, 245, 150)
        renderer.submit_nebula(self.x, self.y, self.z, color, size, alpha=alpha, layer='alpha')


# ──────────────────────────────────────────────
#  MOVEMENT PATTERNS
# ──────────────────────────────────────────────

def _pattern_direct(t, phase, speed):
    return (0.0, 0.0, 0.0)


def _pattern_weave(t, phase, speed):
    amp = speed * 0.55
    return (math.sin(t * 1.8 + phase) * amp, 0.0, 0.0)


def _pattern_wobble(t, phase, speed):
    amp = speed * 0.4
    return (
        math.sin(t * 2.5 + phase) * amp,
        math.cos(t * 2.8 + phase) * amp,
        0.0,
    )


def _pattern_spiral(t, phase, speed):
    amp = speed * 0.65
    return (
        math.sin(t * 1.4 + phase) * amp,
        math.cos(t * 1.4 + phase) * amp,
        0.0,
    )


def _pattern_zigzag(t, phase, speed):
    amp = speed * 0.8
    sign = 1.0 if math.sin(t * 1.1 + phase) >= 0 else -1.0
    return (sign * amp, 0.0, 0.0)


def _pattern_corkscrew(t, phase, speed):
    amp = speed * 0.5
    return (
        math.sin(t * 2.2 + phase) * amp,
        math.cos(t * 2.0 + phase) * amp * 0.6,
        0.0,
    )


PATTERNS = [
    _pattern_direct,
    _pattern_weave,
    _pattern_wobble,
    _pattern_spiral,
    _pattern_zigzag,
    _pattern_corkscrew,
]

PATTERN_MAP = {
    'direct': _pattern_direct,
    'weave': _pattern_weave,
    'wobble': _pattern_wobble,
    'spiral': _pattern_spiral,
    'zigzag': _pattern_zigzag,
    'corkscrew': _pattern_corkscrew,
}


# ──────────────────────────────────────────────
#  SUICIDE DRONE
# ──────────────────────────────────────────────

class SuicideDrone(Enemy):

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 1
        self.max_hp = 1
        self.base_color = (255, 30, 30)

        # Single bright red thruster
        self.engine_offsets = [(0, 0, -20)]
        self.engine_color = (255, 120, 80)
        self.engine_size = 5.0
        self.engine_pulse_rate = 15.0
        self.trail_life = 0.4
        self.trail_drift = 120.0

        self.t = 0
        self.pattern = _pattern_weave
        self.pattern_phase = random.uniform(0, math.pi * 2)
        self._pattern_cache = None
        self._pattern_check_timer = 0.0
        self._flicker = 0

        # ── Newtonian physics ──
        self.max_speed      = 5600.0
        self.thrust         = 9000.0
        self.lateral_thrust = 0.5
        self.turn_rate      = 1.5
        self.drag           = 0.2

        self.hit_radius = 100
        self.did_detonate = False

        # Mesh loaded from assets/drone.obj + drone.mtl
        self.baked_mesh = get_ship_mesh('drone')
        self.verts = {f'v{i}': tuple(row) for i, row in enumerate(self.baked_mesh.v_data)}
        self.faces = [
            {'v': [f'v{self.baked_mesh.f_idx[i, 0]}',
                   f'v{self.baked_mesh.f_idx[i, 1]}',
                   f'v{self.baked_mesh.f_idx[i, 2]}'],
             'color': tuple(self.baked_mesh.f_col[i])}
            for i in range(len(self.baked_mesh.f_idx))
        ]

        self.spawn_immunity_timer = 20.0

        self.apply_scale(2.5)

    def set_pattern(self, pattern_name):
        if pattern_name in PATTERN_MAP:
            self.pattern = PATTERN_MAP[pattern_name]

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None, spatial=None):
        self.t += dt
        self.engine_time += dt
        self._pattern_check_timer += dt

        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        if self.pattern is not None:
            active_pattern = self.pattern
        elif self._pattern_check_timer >= 0.5:
            self._pattern_check_timer = 0.0
            fwd = get_forward_from_quat(player_orientation)

            dot = nx * fwd[0] + ny * fwd[1] + nz * fwd[2]

            if dot < -0.82:
                self._pattern_cache = _pattern_direct
            else:
                if self._pattern_cache is _pattern_direct:
                    self._pattern_cache = random.choice(PATTERNS[1:])
                elif self._pattern_cache is None:
                    self._pattern_cache = random.choice(PATTERNS[1:])

            active_pattern = self._pattern_cache
        else:
            active_pattern = self._pattern_cache or _pattern_weave

        # Pattern offset becomes a lateral force impulse
        offset = active_pattern(self.t, self.pattern_phase, 1.0)
        lat_force = (
            offset[0] * self.thrust * 0.55,
            offset[1] * self.thrust * 0.55,
            offset[2] * self.thrust * 0.55,
        )

        # Proximity detonation (Ballistic Missile behavior)
        if dist < DRONE_DETONATION_RANGE and self.spawn_immunity_timer <= 0.0:
            self.detonate(player)
            return

        # Proximity visual cue: pulse faster as it gets closer
        if dist < 1000:
            proximity_factor = 1.0 - (dist / 1000.0)
            self.engine_pulse_rate = 15.0 + proximity_factor * 30.0

        desired_heading = (nx, ny, nz)
        
        # Compute collision avoidance (avoid asteroids and enemies, but NOT the player - this is a suicide drone!)
        avoidance_force = self.compute_avoidance_force(spatial, player_pos, avoid_player=False, max_range=2500.0)
        
        # Blend avoidance with pattern-based movement
        if avoidance_force is not None:
            lat_force = (
                lat_force[0] + avoidance_force[0] * 0.7,
                lat_force[1] + avoidance_force[1] * 0.7,
                lat_force[2] + avoidance_force[2] * 0.7,
            )
        
        self._apply_newtonian(desired_heading, dt, lateral_force=lat_force)
        self._spawn_engine_trail()
        self._update_engine_trail(dt)

        if self._flicker > 0:
            self._flicker -= dt * 8

    def detonate(self, player=None):
        """Triggers proximity explosion and deals radial damage to player."""
        if player:
            dist = self.dist_to_player(player.pos)
            # Radial damage falloff: full damage at center, 0 at EXPLOSION_RADIUS
            falloff = max(0.0, 1.0 - (dist / DRONE_EXPLOSION_RADIUS))
            damage = DRONE_MAX_DAMAGE * falloff
            player.take_damage(damage)
        
        self.did_detonate = True
        self.hp = 0

    def on_hit(self, damage=1):
        hull_damage = self._apply_damage(damage)
        if hull_damage > 0:
            self._flicker = 1
        if self._pattern_cache is _pattern_direct:
            self._pattern_cache = random.choice(PATTERNS[1:])


# ──────────────────────────────────────────────
#  DOGFIGHTER
# ──────────────────────────────────────────────

class Dogfighter(Enemy):
    SPEED = 2000
    FIRE_RANGE = 4500
    IDEAL_RANGE = 1000
    CIRCLE_RADIUS = 1500

    def __init__(self, x, y, z):
        super().__init__(x, y, z)

        self.hp = 10
        self.max_hp = 10
        self.t = 0
        self.base_color = (50, 0, 255)

        # Twin Blue Thrusters – repositioned to tail top
        self.engine_offsets = [(-32, -10, -45), (32, -10, -45)]
        self.engine_color = (60, 150, 255)
        self.engine_size = 1.5
        self.engine_pulse_rate = 8.0
        self.trail_life = 0.6
        self.trail_drift = 60.0
        self.hit_radius = 200

        self.mg_timer = 0.0
        self.bolt_timer = random.uniform(1.0, 2.0)

        self.mode = 'positioning'
        self.mode_timer = random.uniform(2.0, 4.0)
        self.phase = random.uniform(0, math.pi * 2)
        
        # Pattern and randomization settings
        self.pattern = random.choice(PATTERNS[1:])  # Skip 'direct'
        self.circle_sign = random.choice([1.0, -1.0])
        self.ideal_range = random.uniform(800, 1200)
        self.circle_radius = random.uniform(2000, 2800)
        self.pattern_scale = 2.5  # Dogfighters need larger sweeps than drones

        # ── Newtonian physics ──
        self.max_speed      = 5000.0
        self.thrust         = 5000.0
        self.lateral_thrust = 0.35
        self.turn_rate      = 2.0
        self.drag           = 0.01
        
        self._flicker = 0

        # Mesh loaded from assets/dogfighter.obj + dogfighter.mtl
        self.baked_mesh = get_ship_mesh('dogfighter')
        self.verts = {f'v{i}': tuple(row) for i, row in enumerate(self.baked_mesh.v_data)}
        self.faces = [
            {'v': [f'v{self.baked_mesh.f_idx[i, 0]}',
                   f'v{self.baked_mesh.f_idx[i, 1]}',
                   f'v{self.baked_mesh.f_idx[i, 2]}'],
             'color': tuple(self.baked_mesh.f_col[i])}
            for i in range(len(self.baked_mesh.f_idx))
        ]

        self.apply_scale(2.5)



    def _player_forward(self, orientation):
        return get_forward_from_quat(orientation)

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None,
               spatial=None):
        self.t += dt
        self.engine_time += dt
        self.mg_timer -= dt
        self.bolt_timer -= dt
        self.mode_timer -= dt

        px, py, pz = player_pos
        dist_to_player = self.dist_to_player(player_pos)
        self._last_dist = dist_to_player

        # ⚡ 1. EVASIVE BARREL ROLL
        # If the player's crosshair is aiming right at us, panic and dodge!
        dx, dy, dz = self.x - px, self.y - py, self.z - pz
        d_len = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        nx_e, ny_e, nz_e = dx / d_len, dy / d_len, dz / d_len
        p_fwd = get_forward_from_quat(player_orientation)

        # Dot product: -1.0 means player is looking dead at us
        aim_dot = nx_e * p_fwd[0] + ny_e * p_fwd[1] + nz_e * p_fwd[2]

        if aim_dot < -0.96 and getattr(self, '_roll_timer', 0) <= 0:
            self._roll_timer = BARREL_ROLL_DURATION
            self._roll_direction = random.choice([-1.0, 1.0])
            self.lateral_thrust = 1.2  # Boost lateral thrusters temporarily to actually move out of the way

        # Execute roll if active
        if getattr(self, '_roll_timer', 0) > 0:
            self._barrel_roll(dt, roll_speed=self._roll_direction * 2.5)
            if self._roll_timer <= 0:
                self.lateral_thrust = 0.35  # Reset to normal

        # --- COLLISION AVOIDANCE & POSITIONING ---
        if dist_to_player < 800:
            self.mode = 'positioning'
            self.mode_timer = random.uniform(1.5, 3.0)
            target_x = self.x + self.right[0] * 1000 * self.circle_sign
            target_y = self.y + self.right[1] * 1000 * self.circle_sign
            target_z = self.z + self.right[2] * 1000 * self.circle_sign

        elif self.mode_timer <= 0:
            if self.mode == 'positioning':
                self.mode = 'attack_run'
                self.mode_timer = random.uniform(2.0, 4.0)
            else:
                self.mode = 'positioning'
                self.mode_timer = random.uniform(3.0, 5.0)
                self.phase = random.uniform(0, math.pi * 2)
                self.pattern = random.choice(PATTERNS[1:])

        # ⚡ 2. PREDICTIVE FLIGHT PATH
        if dist_to_player >= 800:
            if self.mode == 'positioning':
                pfw = self._player_forward(player_orientation)
                behind_x = px - pfw[0] * self.ideal_range
                behind_y = py - pfw[1] * self.ideal_range
                behind_z = pz - pfw[2] * self.ideal_range

                offset = self.pattern(self.t, self.phase, self.SPEED)
                target_x = behind_x + offset[0] * self.pattern_scale * self.circle_sign
                target_y = behind_y + offset[1] * self.pattern_scale
                target_z = behind_z + offset[2] * self.pattern_scale
            else:
                # TRUE PREDICTIVE AIMING: Fly towards where the player WILL be
                if player is not None and hasattr(player, 'vel'):
                    p_vx, p_vy, p_vz = player.vel
                    time_to_impact = dist_to_player / 15000.0  # Machine gun speed
                    target_x = px + (p_vx * time_to_impact)
                    target_y = py + (p_vy * time_to_impact)
                    target_z = pz + (p_vz * time_to_impact)
                else:
                    target_x, target_y, target_z = px, py, pz

        tdx = target_x - self.x
        tdy = target_y - self.y
        tdz = target_z - self.z
        tdist = math.sqrt(tdx * tdx + tdy * tdy + tdz * tdz) or 1.0
        desired_heading = (tdx / tdist, tdy / tdist, tdz / tdist)

        if self._approaching_too_fast((target_x, target_y, target_z), brake_threshold=500.0):
            spd = math.sqrt(self.vx ** 2 + self.vy ** 2 + self.vz ** 2) or 1.0
            desired_heading = (-self.vx / spd, -self.vy / spd, -self.vz / spd)

        avoid_player = self.mode != 'attack_run'
        avoidance_force = self.compute_avoidance_force(spatial, player_pos, avoid_player=avoid_player, max_range=3000.0)

        if self.mode == 'positioning':
            lat_force = (
                self.right[0] * self.circle_sign * self.thrust * 0.45,
                self.right[1] * self.circle_sign * self.thrust * 0.45,
                self.right[2] * self.circle_sign * self.thrust * 0.45,
            )
            if avoidance_force is not None:
                lat_force = (
                    lat_force[0] + avoidance_force[0] * 0.5,
                    lat_force[1] + avoidance_force[1] * 0.5,
                    lat_force[2] + avoidance_force[2] * 0.5,
                )
        else:
            lat_force = avoidance_force

        self._apply_newtonian(desired_heading, dt, lateral_force=lat_force)

        # ⚡ 3. PREDICTIVE WEAPON FIRING
        if self.mode == 'attack_run' and dist_to_player < self.FIRE_RANGE:
            # Aim weapons at future position, not current position
            if player is not None and hasattr(player, 'vel'):
                # Use your Numba function! Shooter = Enemy, Target = Player
                aim_x, aim_y, aim_z = calculate_lead_position(
                    player_pos=(self.x, self.y, self.z),
                    player_vel=(self.vx, self.vy, self.vz),
                    target_pos=player.pos,
                    target_vel=player.vel,
                    projectile_speed=15000.0  # MG Speed
                )
            else:
                aim_x, aim_y, aim_z = px, py, pz
                
            aim_dx, aim_dy, aim_dz = aim_x - self.x, aim_y - self.y, aim_z - self.z
            aim_dist = math.sqrt(aim_dx*aim_dx + aim_dy*aim_dy + aim_dz*aim_dz) or 1.0
            aim_dir = (aim_dx/aim_dist, aim_dy/aim_dist, aim_dz/aim_dist)

            dot = (self.forward[0] * aim_dir[0] +
                   self.forward[1] * aim_dir[1] +
                   self.forward[2] * aim_dir[2])

            # If they are aiming perfectly at the intercept point, light you up
            if dot > 0.85:
                if self.mg_timer <= 0:
                    self.mg_timer = MG_COOLDOWN
                    self._fire_projectile(aim_dir, global_projectiles, w_type='mg')

                if self.bolt_timer <= 0:
                    self.bolt_timer = random.uniform(5.0, 8.0)
                    self._fire_projectile(aim_dir, global_projectiles, w_type='bolt')

        self._spawn_engine_trail()
        self._update_engine_trail(dt)
        if self._flicker > 0:
            self._flicker -= dt * 8
    def _fire_projectile(self, aim_dir, global_projectiles, w_type='mg'):
        if global_projectiles is None: return

        # Offset spawn position outside the ship's hit radius to prevent self-collision
        spawn_offset = self.hit_radius + 20.0
        ox = self.x + aim_dir[0] * spawn_offset
        oy = self.y + aim_dir[1] * spawn_offset
        oz = self.z + aim_dir[2] * spawn_offset

        if w_type == 'mg':
            proj_speed = 15000
            spread = 0.03
            ax = aim_dir[0] + random.uniform(-spread, spread)
            ay = aim_dir[1] + random.uniform(-spread, spread)
            az = aim_dir[2] + random.uniform(-spread, spread)
            n = math.sqrt(ax * ax + ay * ay + az * az) or 1
            ax, ay, az = ax / n, ay / n, az / n

            vx = ax * proj_speed + self.vx * 0.3
            vy = ay * proj_speed + self.vy * 0.3
            vz = az * proj_speed + self.vz * 0.3

            bolt = MachineGunBolt(ox, oy, oz, vx, vy, vz)
            bolt.owner = self
            global_projectiles.append(bolt)

        elif w_type == 'bolt':
            proj_speed = 2200
            vx = aim_dir[0] * proj_speed + self.vx * 0.5
            vy = aim_dir[1] * proj_speed + self.vy * 0.5
            vz = aim_dir[2] * proj_speed + self.vz * 0.5

            bolt = HomingBolt(ox, oy, oz, vx, vy, vz)
            bolt.owner = self
            global_projectiles.append(bolt)

    def on_hit(self, damage=1):
        hull_damage = self._apply_damage(damage)
        if hull_damage > 0:
            self._flicker = 1
            self.mode = 'attack_run'
            self.mode_timer = 3.0


# ===========================================================
# Sniper
# ===========================================================

class Sniper(Enemy):
    SPEED = 800          # was 1200, stays far but catchable now
    FIRE_RANGE = 7000
    FLEE_RANGE = 3500

    def __init__(self, x, y, z):
        super().__init__(x, y, z)

        self.hp = 1
        self.max_hp = 1
        self.hit_radius = 120       # was 70
        self.base_color = (210, 165, 45)

        # Single deep green thruster at back of long barrel
        self.engine_offsets = [(0, 0, -90)]
        self.engine_color = (255, 50, 50)
        self.engine_size = 6.0
        self.engine_pulse_rate = 2.0
        self.trail_life = 1.2
        self.trail_drift = 10.0

        self.hit_radius = 120

        self.state = 'aiming'
        self.timer = random.uniform(2.0, 4.0)
        self._flicker = 0

        # ── Newtonian physics ──
        self.max_speed      = 4100.0
        self.thrust         = 3000.0
        self.lateral_thrust = 0.2
        self.turn_rate      = 2.0
        self.drag           = 0.35

        # Mesh loaded from assets/sniper.obj + sniper.mtl
        self.baked_mesh = get_ship_mesh('sniper')
        self.verts = {f'v{i}': tuple(row) for i, row in enumerate(self.baked_mesh.v_data)}
        self.faces = [
            {'v': [f'v{self.baked_mesh.f_idx[i, 0]}',
                   f'v{self.baked_mesh.f_idx[i, 1]}',
                   f'v{self.baked_mesh.f_idx[i, 2]}'],
             'color': tuple(self.baked_mesh.f_col[i])}
            for i in range(len(self.baked_mesh.f_idx))
        ]

        self.apply_scale(2.5)

    
    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None, spatial=None):
        self.timer -= dt
        self.engine_time += dt
        px, py, pz = player_pos

        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        if dist < self.FLEE_RANGE:
            self.state = 'fleeing'
            self.base_color = (20, 20, 30)      # was (255, 255, 255)
            self.engine_size = 0.0              # kill trail while cloaked
        elif self.state == 'fleeing' and dist > self.FLEE_RANGE + 1000:
            self.state = 'aiming'
            self.timer = 2.0
            self.base_color = (210, 165, 45)   # uncloak on re-engage
            self.engine_size = 6.0

        if self.state == 'aiming' and self.timer <= 0:
            self.state = 'charging'
            self.timer = 1.5

        if self.state == 'charging':
            # --- LIGHT-SPEED RAYCAST LOS CHECK ---
            dx_p, dy_p, dz_p = px - self.x, py - self.y, pz - self.z
            dist_f = math.sqrt(dx_p*dx_p + dy_p*dy_p + dz_p*dz_p) or 1.0
            
            blocked = False
            hit_dist = dist_f
            hit_obj = None
            if spatial is not None:
                mid_x, mid_y, mid_z = self.x + dx_p * 0.5, self.y + dy_p * 0.5, self.z + dz_p * 0.5
                nearby = spatial.query_nearby((mid_x, mid_y, mid_z), dist_f * 0.5 + 500)
                for obj in nearby:
                    if obj is self or obj is player: continue
                    if hasattr(obj, 'hit_radius'):
                        t = ray_sphere_intersection((self.x, self.y, self.z), self.forward, (obj.x, obj.y, obj.z), obj.hit_radius)
                        if 0 < t < hit_dist:
                            blocked = True
                            hit_dist = t
                            hit_obj = obj
            
            if blocked:
                # Cancel charge-up
                self.state = 'aiming'
                self.timer = 1.5
                self.base_color = (210, 165, 45)
            else:
                flash = int((math.sin(self.timer * 20) + 1) * 127)
                self.base_color = (255, flash, flash)

                if self.timer <= 0:

                    # closest approach of beam line to player center
                    cx = (dy_p/dist_f)*self.forward[2] - (dz_p/dist_f)*self.forward[1]
                    cy = (dz_p/dist_f)*self.forward[0] - (dx_p/dist_f)*self.forward[2]
                    cz = (dx_p/dist_f)*self.forward[1] - (dy_p/dist_f)*self.forward[0]
                    perp_dist = math.sqrt(cx*cx + cy*cy + cz*cz) * dist_f
                    
                    dot = (dx_p/dist_f)*self.forward[0] + (dy_p/dist_f)*self.forward[1] + (dz_p/dist_f)*self.forward[2]
                    
                    if player is not None and dot > 0 and perp_dist < PLAYER_COLLISION_RADIUS:
                        # Roll for hit success based on tunable constant
                        if random.random() < SNIPER_ACCURACY:
                            player.take_damage(50)
                    
                    # spawn visual beam regardless of hit
                    if global_projectiles is not None:
                        spawn_offset = self.hit_radius + 20.0
                        global_projectiles.append(SniperBeam(
                            self.x + self.forward[0] * spawn_offset,
                            self.y + self.forward[1] * spawn_offset,
                            self.z + self.forward[2] * spawn_offset,
                            self.forward[0] * 32000,
                            self.forward[1] * 32000,
                            self.forward[2] * 32000
                        ))
                    
                    self.state = 'aiming'
                    self.timer = random.uniform(4.0, 6.0)
                    self.base_color = (210, 165, 45)

        if self.state == 'fleeing':
            # Rotate away from player and thrust
            desired_heading = (-nx, -ny, -nz)
            avoidance_force = self.compute_avoidance_force(spatial, player_pos, avoid_player=False, max_range=2500.0)
            self._apply_newtonian(desired_heading, dt, lateral_force=avoidance_force)
        elif self.state == 'aiming':
            # Face player (for accurate raycast), drift laterally
            desired_heading = (nx, ny, nz)
            lat_force = (
                self.right[0] * self.thrust * 0.18,
                self.right[1] * self.thrust * 0.18,
                self.right[2] * self.thrust * 0.18,
            )
            # Blend with avoidance
            avoidance_force = self.compute_avoidance_force(spatial, player_pos, avoid_player=True, max_range=2500.0)
            if avoidance_force is not None:
                lat_force = (
                    lat_force[0] + avoidance_force[0] * 0.6,
                    lat_force[1] + avoidance_force[1] * 0.6,
                    lat_force[2] + avoidance_force[2] * 0.6,
                )
            self._apply_newtonian(desired_heading, dt, lateral_force=lat_force)
        elif self.state == 'charging':
            # Hold position: face player for raycast but no thrust (drag bleeds speed)
            desired_heading = (nx, ny, nz)
            avoidance_force = self.compute_avoidance_force(spatial, player_pos, avoid_player=False, max_range=2500.0)
            saved = self.thrust
            self.thrust = 0.0
            self._apply_newtonian(desired_heading, dt, lateral_force=avoidance_force)
            self.thrust = saved

        self._spawn_engine_trail()
        self._update_engine_trail(dt)

    def on_hit(self, damage=1):
        hull_damage = self._apply_damage(damage)
        if hull_damage > 0:
            self._flicker = 1


# =============================================================
# Corvette
# =============================================================

class Corvette(Enemy):
    SPEED = 500
    FIRE_RANGE = 4000

    def __init__(self, x, y, z):
        super().__init__(x, y, z)

        self.hp = 30
        self.max_hp = 30
        self.base_color = (180, 180, 200)

        self.hit_radius = 400

        # Huge thruster block for a massive ship
        self.engine_offsets = [
            (-50, -10, -200), (50, -10, -200),
            (0, 20, -200)
        ]
        self.engine_color = (255, 140, 0)
        self.engine_size = 6.0
        self.engine_pulse_rate = 1.0
        self.trail_life = 0.0
        self.trail_drift = 30.0

        self.turret_timer = 0.0
        self.spawn_timer = random.uniform(5.0, 10.0)
        self._flicker = 0
        self.t = random.uniform(0, 100)

        # ── Newtonian physics ──
        self.max_speed      = 3500.0
        self.thrust         = 2000.0
        self.lateral_thrust = 0.2
        self.turn_rate      = 1.2
        self.drag           = 0.15

        # Mesh loaded from assets/corvette.obj + corvette.mtl
        self.baked_mesh = get_ship_mesh('corvette')
        self.verts = {f'v{i}': tuple(row) for i, row in enumerate(self.baked_mesh.v_data)}
        self.faces = [
            {'v': [f'v{self.baked_mesh.f_idx[i, 0]}',
                   f'v{self.baked_mesh.f_idx[i, 1]}',
                   f'v{self.baked_mesh.f_idx[i, 2]}'],
             'color': tuple(self.baked_mesh.f_col[i])}
            for i in range(len(self.baked_mesh.f_idx))
        ]

        self.apply_scale(2.5)

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None, spatial=None):
        self.t += dt
        self.engine_time += dt
        self.turret_timer -= dt
        self.spawn_timer -= dt

        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        # Compute collision avoidance
        avoidance_force = self.compute_avoidance_force(spatial, player_pos, avoid_player=False, max_range=3500.0)
        self._apply_newtonian((nx, ny, nz), dt, lateral_force=avoidance_force)

        # Weaponry
        if dist < self.FIRE_RANGE and self.turret_timer <= 0:
            self.turret_timer = 0.3
            if global_projectiles is not None:
                spread = 0.05
                ax, ay, az = nx + random.uniform(-spread, spread), ny + random.uniform(-spread, spread), nz + random.uniform(-spread, spread)
                n = math.sqrt(ax * ax + ay * ay + az * az) or 1
                ax, ay, az = ax / n, ay / n, az / n

                spawn_offset = self.hit_radius + 20.0
                bolt = CorvetteTurret(
                    self.x + ax * spawn_offset,
                    self.y + ay * spawn_offset,
                    self.z + az * spawn_offset,
                    ax * 4000 + self.vx * 0.5,
                    ay * 4000 + self.vy * 0.5,
                    az * 4000 + self.vz * 0.5
                )
                bolt.owner = self
                global_projectiles.append(bolt)

        # Drone Spawning
        if self.spawn_timer <= 0 and dist < 12000:
            self.spawn_timer = 8.0
            if global_enemies is not None:
                drone = SuicideDrone(self.x, self.y - 40, self.z)
                drone.vx, drone.vy, drone.vz = self.vx, self.vy - 300, self.vz
                drone.set_pattern(random.choice(['weave', 'wobble', 'spiral', 'zigzag', 'corkscrew']))
                drone.spawn_immunity_timer = 10.0  # 10 second grace period
                global_enemies.append(drone)

        self._spawn_engine_trail()
        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self, damage=1):
        hull_damage = self._apply_damage(damage)
        if hull_damage > 0:
            self._flicker = 1


# =============================================================
# Space Mine (Stationary Explosive)
# =============================================================

class Mine(Enemy):
    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 1
        self.max_hp = 1
        self.hit_radius = 200.0
        self.base_color = (255, 30, 30)
        self.size_mult = 10.0

        self.engine_offsets = []
        self.trail_life = 0.0

        self.did_detonate = False
        self.spawn_immunity_timer = 10.0
        self.life = 25.0

        # Override physical movement speeds so it sits perfectly still
        self.max_speed = 0.0
        self.thrust = 0.0
        self.vx = self.vy = self.vz = 0.0

        self.verts = {}
        self.faces = []

        self._last_player = None
        self._last_spatial = None

        

    def detonate(self, player=None, spatial=None):
        if self.did_detonate:
            return  # Prevent infinite loop if mines explode near each other

        self.did_detonate = True
        self.hp = 0  # Flags for removal in game.py loop

        EXPLOSION_RADIUS = 2000.0
        MAX_DAMAGE = 100.0

        # 1. Damage Player
        if player:
            dist = self.dist_to_player(player.pos)
            if dist < EXPLOSION_RADIUS:
                falloff = max(0.0, 1.0 - (dist / EXPLOSION_RADIUS * 0.8))
                player.take_damage(MAX_DAMAGE * falloff)

        # 2. Damage nearby Enemies and Asteroids
        if spatial:
            nearby = spatial.query_nearby((self.x, self.y, self.z), EXPLOSION_RADIUS)
            for obj in nearby:
                if obj is self:
                    continue
                if hasattr(obj, 'on_hit') and hasattr(obj, 'hit_radius'):
                    # Accurate distance check for AoE application
                    dist_sq = (self.x - obj.x) ** 2 + (self.y - obj.y) ** 2 + (self.z - obj.z) ** 2
                    if dist_sq < EXPLOSION_RADIUS ** 2:
                        obj.on_hit(int(MAX_DAMAGE))

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None,
               spatial=None):
        # Cache references so the on_hit hook can still access them for AoE
        self._last_player = player
        self._last_spatial = spatial

        self.life -= dt
        if self.life <= 0:
            self.hp = 0
            return

        if self.spawn_immunity_timer > 0:
            self.spawn_immunity_timer -= dt

        if self.spawn_immunity_timer <= 0:
            TRIGGER_RADIUS = 2500.0

            # Check player proximity
            if self.dist_to_player(player_pos) < TRIGGER_RADIUS:
                self.detonate(player, spatial)
                return

            # Check asteroid or enemy proximity
            if spatial:
                nearby = spatial.query_nearby((self.x, self.y, self.z), TRIGGER_RADIUS)
                for obj in nearby:
                    if obj is self:
                        continue
                    # Check if it's an asteroid (has 'split') or enemy
                    if hasattr(obj, 'split') or (hasattr(obj, 'on_hit') and hasattr(obj, 'hit_radius')):
                        dist_sq = (self.x - obj.x) ** 2 + (self.y - obj.y) ** 2 + (self.z - obj.z) ** 2
                        if dist_sq < TRIGGER_RADIUS ** 2:
                            self.detonate(player, spatial)
                            return

    def on_hit(self, damage=1):
        # Explode instantly if struck by a laser or projectile
        hull_damage = self._apply_damage(damage)
        if hull_damage > 0 and self.spawn_immunity_timer <= 0:
            self.detonate(self._last_player, self._last_spatial)

    def submit_to_renderer(self, renderer):
        # Discard the mesh rendering completely and render the blinking sprite
        self._submit_shield_visual(renderer)
        flash = (pygame.time.get_ticks() // 200) % 2 == 0
        draw_color = (255, 255, 255) if flash else self.base_color
        renderer.submit_sprite(self.x, self.y, self.z, draw_color, self.size_mult * 2)


# =============================================================
# Minelayer
# =============================================================

class Minelayer(Enemy):
    SPEED = 1400

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 12
        self.max_hp = 12
        self.visible_color = (255, 140, 0)
        self.stealth_color = (20, 20, 30)
        self.base_color = self.stealth_color

        self.hit_radius = 200.0
        self.stealthed = True

        # 4 spaced out thrusters
        self.engine_offsets = [
            (-60, 0, -30), (-20, 0, -30),
            (20, 0, -30), (60, 0, -30)
        ]
        self.engine_color = (255, 210, 0)
        self.engine_size = 5.0
        self.engine_pulse_rate = 4.0
        self.trail_life = 0.5
        self.trail_drift = 80.0

        self.state = 'traveling'
        self.flank_offset = None
        self.bombing_timer = 0.0
        self.heavy_mg_timer = 0.0
        self._flicker = 0

        # ── Newtonian physics ──
        self.max_speed      = 4500.0
        self.thrust         = 4000.0
        self.lateral_thrust = 0.3
        self.turn_rate      = 2.5
        self.drag           = 0.35

        # Mesh loaded from assets/minelayer.obj + minelayer.mtl
        self.baked_mesh = get_ship_mesh('minelayer')
        self.verts = {f'v{i}': tuple(row) for i, row in enumerate(self.baked_mesh.v_data)}
        self.faces = [
            {'v': [f'v{self.baked_mesh.f_idx[i, 0]}',
                   f'v{self.baked_mesh.f_idx[i, 1]}',
                   f'v{self.baked_mesh.f_idx[i, 2]}'],
             'color': tuple(self.baked_mesh.f_col[i])}
            for i in range(len(self.baked_mesh.f_idx))
        ]

        self.apply_scale(2.5)

    def _pick_flank_offset(self, p_fwd):
        dist = random.uniform(3500, 5000)
        phi = random.uniform(0, 2 * math.pi)
        costheta = random.uniform(-0.5, 0.5)
        theta = math.acos(costheta)
        rx = math.sin(theta) * math.cos(phi)
        ry = math.sin(theta) * math.sin(phi)
        rz = math.cos(theta)
        
        # bias away from player forward
        dot = rx * p_fwd[0] + ry * p_fwd[1] + rz * p_fwd[2]
        if dot > 0:
            rx, ry, rz = -rx, -ry, -rz
            
        self.flank_offset = (rx * dist, ry * dist, rz * dist)

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None, spatial=None):
        self.engine_time += dt
        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist
        p_fwd = get_forward_from_quat(player_orientation)

        # State transition: Defensive check
        if dist < 3000:
            self.state = 'defensive'
        elif self.state == 'defensive' and dist > 4500:
            self.state = 'traveling'
            self.flank_offset = None

        if self.state == 'traveling':
            self.stealthed = True
            self.base_color = self.stealth_color
            self.hit_radius = 200.0
            
            if self.flank_offset is None:
                self._pick_flank_offset(p_fwd)
                
            tx, ty, tz = px + self.flank_offset[0], py + self.flank_offset[1], pz + self.flank_offset[2]
            tdx, tdy, tdz = tx - self.x, ty - self.y, tz - self.z
            tdist = math.sqrt(tdx*tdx + tdy*tdy + tdz*tdz)
            
            if tdist < 500:
                self.state = 'bombing'
                self.bombing_timer = 4.0
                
            target_x, target_y, target_z = tx, ty, tz

        elif self.state == 'bombing':
            self.stealthed = False
            self.base_color = self.visible_color
            self.hit_radius = 200.0
            
            # Fly across
            target_x, target_y, target_z = px - p_fwd[0] * 3000, py - p_fwd[1] * 3000, pz - p_fwd[2] * 3000
            
            self.bombing_timer -= dt
            if int(self.bombing_timer * 8) % 8 == 0 and random.random() < 0.3:
                if global_projectiles is not None:
                    # Determine safe drop direction (directly opposite to current velocity)
                    v_mag = math.sqrt(self.vx ** 2 + self.vy ** 2 + self.vz ** 2)
                    if v_mag > 1.0:
                        drop_x, drop_y, drop_z = -self.vx / v_mag, -self.vy / v_mag, -self.vz / v_mag
                    else:
                        # Fallback if stationary
                        drop_x, drop_y, drop_z = -self.up[0], -self.up[1], -self.up[2]
                    spawn_offset = self.hit_radius + 200.0
                    mine = Mine(
                        self.x + drop_x * spawn_offset,
                        self.y + drop_y * spawn_offset,
                        self.z + drop_z * spawn_offset
                    )
                    mine.spawn_immunity_timer = 10
                    global_enemies.append(mine)
            
            if self.bombing_timer <= 0:
                self.state = 'traveling'
                self.flank_offset = None

        elif self.state == 'defensive':
            self.stealthed = False
            self.base_color = self.visible_color
            self.hit_radius = 200.0
            
            # Close in somewhat aggressively if still far, then back away
            if dist > 2000:
                target_x, target_y, target_z = px, py, pz
            else:
                target_x, target_y, target_z = self.x - nx * 1000, self.y - ny * 1000, self.z - nz * 1000
            
            self.heavy_mg_timer -= dt
            if self.heavy_mg_timer <= 0:
                self.heavy_mg_timer = 0.15 # Faster refire
                if global_projectiles is not None:
                    spawn_offset = self.hit_radius + 20.0
                    proj_speed = 12000
                    spread = 0.08
                    ax, ay, az = nx + random.uniform(-spread, spread), ny + random.uniform(-spread, spread), nz + random.uniform(-spread, spread)
                    bolt = MachineGunBolt(
                        self.x + ax * spawn_offset,
                        self.y + ay * spawn_offset,
                        self.z + az * spawn_offset,
                        ax * proj_speed, ay * proj_speed, az * proj_speed
                    )
                    bolt.damage = 4.0  # Even heavier damage
                    bolt.color = (255, 100, 0)
                    bolt.owner = self
                    global_projectiles.append(bolt)

        tdx, tdy, tdz = target_x - self.x, target_y - self.y, target_z - self.z
        tdist = math.sqrt(tdx * tdx + tdy * tdy + tdz * tdz) or 1
        desired_heading = (tdx/tdist, tdy/tdist, tdz/tdist)

        # Brake if closing too fast on target
        if self._approaching_too_fast((target_x, target_y, target_z), brake_threshold=450.0):
            spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2) or 1.0
            desired_heading = (-self.vx/spd, -self.vy/spd, -self.vz/spd)

        # Compute collision avoidance (avoid player except when defensive)
        avoid_player = self.state == 'traveling'
        avoidance_force = self.compute_avoidance_force(spatial, player_pos, avoid_player=avoid_player, max_range=3000.0)
        self._apply_newtonian(desired_heading, dt, lateral_force=avoidance_force)

        if not self.stealthed:
            self.engine_size = 6.0
            self._spawn_engine_trail()
        else:
            self.engine_size = 0.0

        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self, damage=1):
        hull_damage = self._apply_damage(damage)
        if hull_damage > 0:
            self._flicker = 1
        if self.state == 'traveling' and random.random() < 0.3:
            self.flank_offset = None



# =============================================================
# Stealth Interceptor
# =============================================================

class StealthInterceptor(Enemy):
    SPEED = 2500

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 2
        self.max_hp = 2
        self.base_color = (20, 20, 30)

        # Twin thin thrusters
        self.engine_offsets = [(-10, 2, -30), (10, 2, -30)]
        self.engine_color = (180, 0, 255)
        self.engine_size = 4.0
        self.engine_pulse_rate = 12.0
        self.trail_life = 0.3
        self.trail_drift = 20.0

        self.stealthed = True
        self.state = 'traveling'
        self._flicker = 0
        
        self.flank_offset = None
        self.reached_flank = False
        self.hit_radius = 200.0

        # ── Newtonian physics ──
        self.max_speed      = 5300.0
        self.thrust         = 12000.0
        self.lateral_thrust = 0.15
        self.turn_rate      = 5.0
        self.drag           = 0.5

        # Mesh loaded from assets/interceptor.obj + interceptor.mtl
        self.baked_mesh = get_ship_mesh('interceptor')
        self.verts = {f'v{i}': tuple(row) for i, row in enumerate(self.baked_mesh.v_data)}
        self.faces = [
            {'v': [f'v{self.baked_mesh.f_idx[i, 0]}',
                   f'v{self.baked_mesh.f_idx[i, 1]}',
                   f'v{self.baked_mesh.f_idx[i, 2]}'],
             'color': tuple(self.baked_mesh.f_col[i])}
            for i in range(len(self.baked_mesh.f_idx))
        ]

        self.apply_scale(2.5)

    def _pick_flank_offset(self, p_fwd):
        dist = random.uniform(2500, 3500)
        for _ in range(10):
            phi = random.uniform(0, 2 * math.pi)
            costheta = random.uniform(-1, 1)
            theta = math.acos(costheta)
            rx = math.sin(theta) * math.cos(phi)
            ry = math.sin(theta) * math.sin(phi)
            rz = math.cos(theta)
            
            dot = rx * p_fwd[0] + ry * p_fwd[1] + rz * p_fwd[2]
            if dot < 0.2: # Bias away from frontal approach
                self.flank_offset = (rx * dist, ry * dist, rz * dist)
                break
        else:
            self.flank_offset = (-p_fwd[0] * dist, -p_fwd[1] * dist, -p_fwd[2] * dist)
        self.reached_flank = False

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None, spatial=None):
        self.engine_time += dt
        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist
        p_fwd = get_forward_from_quat(player_orientation)

        if self.flank_offset is None:
            self._pick_flank_offset(p_fwd)

        if self.state == 'traveling':
            self.stealthed = True
            self.base_color = (20, 20, 30)
            self.hit_radius = 200.0
            
            if not self.reached_flank:
                tx, ty, tz = px + self.flank_offset[0], py + self.flank_offset[1], pz + self.flank_offset[2]
                tdx, tdy, tdz = tx - self.x, ty - self.y, tz - self.z
                tdist = math.sqrt(tdx*tdx + tdy*tdy + tdz*tdz)
                if tdist < 200:
                    self.reached_flank = True
                target_x, target_y, target_z = tx, ty, tz
            else:
                target_x, target_y, target_z = px, py, pz
                if dist < 1200:
                    self.state = 'attacking'
                    self.stealthed = False
                    self.base_color = (100, 100, 255)
                    self.hit_radius = 200.0

        elif self.state == 'attacking':
            target_x, target_y, target_z = px, py, pz
            if global_projectiles is not None:
                spawn_offset = self.hit_radius + 10.0
                for _ in range(7):
                    spread = WEAPON_SPREAD
                    ax, ay, az = nx + random.uniform(-spread, spread), ny + random.uniform(-spread, spread), nz + random.uniform(-spread, spread)
                    bolt = StealthShotgun(
                        self.x + ax * spawn_offset,
                        self.y + ay * spawn_offset,
                        self.z + az * spawn_offset,
                        ax * 3000, ay * 3000, az * 3000
                    )
                    bolt.owner = self
                    global_projectiles.append(bolt)
            self.state = 'fleeing'
            self.stealthed = True
            self.base_color = (20, 20, 30)
            self.hit_radius = 100.0

        elif self.state == 'fleeing':
            self.stealthed = True
            self.base_color = (20, 20, 30)
            self.hit_radius = 200.0
            target_x, target_y, target_z = self.x - nx * 1000, self.y - ny * 1000, self.z - nz * 1000
            if dist > 4000:
                self._pick_flank_offset(p_fwd)
                self.state = 'traveling'

        tdx, tdy, tdz = target_x - self.x, target_y - self.y, target_z - self.z
        tdist = math.sqrt(tdx * tdx + tdy * tdy + tdz * tdz) or 1
        desired_heading = (tdx/tdist, tdy/tdist, tdz/tdist)

        # Brake when closing on target to prevent overshoot
        if self._approaching_too_fast((target_x, target_y, target_z), brake_threshold=600.0):
            spd = math.sqrt(self.vx**2 + self.vy**2 + self.vz**2) or 1.0
            desired_heading = (-self.vx/spd, -self.vy/spd, -self.vz/spd)

        # Compute collision avoidance (avoid player except when attacking)
        avoid_player = self.state != 'attacking'
        avoidance_force = self.compute_avoidance_force(spatial, player_pos, avoid_player=avoid_player, max_range=2800.0)
        self._apply_newtonian(desired_heading, dt, lateral_force=avoidance_force)

        if not self.stealthed:
            self.engine_size = 6.0
            self._spawn_engine_trail()
        else:
            self.engine_size = 0.0

        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self, damage=1):
        hull_damage = self._apply_damage(damage)
        if hull_damage > 0:
            self._flicker = 1



# =============================================================
# Carrier
# =============================================================

class Carrier(Enemy):

    def __init__(self, x, y, z):
        super().__init__(x, y, z)
        self.hp = 100
        self.max_hp = 100
        self.base_color = (120, 100, 150)

        self.hit_radius = 800.0

        # Massive thruster bank
        self.engine_offsets = [
            (0, -30, -500),  # Center Main Drive
            (-120, 0, -500), (120, 0, -500),  # Outer Drives
            (-60, -40, -500), (60, -40, -500)  # Lower Drives
        ]
        self.engine_color = (200, 100, 255)
        self.engine_size = 25.0
        self.engine_pulse_rate = 1.5
        self.trail_life = 0.5
        self.trail_drift = 20.0

        self.spawn_timer = 5.0
        self.sniper_timer = random.uniform(6.0, 12.0)
        self.bolt_timer = 4.0
        self.mg_timer = 0.1
        self.state = 'idle' # For sniper charge visual
        self._flicker = 0

        # ── Newtonian physics ──
        self.max_speed      = 3500.0
        self.thrust         = 800.0
        self.lateral_thrust = 0.1
        self.turn_rate      = 0.6
        self.drag           = 0.08

        # Mesh loaded from assets/carrier.obj + carrier.mtl
        self.baked_mesh = get_ship_mesh('carrier')
        self.verts = {f'v{i}': tuple(row) for i, row in enumerate(self.baked_mesh.v_data)}
        self.faces = [
            {'v': [f'v{self.baked_mesh.f_idx[i, 0]}',
                   f'v{self.baked_mesh.f_idx[i, 1]}',
                   f'v{self.baked_mesh.f_idx[i, 2]}'],
             'color': tuple(self.baked_mesh.f_col[i])}
            for i in range(len(self.baked_mesh.f_idx))
        ]

        self.apply_scale(2.5)

    def is_hit(self, px, py, pz):
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        local_x = dx * self.right[0]   + dy * self.right[1]   + dz * self.right[2]
        local_y = dx * self.up[0]      + dy * self.up[1]      + dz * self.up[2]
        local_z = dx * self.forward[0] + dy * self.forward[1] + dz * self.forward[2]
        
        scale = getattr(self, 'mesh_scale', 1.0)
        
        hit_x = (-400 * scale) <= local_x <= (400 * scale)
        hit_y = (-120 * scale) <= local_y <= (180 * scale)
        hit_z = (-500 * scale) <= local_z <= (800 * scale)
        
        return hit_x and hit_y and hit_z

    def update(self, dt, player_pos, player_orientation, global_projectiles=None, global_enemies=None, player=None, spatial=None):
        self.spawn_timer -= dt
        self.sniper_timer -= dt
        self.bolt_timer -= dt
        self.mg_timer -= dt
        self.engine_time += dt

        px, py, pz = player_pos
        dx, dy, dz = px - self.x, py - self.y, pz - self.z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        self._last_dist = dist
        nx, ny, nz = dx / dist, dy / dist, dz / dist

        # Movement: orbit at range using Newtonian thrust
        if dist < 7000:
            desired_heading = (-nx, -ny, -nz)  # back away
        elif dist > 9000:
            desired_heading = (nx, ny, nz)     # close in
        else:
            # Hold at distance — thrust laterally to avoid hovering dead still
            desired_heading = (self.right[0], self.right[1], self.right[2])

        # Compute collision avoidance
        avoidance_force = self.compute_avoidance_force(spatial, player_pos, avoid_player=False, max_range=4000.0)
        self._apply_newtonian(desired_heading, dt, lateral_force=avoidance_force)

        # --- ARSENAL ---
        
        # 1. Sniper Raycast
        if self.state == 'charging':
            if self.sniper_timer <= 0:
                # Fire Raycast
                dx_p, dy_p, dz_p = px - self.x, py - self.y, pz - self.z
                dist_f = math.sqrt(dx_p*dx_p + dy_p*dy_p + dz_p*dz_p) or 1.0
                # closest approach
                cx = (dy_p/dist_f)*self.forward[2] - (dz_p/dist_f)*self.forward[1]
                cy = (dz_p/dist_f)*self.forward[0] - (dx_p/dist_f)*self.forward[2]
                cz = (dx_p/dist_f)*self.forward[1] - (dy_p/dist_f)*self.forward[0]
                perp_dist = math.sqrt(cx*cx + cy*cy + cz*cz) * dist_f
                dot = (dx_p/dist_f)*self.forward[0] + (dy_p/dist_f)*self.forward[1] + (dz_p/dist_f)*self.forward[2]
                
                if player is not None and dot > 0 and perp_dist < PLAYER_COLLISION_RADIUS:
                    player.take_damage(20)
                
                if global_projectiles is not None:
                    spawn_offset = self.hit_radius + 20.0
                    beam = SniperBeam(
                        self.x + self.forward[0] * spawn_offset,
                        self.y + self.forward[1] * spawn_offset,
                        self.z + self.forward[2] * spawn_offset,
                        self.forward[0] * 32000, self.forward[1] * 32000, self.forward[2] * 32000
                    )
                    beam.owner = self
                    global_projectiles.append(beam)
                
                self.state = 'idle'
                self.sniper_timer = random.uniform(8.0, 12.0)
        elif self.sniper_timer <= 0 and dist < 12000:
            self.state = 'charging'
            self.sniper_timer = 1.5 # Charge duration

        # 2. Homing Bolts
        if self.bolt_timer <= 0 and dist < 8000:
            self.bolt_timer = 4.0
            if global_projectiles is not None:
                spawn_offset = self.hit_radius + 20.0
                for _ in range(3):
                    spread = 0.3
                    bx, by, bz = nx + random.uniform(-spread, spread), ny + random.uniform(-spread, spread), nz + random.uniform(-spread, spread)
                    bolt = HomingBolt(
                        self.x + bx * spawn_offset,
                        self.y + by * spawn_offset,
                        self.z + bz * spawn_offset,
                        bx * 2000, by * 2000, bz * 2000
                    )
                    bolt.owner = self
                    global_projectiles.append(bolt)

        # 3. Point Defense MG
        if self.mg_timer <= 0 and dist < 4000:
            self.mg_timer = 0.1
            spawn_offset = self.hit_radius + 20.0
            if global_projectiles is not None:
                spread = 0.1
                mx, my, mz = nx + random.uniform(-spread, spread), ny + random.uniform(-spread, spread), nz + random.uniform(-spread, spread)
                bolt = MachineGunBolt(
                    self.x + mx * spawn_offset,
                    self.y + my * spawn_offset,
                    self.z + mz * spawn_offset,
                    mx * 8000, my * 8000, mz * 8000
                )
                bolt.owner = self
                global_projectiles.append(bolt)

        # --- SPAWNING ---
        if self.spawn_timer <= 0 and dist < 15000:
            self.spawn_timer = 6.0
            if global_enemies is not None:
                # 70% Drone, 30% Dogfighter
                if random.random() < 0.7:
                    new_e = SuicideDrone(self.x - self.up[0]*150, self.y - self.up[1]*150, self.z - self.up[2]*150)
                    new_e.vx, new_e.vy, new_e.vz = self.vx, self.vy - 500, self.vz
                    new_e.set_pattern(random.choice(['spiral', 'corkscrew', 'zigzag']))
                else:
                    new_e = Dogfighter(self.x + self.right[0]*150, self.y + self.right[1]*150, self.z + self.right[2]*150)
                    new_e.vx, new_e.vy, new_e.vz = self.vx + 200, self.vy, self.vz
                new_e.spawn_immunity_timer = 10.0  # 10 second grace period
                global_enemies.append(new_e)

        self._spawn_engine_trail()
        self._update_engine_trail(dt)
        if self._flicker > 0: self._flicker -= dt * 8

    def on_hit(self, damage=1):
        hull_damage = self._apply_damage(damage)
        if hull_damage > 0:
            self._flicker = 1
