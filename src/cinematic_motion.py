import math


# ──────────────────────────────────────────────────────────────────
#  CINEMATIC STEP + SCRIPT
# ──────────────────────────────────────────────────────────────────

class CinematicStep:
    """One beat in a scripted sequence."""
    def __init__(self, duration, motion_fn):
        self.duration = duration    # seconds, or None = run forever
        self.motion_fn = motion_fn
        self._elapsed = 0.0

    def step(self, enemy, dt):
        self.motion_fn(enemy, dt, self._elapsed)
        self._elapsed += dt

    def done(self):
        return self.duration is not None and self._elapsed >= self.duration


class CinematicScript:
    """Chains CinematicSteps in sequence.  Last step runs until replaced."""

    def __init__(self, *steps):
        self._steps = list(steps)
        self._idx   = 0

    def step(self, enemy, dt):
        if self._idx >= len(self._steps):
            return
        current = self._steps[self._idx]
        current.step(enemy, dt)
        if current.done():
            self._idx += 1

    # ── MOTION PRIMITIVES ─────────────────────────────────────────

    @staticmethod
    def linear(vx, vy, vz):
        """Straight-line constant velocity.  Keeps forward aligned to heading."""
        def _fn(enemy, dt, t):
            enemy.vx = vx
            enemy.vy = vy
            enemy.vz = vz
            enemy.x += vx * dt
            enemy.y += vy * dt
            enemy.z += vz * dt
            spd = math.sqrt(vx*vx + vy*vy + vz*vz)
            if spd > 1e-3:
                from src.math_engine import basis_from_forward
                enemy.forward, enemy.right, enemy.up = basis_from_forward(
                    (vx/spd, vy/spd, vz/spd)
                )
        return _fn

    @staticmethod
    def barrel_roll(vx, vy, vz, roll_speed=1.0, direction=1.0):
        """Fly straight while rolling around the forward axis.
        roll_speed : full rotations per second.
        direction  : 1.0 = clockwise from nose, -1.0 = counter.
        """
        def _fn(enemy, dt, t):
            enemy.vx = vx
            enemy.vy = vy
            enemy.vz = vz
            enemy.x += vx * dt
            enemy.y += vy * dt
            enemy.z += vz * dt

            angle  = roll_speed * direction * math.tau * dt
            cos_a  = math.cos(angle)
            sin_a  = math.sin(angle)
            ux, uy, uz = enemy.up
            rx, ry, rz = enemy.right
            enemy.up    = (ux*cos_a - rx*sin_a,
                           uy*cos_a - ry*sin_a,
                           uz*cos_a - rz*sin_a)
            enemy.right = (rx*cos_a + ux*sin_a,
                           ry*cos_a + uy*sin_a,
                           rz*cos_a + uz*sin_a)
        return _fn

    @staticmethod
    def helix(vx, vz, amplitude, frequency, roll_speed=0.5):
        """Corkscrew through space — actual helical path, nose tracks the curve."""
        def _fn(enemy, dt, t):
            vy_helix = amplitude * frequency * math.tau * math.cos(frequency * math.tau * t)
            enemy.vx = vx
            enemy.vy = vy_helix
            enemy.vz = vz
            enemy.x += vx * dt
            enemy.y += vy_helix * dt
            enemy.z += vz * dt

            spd = math.sqrt(vx*vx + vy_helix*vy_helix + vz*vz)
            if spd > 1e-3:
                from src.math_engine import basis_from_forward
                enemy.forward, enemy.right, enemy.up = basis_from_forward(
                    (vx/spd, vy_helix/spd, vz/spd)
                )

            angle  = roll_speed * math.tau * dt
            cos_a  = math.cos(angle)
            sin_a  = math.sin(angle)
            ux, uy, uz = enemy.up
            rx, ry, rz = enemy.right
            enemy.up    = (ux*cos_a - rx*sin_a, uy*cos_a - ry*sin_a, uz*cos_a - rz*sin_a)
            enemy.right = (rx*cos_a + ux*sin_a, ry*cos_a + uy*sin_a, rz*cos_a + uz*sin_a)
        return _fn

    @staticmethod
    def ring_formation(center_x, center_y, vz, radius, phase,
                       rotation_speed, shared, is_ticker=False):
        """One drone's role inside a rotating ring formation.

        All drones in the ring close over the same `shared` dict:
            shared = {'angle': 0.0}

        Only the ticker drone (is_ticker=True) advances shared['angle']
        each frame.  Every other drone reads it, so the ring rotates as
        one rigid body regardless of update order.

        Parameters
        ----------
        center_x, center_y : world-space axis the ring orbits
        vz                 : forward velocity (negative = toward camera)
        radius             : ring radius in world units
        phase              : this drone's fixed angular offset on the ring
                             (i * tau / DRONE_COUNT)
        rotation_speed     : ring rotations per second
        shared             : {'angle': 0.0} dict shared by all ring members
        is_ticker          : True for exactly one drone — the one that
                             advances shared['angle']
        """
        def _fn(enemy, dt, t):
            # ── 1. Advance shared ring angle (ticker only) ────────
            if is_ticker:
                shared['angle'] += rotation_speed * math.tau * dt

            ring_angle = shared['angle']

            # ── 2. Position on ring ───────────────────────────────
            a = ring_angle + phase
            enemy.x = center_x + radius * math.cos(a)
            enemy.y = center_y + radius * math.sin(a)
            enemy.z += vz * dt

            # ── 3. Velocity — used by engine trail spawn ──────────
            # tangential XY component + forward Z
            tang_speed = rotation_speed * math.tau * radius
            enemy.vx = -tang_speed * math.sin(a)
            enemy.vy =  tang_speed * math.cos(a)
            enemy.vz = vz

            # ── 4. Orientation: nose points down the Z axis ───────
            # forward = toward camera, right = tangential, up = outward
            from src.math_engine import basis_from_forward
            # pure forward along -Z (toward camera)
            enemy.forward = (0.0, 0.0, -1.0)
            # right = tangential direction on the ring
            tx = -math.sin(a)
            ty =  math.cos(a)
            tlen = math.sqrt(tx*tx + ty*ty) or 1.0
            enemy.right = (tx/tlen, ty/tlen, 0.0)
            # up = outward radial
            ox = math.cos(a)
            oy = math.sin(a)
            enemy.up = (ox, oy, 0.0)

        return _fn


# ──────────────────────────────────────────────────────────────────
#  CONVENIENCE: build a full drone swarm in ring formation
# ──────────────────────────────────────────────────────────────────

def make_ring_swarm(drone_class, count, center_x, center_y, spawn_z,
                    vz, radius=500, rotation_speed=1.5,
                    spawn_stagger=0.06):
    """Instantiate `count` drones arranged in a rotating ring.

    Returns a list of (drone, spawn_delay) tuples.  The caller is
    responsible for adding each drone to the active list after its
    delay has elapsed.

    Parameters
    ----------
    drone_class     : SuicideDrone (or any Enemy subclass)
    count           : number of drones in the ring
    center_x/y      : world-space center axis
    spawn_z         : Z coordinate where drones start
    vz              : forward velocity (negative = toward camera)
    radius          : ring radius in world units (default 500 → 1000 wide)
    rotation_speed  : ring rotations per second
    spawn_stagger   : seconds between each drone's activation
    """
    shared = {'angle': 0.0}
    result = []

    for i in range(count):
        phase = i * math.tau / count

        # Place drone on its ring position at spawn_z
        a = phase   # ring_angle starts at 0
        x = center_x + radius * math.cos(a)
        y = center_y + radius * math.sin(a)

        drone = drone_class(x, y, spawn_z)
        drone.did_detonate = False

        drone.cinematic_script = CinematicScript(
            CinematicStep(None, CinematicScript.ring_formation(
                center_x=center_x,
                center_y=center_y,
                vz=vz,
                radius=radius,
                phase=phase,
                rotation_speed=rotation_speed,
                shared=shared,
                is_ticker=(i == 0),   # drone 0 owns the clock
            ))
        )

        delay = i * spawn_stagger
        result.append((drone, delay))

    return result