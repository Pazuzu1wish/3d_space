import pygame
import math

class RenderPipeline:
    def __init__(self, camera):
        self.camera = camera
        self._primitives = []
        
        # Cache for nebula/soft sprite rendering
        self._puff_cache = self._create_puff_texture(128)
        
        # Color tinted cache to avoid re-tinting every frame
        self._tinted_puffs = {} # (r, g, b, alpha) -> surface
        
        # Scale cache for nebulae to avoid expensive transform.scale every frame
        self._scaled_nebulae = {} # (cache_key, size) -> surface

    def _create_puff_texture(self, size):
        """Create a soft, radial gradient puff texture for nebulae."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2
        for r in range(center, 0, -1):
            alpha = int(180 * (1.0 - (r / center)**1.5))
            pygame.draw.circle(surf, (255, 255, 255, alpha), (center, center), r)
        return surf

    def clear(self):
        self._primitives.clear()
        # Periodically clear caches if they grow too large
        if len(self._tinted_puffs) > 100:
            self._tinted_puffs.clear()
        if len(self._scaled_nebulae) > 200:
            self._scaled_nebulae.clear()
        
    def submit_mesh(self, pos, right, up, forward, verts, faces):
        """
        Submit a whole mesh for optimized rendering.
        pos: (x, y, z)
        right, up, forward: basis vectors
        verts: dict or list of local (x, y, z)
        faces: list of {'v': [indices], 'color': (r,g,b)}
        """
        px, py, pz = pos
        rx, ry, rz = right
        ux, uy, uz = up
        fx, fy, fz = forward
        
        # 1. Transform all vertices once
        cam_verts = {}
        projected_verts = {}
        
        # Check if verts is a dict or list
        items = verts.items() if isinstance(verts, dict) else enumerate(verts)
        
        for v_id, (vx, vy, vz) in items:
            # Local to World
            wx = px + vx * rx + vy * ux + vz * fx
            wy = py + vx * ry + vy * uy + vz * fy
            wz = pz + vx * rz + vy * uz + vz * fz
            
            # World to Camera
            cx, cy, cz = self.camera.world_to_camera(wx, wy, wz)
            cam_verts[v_id] = (cx, cy, cz)
            
            # Project
            proj = self.camera.project(cx, cy, cz)
            if proj:
                projected_verts[v_id] = proj
        
        # 2. Process faces
        for f in faces:
            v_ids = f['v']
            # Basic frustum culling: if any vertex is not projected, skip face for simplicity
            # (In a real engine we'd clip, but here we just skip if it's behind the camera)
            if any(vid not in projected_verts for vid in v_ids):
                continue
                
            pts = [projected_verts[vid] for vid in v_ids]
            c_pts = [cam_verts[vid] for vid in v_ids]
            
            # Backface culling in camera space
            v1, v2, v3 = c_pts[0], c_pts[1], c_pts[2]
            ux_f, uy_f, uz_f = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
            vx_f, vy_f, vz_f = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
            fnz = ux_f * vy_f - uy_f * vx_f
            
            if fnz >= 0:
                continue
                
            # Shading
            length = math.sqrt(fnz ** 2 + (ux_f*vz_f - uz_f*vx_f)**2 + (uy_f*vz_f - uz_f*vy_f)**2)
            normalized_z = fnz / length if length > 0.0001 else 0
            shade = max(0, min(255, int(255 * max(0.2, -normalized_z))))
            
            color = f['color']
            r = int(color[0] * (shade / 255))
            g = int(color[1] * (shade / 255))
            b = int(color[2] * (shade / 255))
            
            avg_z = sum(cv[2] for cv in c_pts) / len(c_pts)
            
            self._primitives.append({
                'depth': avg_z,
                'type': 'poly',
                'pts': [(p[0], p[1]) for p in pts],
                'color': (r, g, b)
            })

    def submit_polygon(self, world_verts, color):
        """Submit a single polygon (legacy, kept for asteroids or custom objects)."""
        if len(world_verts) < 3:
            return
            
        cam_verts = []
        for vx, vy, vz in world_verts:
            cx, cy, cz = self.camera.world_to_camera(vx, vy, vz)
            cam_verts.append((cx, cy, cz))
            
        # Backface culling
        v1, v2, v3 = cam_verts[0], cam_verts[1], cam_verts[2]
        ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        vx2, vy2, vz2 = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
        fnz = ux * vy2 - uy * vx2
        
        if fnz >= 0: 
            return 
            
        projected = []
        avg_z = 0.0
        for cx, cy, cz in cam_verts:
            proj = self.camera.project(cx, cy, cz)
            if not proj:
                return 
            projected.append((proj[0], proj[1]))
            avg_z += cz
            
        avg_z /= len(cam_verts)
        
        length = math.sqrt(fnz ** 2 + (ux*vz2 - uz*vx2)**2 + (uy*vz2 - uz*vy2)**2)
        normalized_z = fnz / length if length > 0.0001 else 0
        shade = max(0, min(255, int(255 * max(0.2, -normalized_z))))
        r = int(color[0] * (shade / 255))
        g = int(color[1] * (shade / 255))
        b = int(color[2] * (shade / 255))
        
        self._primitives.append({
            'depth': avg_z,
            'type': 'poly',
            'pts': projected,
            'color': (r, g, b)
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

    def submit_nebula(self, x, y, z, color, size, alpha=40):
        """Submit a soft, semi-transparent nebula puff."""
        cx, cy, cz = self.camera.world_to_camera(x, y, z)
        # Cull nebulae that are behind or too far
        if cz < 10 or cz > 50000:
            return

        proj = self.camera.project(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            scaled_size = max(1, int(scale * size))
            self._primitives.append({
                'depth': cz,
                'type': 'nebula',
                'pos': (sx, sy),
                'size': scaled_size,
                'color': color,
                'alpha': alpha
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
            self._primitives.append({
                'depth': (c1z + c2z) / 2.0,
                'type': 'line',
                'p1': (s1x, s1y),
                'p2': (s2x, s2y),
                'color': color,
                'thickness': thickness
            })

    def render(self, surface):
        """Sort and render all submitted primitives."""
        # Use a stable sort to maintain relative order for objects at same depth
        self._primitives.sort(key=lambda p: p['depth'], reverse=True)
        
        # Pre-bind draw functions for speed
        draw_poly = pygame.draw.polygon
        draw_circle = pygame.draw.circle
        draw_line = pygame.draw.line
        
        for p in self._primitives:
            t = p['type']
            if t == 'poly':
                draw_poly(surface, p['color'], p['pts'])
            elif t == 'sprite':
                draw_circle(surface, p['color'], p['pos'], p['size'])
            elif t == 'nebula':
                s = p['size'] * 2
                if s < 2 or s > 2000:
                    continue
                
                # Snap size to nearest 4 pixels to increase cache hits
                s = (s // 4) * 4
                
                cache_key = (*p['color'], p['alpha'])
                if cache_key not in self._tinted_puffs:
                    tinted = self._puff_cache.copy()
                    tint_surf = pygame.Surface(self._puff_cache.get_size(), pygame.SRCALPHA)
                    tint_surf.fill(cache_key)
                    tinted.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    self._tinted_puffs[cache_key] = tinted
                
                scaled_key = (cache_key, s)
                if scaled_key not in self._scaled_nebulae:
                    try:
                        self._scaled_nebulae[scaled_key] = pygame.transform.scale(self._tinted_puffs[cache_key], (s, s))
                    except pygame.error:
                        continue
                
                puff = self._scaled_nebulae[scaled_key]
                surface.blit(puff, (p['pos'][0] - s//2, p['pos'][1] - s//2))
                
            elif t == 'line':
                draw_line(surface, p['color'], p['p1'], p['p2'], p['thickness'])

