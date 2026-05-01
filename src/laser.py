from src.math_engine import *
import pygame

class Laser:
    def __init__(self, ppos=None, prot=None, x=0, y=0, z=0, vx=0, vy=0, vz=0, life=1.5):
        """
        Initialize a laser. Can be initialized with player orientation or with explicit values.
        
        Args:
            ppos: Player position tuple (x, y, z) - optional if using explicit values
            prot: Player orientation quaternion - optional if using explicit values
            x, y, z: Starting position - used if ppos/prot not provided
            vx, vy, vz: Velocity vector - used if ppos/prot not provided
            life: Laser lifetime in seconds
        """
        if ppos is not None and prot is not None:
            fx, fy, fz = get_forward_from_quat(prot)
            # Start laser slightly ahead of the ship so it doesn't clip the camera
            self.x = ppos[0] + fx * 50
            self.y = ppos[1] + fy * 50
            self.z = ppos[2] + fz * 50
            
            speed = 20000
            self.vx, self.vy, self.vz = fx * speed, fy * speed, fz * speed
            self.life = life
        else:
            self.x, self.y, self.z = float(x), float(y), float(z)
            self.vx, self.vy, self.vz = float(vx), float(vy), float(vz)
            self.life = float(life)
        
        # Track previous position to draw as a line (blaster bolt)
        self.px, self.py, self.pz = self.x, self.y, self.z
    
    def init(self, x, y, z, vx, vy, vz, life=1.5):
        """Reinitialize laser with new values (for object pooling)."""
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.vx, self.vy, self.vz = float(vx), float(vy), float(vz)
        self.life = float(life)
        self.px, self.py, self.pz = self.x, self.y, self.z
    
    def reset(self):
        """Reset laser to default state (for object pooling)."""
        self.x = self.y = self.z = 0
        self.vx = self.vy = self.vz = 0
        self.life = 0
        self.px = self.py = self.pz = 0

    def update(self, dt):
        self.px, self.py, self.pz = self.x, self.y, self.z
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.life -= dt

    def draw(self, surf, ppos, prot):
        # Project both the head and the tail of the laser
        cx1, cy1, cz1 = world_to_camera(self.px, self.py, self.pz, *ppos, prot)
        cx2, cy2, cz2 = world_to_camera(self.x, self.y, self.z, *ppos, prot)

        proj1 = project_to_screen(cx1, cy1, cz1)
        proj2 = project_to_screen(cx2, cy2, cz2)

        if proj1 and proj2:
            pygame.draw.line(surf, (100, 255, 100), (proj1[0], proj1[1]), (proj2[0], proj2[1]), 4)
