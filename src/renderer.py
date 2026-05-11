import pygame
import math
import numpy as np

class RenderPipeline:
    def __init__(self, camera):
        self.camera = camera
        
        # Layered primitives
        self._layers = {
            'background': [],  # Stars
            'opaque': [],      # Ships, Asteroids
            'alpha': [],       # Nebula, Particles, Lasers
            'overlay': []      # HUD
        }
        
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
        for layer in self._layers.values():
            layer.clear()
        # Periodically clear caches if they grow too large
        if len(self._tinted_puffs) > 100:
            self._tinted_puffs.clear()
        if len(self._scaled_nebulae) > 200:
            self._scaled_nebulae.clear()
        
    def submit_mesh(self, pos, right, up, forward, verts, faces, layer='opaque', radius=None):
        """
        Submit a whole mesh for optimized rendering.
        Uses Numba-optimized batch transformations.
        """
        # Fast frustum culling
        if radius is not None:
            if not self.camera.sphere_in_frustum(pos[0], pos[1], pos[2], radius):
                return

        # 1. Transform all vertices once using NumPy and Numba
        if isinstance(verts, dict):
            v_ids = list(verts.keys())
            v_data = np.array([verts[vid] for vid in v_ids], dtype=np.float64)
        else:
            v_data = np.asanyarray(verts, dtype=np.float64)
            v_ids = None # Use indices directly

        # Local to World (Vectorized)
        basis = np.array([right, up, forward], dtype=np.float64)
        world_verts = v_data @ basis + np.array(pos, dtype=np.float64)
        
        # World to Camera (Batch Numba)
        cam_verts = self.camera.world_to_camera_batch(world_verts)
        
        # Project (Batch Numba)
        projected = self.camera.project_batch(cam_verts)
        
        # Mapping for face processing
        if v_ids is not None:
            cam_verts_map = {vid: cam_verts[i] for i, vid in enumerate(v_ids)}
            projected_map = {}
            for i, vid in enumerate(v_ids):
                if projected[i, 0] > -900000.0:
                    projected_map[vid] = projected[i]
        else:
            # If verts was a list/array, v_ids are just indices
            cam_verts_map = cam_verts
            projected_map = projected
        
        # 2. Process faces
        for f in faces:
            v_indices = f['v']
            
            # Check projection and cull
            skip = False
            pts = []
            c_pts = []
            for vid in v_indices:
                if v_ids is not None:
                    if vid not in projected_map:
                        skip = True; break
                    pts.append(projected_map[vid])
                    c_pts.append(cam_verts_map[vid])
                else:
                    if projected_map[vid, 0] <= -900000.0:
                        skip = True; break
                    pts.append(projected_map[vid])
                    c_pts.append(cam_verts_map[vid])
            
            if skip: continue
                
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
            
            self._layers[layer].append((
                avg_z, 'poly', [(p[0], p[1]) for p in pts], (r, g, b)
            ))

    def submit_polygon(self, world_verts, color, layer='opaque'):
        """Submit a single polygon."""
        if len(world_verts) < 3:
            return
            
        v_data = np.array(world_verts, dtype=np.float64)
        cam_verts = self.camera.world_to_camera_batch(v_data)
            
        # Backface culling
        v1, v2, v3 = cam_verts[0], cam_verts[1], cam_verts[2]
        ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        vx2, vy2, vz2 = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
        fnz = ux * vy2 - uy * vx2
        
        if fnz >= 0: 
            return 
            
        projected = self.camera.project_batch(cam_verts)
        
        pts = []
        avg_z = 0.0
        for i in range(len(cam_verts)):
            if projected[i, 0] <= -900000.0:
                return 
            pts.append((projected[i, 0], projected[i, 1]))
            avg_z += cam_verts[i, 2]
            
        avg_z /= len(cam_verts)
        
        length = math.sqrt(fnz ** 2 + (ux*vz2 - uz*vx2)**2 + (uy*vz2 - uz*vy2)**2)
        normalized_z = fnz / length if length > 0.0001 else 0
        shade = max(0, min(255, int(255 * max(0.2, -normalized_z))))
        r = int(color[0] * (shade / 255))
        g = int(color[1] * (shade / 255))
        b = int(color[2] * (shade / 255))
        
        self._layers[layer].append((
            avg_z, 'poly', pts, (r, g, b)
        ))
        
    def submit_sprite(self, x, y, z, color, size, is_glow=False, layer='alpha', cam_pos=None):
        """Submit a 2D circle sprite."""
        if cam_pos:
            cx, cy, cz = cam_pos
        else:
            cx, cy, cz = self.camera.world_to_camera(x, y, z)
            
        proj = self.camera.project(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            scaled_size = max(1, int(scale * size))
            self._layers[layer].append((
                cz, 'sprite', (sx, sy), scaled_size, color, is_glow
            ))

    def submit_nebula(self, x, y, z, color, size, alpha=40, layer='alpha'):
        """Submit a soft, semi-transparent nebula puff."""
        cx, cy, cz = self.camera.world_to_camera(x, y, z)
        if cz < 10 or cz > 50000:
            return

        proj = self.camera.project(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            scaled_size = max(1, int(scale * size))
            self._layers[layer].append((
                cz, 'nebula', (sx, sy), scaled_size, color, alpha
            ))

    def submit_line(self, p1, p2, color, thickness=1, layer='alpha'):
        """Submit a 3D line."""
        c1x, c1y, c1z = self.camera.world_to_camera(p1[0], p1[1], p1[2])
        c2x, c2y, c2z = self.camera.world_to_camera(p2[0], p2[1], p2[2])
        proj1 = self.camera.project(c1x, c1y, c1z)
        proj2 = self.camera.project(c2x, c2y, c2z)
        
        if proj1 and proj2:
            s1x, s1y, _ = proj1
            s2x, s2y, _ = proj2
            self._layers[layer].append((
                (c1z + c2z) / 2.0, 'line', (s1x, s1y), (s2x, s2y), color, thickness
            ))

    def render(self, surface):
        """Sort and render all submitted primitives by layer."""
        draw_poly = pygame.draw.polygon
        draw_circle = pygame.draw.circle
        draw_line = pygame.draw.line
        
        # 1. Background
        self._layers['background'].sort(key=lambda p: p[0], reverse=True)
        for p in self._layers['background']:
            draw_circle(surface, p[4], p[2], p[3])
            
        # 2. Opaque
        self._layers['opaque'].sort(key=lambda p: p[0], reverse=True)
        for p in self._layers['opaque']:
            draw_poly(surface, p[3], p[2])
            
        # 3. Alpha
        self._layers['alpha'].sort(key=lambda p: p[0], reverse=True)
        for p in self._layers['alpha']:
            t = p[1]
            if t == 'sprite':
                draw_circle(surface, p[4], p[2], p[3])
            elif t == 'nebula':
                s = p[3] * 2
                if s < 2 or s > 2000: continue
                s = (s // 4) * 4
                cache_key = (*p[4], p[5])
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
                    except pygame.error: continue
                
                puff = self._scaled_nebulae[scaled_key]
                surface.blit(puff, (p[2][0] - s//2, p[2][1] - s//2))
            elif t == 'line':
                draw_line(surface, p[4], p[2], p[3], p[5])
