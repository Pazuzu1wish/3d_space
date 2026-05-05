import math
from src.math_engine import quat_rotate_vec, quat_conjugate

class Camera:
    def __init__(self, W, H, fov=400.0, near_clip=0.1):
        self.W = W
        self.H = H
        self.cx = W // 2
        self.cy = H // 2
        self.fov = fov
        self.near_clip = near_clip
        
        self.pos = (0.0, 0.0, 0.0)
        self.orientation = (1.0, 0.0, 0.0, 0.0) # w, x, y, z
        self._inv_quat = self.orientation
        
        self.shake_amount = 0.0
        self.shake_offset = (0.0, 0.0)
        
    def update(self, pos, orientation):
        self.pos = pos
        self.orientation = orientation
        self._inv_quat = quat_conjugate(self.orientation)
        
    def world_to_camera(self, x, y, z):
        px, py, pz = self.pos
        dx, dy, dz = x - px, y - py, z - pz
        return quat_rotate_vec(self._inv_quat, (dx, dy, dz))
        
    def project(self, cx, cy, cz):
        if cz <= self.near_clip:
            return None
        scale = self.fov / cz
        sx = int(cx * scale + self.cx + self.shake_offset[0])
        sy = int(cy * scale + self.cy + self.shake_offset[1])
        return sx, sy, scale

    def trigger_shake(self, intensity):
        from src.constants import SCREEN_SHAKE_MAX
        self.shake_amount = min(SCREEN_SHAKE_MAX, self.shake_amount + intensity)

    def update_shake(self, dt):
        import random
        from src.constants import SCREEN_SHAKE_DECAY
        self.shake_amount = max(0.0, self.shake_amount - SCREEN_SHAKE_DECAY * dt)
        if self.shake_amount > 0:
            dx = (random.random() * 2 - 1) * self.shake_amount
            dy = (random.random() * 2 - 1) * self.shake_amount
            self.shake_offset = (dx, dy)
        else:
            self.shake_offset = (0.0, 0.0)
        return self.shake_offset
        
    def sphere_in_frustum(self, x, y, z, radius):
        """
        Fast frustum culling using a bounding sphere.
        Returns True if the sphere is potentially visible.
        """
        cx, cy, cz = self.world_to_camera(x, y, z)
        
        # Behind near clip plane entirely?
        if cz + radius < self.near_clip:
            return False
            
        # If it's too close to the camera, just render it to avoid false culling artifacts
        if cz < self.near_clip + radius:
            return True
            
        # Check against screen boundaries using a simple projection estimate
        # Estimate screen space radius
        scale = self.fov / cz
        screen_radius = radius * scale
        
        sx = cx * scale + self.cx
        sy = cy * scale + self.cy
        
        # Check if sphere bounding box on screen intersects screen bounding box
        if sx + screen_radius < 0 or sx - screen_radius > self.W:
            return False
        if sy + screen_radius < 0 or sy - screen_radius > self.H:
            return False
            
        return True
