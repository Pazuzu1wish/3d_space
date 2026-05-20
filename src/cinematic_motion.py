import math


class CinematicStep:
    """One beat in a scripted sequence."""
    def __init__(self, duration, motion_fn):
        self.duration = duration   # seconds, or None = run forever
        self.motion_fn = motion_fn
        self._elapsed = 0.0

    def step(self, enemy, dt):
        self.motion_fn(enemy, dt, self._elapsed)
        self._elapsed += dt

    def done(self):
        return self.duration is not None and self._elapsed >= self.duration


class CinematicScript:
    """Chains CinematicSteps in sequence. Last step runs until replaced."""
    def __init__(self, *steps):
        self._steps = list(steps)
        self._idx = 0

    def step(self, enemy, dt):
        if self._idx >= len(self._steps):
            return
        current = self._steps[self._idx]
        current.step(enemy, dt)
        if current.done():
            self._idx += 1

    # ── MOTION PRIMITIVES ────────────────────────────────────────

    @staticmethod
    def linear(vx, vy, vz):
        """Straight-line constant velocity. Updates orientation to match heading."""
        def _fn(enemy, dt, t):
            enemy.vx = vx
            enemy.vy = vy
            enemy.vz = vz
            enemy.x += vx * dt
            enemy.y += vy * dt
            enemy.z += vz * dt
            # keep forward aligned to velocity
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
        roll_speed: full rotations per second.
        direction: 1.0 = clockwise from nose, -1.0 = counter.
        """
        def _fn(enemy, dt, t):
            enemy.vx = vx
            enemy.vy = vy
            enemy.vz = vz
            enemy.x += vx * dt
            enemy.y += vy * dt
            enemy.z += vz * dt

            # Rotate up and right around forward axis
            angle = roll_speed * direction * math.tau * dt
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)

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
        """Corkscrew through space — actual helical path, not just visual roll.
        vx/vz: base travel velocity.
        amplitude: radius of the helix loop (world units).
        frequency: loops per second.
        """
        def _fn(enemy, dt, t):
            # helical vy component — derivative of amplitude*sin(2π*freq*t)
            vy_helix = amplitude * frequency * math.tau * math.cos(frequency * math.tau * t)
            enemy.vx = vx
            enemy.vy = vy_helix
            enemy.vz = vz
            enemy.x += vx * dt
            enemy.y += vy_helix * dt
            enemy.z += vz * dt

            # orient forward to actual velocity
            spd = math.sqrt(vx*vx + vy_helix*vy_helix + vz*vz)
            if spd > 1e-3:
                from src.math_engine import basis_from_forward
                enemy.forward, enemy.right, enemy.up = basis_from_forward(
                    (vx/spd, vy_helix/spd, vz/spd)
                )

            # add visual roll on top
            angle = roll_speed * math.tau * dt
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            ux, uy, uz = enemy.up
            rx, ry, rz = enemy.right
            enemy.up    = (ux*cos_a - rx*sin_a, uy*cos_a - ry*sin_a, uz*cos_a - rz*sin_a)
            enemy.right = (rx*cos_a + ux*sin_a, ry*cos_a + uy*sin_a, rz*cos_a + uz*sin_a)
        return _fn