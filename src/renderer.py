import pygame
import math

class RenderPipeline:
    def __init__(self, camera):
        self.camera = camera
        
        # A flat list to store primitives for the current frame before sorting and rendering.
        # Elements will be dictionaries:
        # { 'depth': cz, 'type': 'poly', 'pts': [(sx, sy)...], 'color': (r,g,b) }
        # { 'depth': cz, 'type': 'sprite', 'pos': (sx, sy), 'size': size, 'color': (r,g,b) }
        # { 'depth': cz, 'type': 'line', 'p1': (sx, sy), 'p2': (ex, ey), 'color': (r,g,b), 'thickness': t }
        self._primitives = []
        
    def clear(self):
        self._primitives.clear()
        
    def submit_polygon(self, world_verts, color):
        """Submit a single polygon (triangle/quad) defined by world-space vertices."""
        if len(world_verts) < 3:
            return
            
        cam_verts = []
        for vx, vy, vz in world_verts:
            cx, cy, cz = self.camera.world_to_camera(vx, vy, vz)
            # Rough near clip check per vertex - if any vertex is behind camera, 
            # we should technically clip the polygon, but for simplicity we'll drop it
            # if all are behind, or let project() handle if some are visible.
            cam_verts.append((cx, cy, cz))
            
        # For simplicity in this engine, we do a basic backface culling on the first 3 verts
        v1, v2, v3 = cam_verts[0], cam_verts[1], cam_verts[2]
        
        ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        vx2, vy2, vz2 = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]

        # Normal Z in camera space
        fnz = ux * vy2 - uy * vx2
        
        if fnz >= 0: 
            return # Backface culled
            
        # Project vertices
        projected = []
        avg_z = 0.0
        for cx, cy, cz in cam_verts:
            proj = self.camera.project(cx, cy, cz)
            if not proj:
                return # If any vertex fails projection (behind near clip), drop face
            projected.append((proj[0], proj[1]))
            avg_z += cz
            
        avg_z /= len(cam_verts)
        
        # Calculate flat shading based on camera-space normal Z
        length = math.sqrt(fnz ** 2 + (ux*vz2 - uz*vx2)**2 + (uy*vz2 - uz*vy2)**2)
        normalized_z = fnz / length if length > 0.0001 else 0
        
        shade = max(0, min(255, int(255 * max(0.2, -normalized_z))))
        r = int(color[0] * (shade / 255))
        g = int(color[1] * (shade / 255))
        b = int(color[2] * (shade / 255))
        shaded_color = (r, g, b)
        
        self._primitives.append({
            'depth': avg_z,
            'type': 'poly',
            'pts': projected,
            'color': shaded_color
        })
        
    def submit_sprite(self, x, y, z, color, size, is_glow=False):
        """Submit a 2D circle sprite at a 3D world position."""
        cx, cy, cz = self.camera.world_to_camera(x, y, z)
        proj = self.camera.project(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            scaled_size = max(1, int(scale * size))
            self._primitives.append({
                'depth': cz,
                'type': 'sprite',
                'pos': (sx, sy),
                'size': scaled_size,
                'color': color,
                'is_glow': is_glow
            })

    def submit_line(self, p1, p2, color, thickness=1):
        """Submit a 3D line."""
        c1x, c1y, c1z = self.camera.world_to_camera(p1[0], p1[1], p1[2])
        c2x, c2y, c2z = self.camera.world_to_camera(p2[0], p2[1], p2[2])
        
        proj1 = self.camera.project(c1x, c1y, c1z)
        proj2 = self.camera.project(c2x, c2y, c2z)
        
        if proj1 and proj2:
            s1x, s1y, _ = proj1
            s2x, s2y, _ = proj2
            avg_z = (c1z + c2z) / 2.0
            
            self._primitives.append({
                'depth': avg_z,
                'type': 'line',
                'p1': (s1x, s1y),
                'p2': (s2x, s2y),
                'color': color,
                'thickness': thickness
            })

    def render(self, surface):
        """Sort and render all submitted primitives."""
        # Sort by depth descending (Painter's Algorithm: furthest to closest)
        self._primitives.sort(key=lambda p: p['depth'], reverse=True)
        
        for p in self._primitives:
            t = p['type']
            if t == 'poly':
                pygame.draw.polygon(surface, p['color'], p['pts'])
            elif t == 'sprite':
                if p.get('is_glow'):
                    # Could draw with a specific blend mode if Pygame supported it well, 
                    # but standard circle works.
                    pygame.draw.circle(surface, p['color'], p['pos'], p['size'])
                else:
                    pygame.draw.circle(surface, p['color'], p['pos'], p['size'])
            elif t == 'line':
                pygame.draw.line(surface, p['color'], p['p1'], p['p2'], p['thickness'])
