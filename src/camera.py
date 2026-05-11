import math
import numpy as np
from src.math_engine import (
    quat_conjugate, 
    world_to_camera_batch, 
    project_to_screen_batch
)

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
        
        self.shake_amount = 0.0
        self.shake_offset = (0.0, 0.0)

        # Pre-computed inverse rotation matrix coefficients (set in update())
        # These turn world_to_camera into 9 muls + 9 adds, zero quat math.
        self._r00 = 1.0; self._r01 = 0.0; self._r02 = 0.0
        self._r10 = 0.0; self._r11 = 1.0; self._r12 = 0.0
        self._r20 = 0.0; self._r21 = 0.0; self._r22 = 1.0
        
        # Flattened coefficients for Numba
        self._r_coeffs = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0], dtype=np.float64)
        
    def update(self, pos, orientation):
        self.pos = pos
        self.orientation = orientation
        # Pre-compute the inverse (conjugate) rotation matrix coefficients once
        w = orientation[0]
        qx = -orientation[1]; qy = -orientation[2]; qz = -orientation[3]
        xx = qx*qx; yy = qy*qy; zz = qz*qz
        xy = qx*qy; xz = qx*qz; yz = qy*qz
        wx = w*qx;  wy = w*qy;  wz = w*qz
        
        self._r00 = 1.0 - 2.0*(yy+zz); self._r01 = 2.0*(xy-wz);       self._r02 = 2.0*(xz+wy)
        self._r10 = 2.0*(xy+wz);       self._r11 = 1.0 - 2.0*(xx+zz); self._r12 = 2.0*(yz-wx)
        self._r20 = 2.0*(xz-wy);       self._r21 = 2.0*(yz+wx);       self._r22 = 1.0 - 2.0*(xx+yy)
        
        # Update flattened coeffs for Numba
        self._r_coeffs[0] = self._r00; self._r_coeffs[1] = self._r01; self._r_coeffs[2] = self._r02
        self._r_coeffs[3] = self._r10; self._r_coeffs[4] = self._r11; self._r_coeffs[5] = self._r12
        self._r_coeffs[6] = self._r20; self._r_coeffs[7] = self._r21; self._r_coeffs[8] = self._r22
        
    def world_to_camera(self, x, y, z):
        """Transform world point to camera space using pre-computed rotation matrix."""
        px, py, pz = self.pos
        dx, dy, dz = x - px, y - py, z - pz
        return (
            dx*self._r00 + dy*self._r01 + dz*self._r02,
            dx*self._r10 + dy*self._r11 + dz*self._r12,
            dx*self._r20 + dy*self._r21 + dz*self._r22,
        )
        
    def world_to_camera_batch(self, verts_array):
        """Transform batch of world points to camera space using Numba."""
        px, py, pz = self.pos
        return world_to_camera_batch(verts_array, px, py, pz, self._r_coeffs)
        
    def project(self, cx, cy, cz):
        if cz <= self.near_clip:
            return None
        scale = self.fov / cz
        sx = int(cx * scale + self.cx + self.shake_offset[0])
        sy = int(cy * scale + self.cy + self.shake_offset[1])
        return sx, sy, scale
        
    def project_batch(self, cam_verts_array):
        """Project batch of camera-space points to screen space using Numba."""
        return project_to_screen_batch(
            cam_verts_array, 
            self.fov, 
            self.cx, 
            self.cy, 
            self.shake_offset[0], 
            self.shake_offset[1], 
            self.near_clip
        )

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
        Returns (visible, cx, cy, cz) — reuse the camera-space coords downstream.
        """
        px, py, pz = self.pos
        dx, dy, dz = x - px, y - py, z - pz
        cx = dx*self._r00 + dy*self._r01 + dz*self._r02
        cy = dx*self._r10 + dy*self._r11 + dz*self._r12
        cz = dx*self._r20 + dy*self._r21 + dz*self._r22
        
        # Behind near clip plane entirely?
        if cz + radius < self.near_clip:
            return False
            
        # If it's too close to the camera, just render it to avoid false culling artifacts
        if cz < self.near_clip + radius:
            return True
            
        # Check against screen boundaries using a simple projection estimate
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
