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
        # Periodically clear tinted cache if it grows too large
        if len(self._tinted_puffs) > 100:
            self._tinted_puffs.clear()
        
    def submit_polygon(self, world_verts, color):
        """Submit a single polygon (triangle/quad) defined by world-space vertices."""
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
        self._primitives.sort(key=lambda p: p['depth'], reverse=True)
        
        for p in self._primitives:
            t = p['type']
            if t == 'poly':
                pygame.draw.polygon(surface, p['color'], p['pts'])
            elif t == 'sprite':
                pygame.draw.circle(surface, p['color'], p['pos'], p['size'])
            elif t == 'nebula':
                s = p['size'] * 2
                if s < 2 or s > 1500:
                    continue
                
                # Get tinted version from cache
                cache_key = (*p['color'], p['alpha'])
                if cache_key not in self._tinted_puffs:
                    tinted = self._puff_cache.copy()
                    tint_surf = pygame.Surface(self._puff_cache.get_size(), pygame.SRCALPHA)
                    tint_surf.fill(cache_key)
                    tinted.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    self._tinted_puffs[cache_key] = tinted
                
                try:
                    puff = pygame.transform.scale(self._tinted_puffs[cache_key], (s, s))
                    surface.blit(puff, (p['pos'][0] - p['size'], p['pos'][1] - p['size']))
                except pygame.error:
                    pass
            elif t == 'line':
                pygame.draw.line(surface, p['color'], p['p1'], p['p2'], p['thickness'])
