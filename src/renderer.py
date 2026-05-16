import pygame
import math
import numpy as np
from numba import njit

@njit(fastmath=True, cache=True)
def process_faces_batch_numba(cam_verts, projected, face_indices, face_colors):
    """
    Fast face processing: backface culling, lighting, and sorting.
    Returns valid mask, shaded colors, and average Z for depth sorting.
    """
    N_faces = face_indices.shape[0]
    valid = np.zeros(N_faces, dtype=np.bool_)
    shaded_colors = np.zeros((N_faces, 3), dtype=np.int32)
    avg_zs = np.zeros(N_faces, dtype=np.float64)
    
    for i in range(N_faces):
        idx0 = face_indices[i, 0]
        idx1 = face_indices[i, 1]
        idx2 = face_indices[i, 2]
        
        # Early skip if any vertex is out of frustum
        if projected[idx0, 0] <= -900000.0 or projected[idx1, 0] <= -900000.0 or projected[idx2, 0] <= -900000.0:
            continue
            
        v1x = cam_verts[idx0, 0]; v1y = cam_verts[idx0, 1]; v1z = cam_verts[idx0, 2]
        v2x = cam_verts[idx1, 0]; v2y = cam_verts[idx1, 1]; v2z = cam_verts[idx1, 2]
        v3x = cam_verts[idx2, 0]; v3y = cam_verts[idx2, 1]; v3z = cam_verts[idx2, 2]
        
        # Edge vectors
        ux = v2x - v1x; uy = v2y - v1y; uz = v2z - v1z
        vx = v3x - v1x; vy = v3y - v1y; vz = v3z - v1z
        
        # Cross product for normal (Z component determines facing)
        fnz = ux * vy - uy * vx
        if fnz >= 0:  # Backfacing
            continue
            
        # Normal vector
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        
        # Normalize and compute shade
        length = math.sqrt(nx*nx + ny*ny + fnz*fnz)
        if length > 0.0001:
            normalized_z = fnz / length
        else:
            normalized_z = 0.0
            
        shade = 255.0 * max(0.2, -normalized_z)
        if shade < 0: shade = 0
        elif shade > 255: shade = 255
        
        shade_int = int(shade)
        
        # Apply shade to base color
        base_r = face_colors[i, 0]
        base_g = face_colors[i, 1]
        base_b = face_colors[i, 2]
        
        shaded_colors[i, 0] = int(base_r * (shade_int / 255.0))
        shaded_colors[i, 1] = int(base_g * (shade_int / 255.0))
        shaded_colors[i, 2] = int(base_b * (shade_int / 255.0))

        valid[i] = True
        avg_zs[i] = (v1z + v2z + v3z) / 3.0
        
    return valid, shaded_colors, avg_zs


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
        self._mesh_cache = {}
        # Per-frame mesh submissions to be processed in a single batched numba call
        self._mesh_submissions = []  # list of (face_indices, face_colors, cam_verts, projected, layer)
        # Cache for static mesh camera-space results: (mesh_id, pos, right, up, forward) -> (cam_verts, projected)
        self._static_mesh_cache = {}

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
        if len(self._mesh_cache) > 2000:
            self._mesh_cache.clear()
        if len(self._static_mesh_cache) > 1000:
            self._static_mesh_cache.clear()
        
    def submit_mesh(self, pos, right, up, forward, verts, faces, layer='opaque', radius=None, static=False):
        """
        Submit a whole mesh for optimized rendering.
        Uses Numba-optimized batch transformations with pre-cached numpy data.
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
        if static:
            # Cache world_verts for static meshes keyed by mesh_id and transform
            transform_key = (mesh_id, tuple(map(float, pos)), tuple(map(float, right)), tuple(map(float, up)), tuple(map(float, forward)))
            if transform_key in self._static_mesh_cache:
                world_verts = self._static_mesh_cache[transform_key]
            else:
                world_verts = v_data @ basis + np.array(pos, dtype=np.float64)
                # store a copy to avoid accidental mutation
                self._static_mesh_cache[transform_key] = world_verts.copy()
        else:
            world_verts = v_data @ basis + np.array(pos, dtype=np.float64)
        
        # World to Camera (Batch Numba)
        cam_verts = self.camera.world_to_camera_batch(world_verts)
        
        # Project (Batch Numba)
        projected = self.camera.project_batch(cam_verts)
        
        n_verts = len(v_ids) if v_ids is not None else len(v_data)
        mesh_id = (id(faces), n_verts)
        if mesh_id not in self._mesh_cache:
            if v_ids is not None:
                vid_map = {vid: i for i, vid in enumerate(v_ids)}
            else:
                vid_map = None
            f_idx = []
            f_col = []
            for f in faces:
                if len(f['v']) == 3:
                    if vid_map:
                        f_idx.append([vid_map[f['v'][0]], vid_map[f['v'][1]], vid_map[f['v'][2]]])
                    else:
                        f_idx.append([f['v'][0], f['v'][1], f['v'][2]])
                    f_col.append(f['color'])
            self._mesh_cache[mesh_id] = (np.array(f_idx, dtype=np.int32), np.array(f_col, dtype=np.int32))
            
        face_indices, face_colors = self._mesh_cache[mesh_id]
        # Enqueue submission for batched processing later in render
        # We store the cam_verts/projected so the heavy work (face culling/shading)
        # can be done once for all submitted meshes in a single numba call.
        self._mesh_submissions.append((face_indices, face_colors, cam_verts, projected, layer))

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
        # Process all mesh submissions in a single batched numba call before drawing
        self._flush_mesh_submissions()
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

    def _flush_mesh_submissions(self):
        """Batch all mesh submissions into a single numba call by concatenating
        camera-space vertex arrays and projected arrays, offsetting indices.
        This reduces numba call overhead and allows the shading to run once
        for all faces.
        """
        if not self._mesh_submissions:
            return

        # Concatenate cam_verts and projected arrays, track offsets
        cam_list = []
        proj_list = []
        face_idx_list = []
        face_col_list = []
        layer_list = []
        offsets = []

        vert_offset = 0
        for (f_idx, f_col, cam_verts, projected, layer) in self._mesh_submissions:
            n_verts = cam_verts.shape[0]
            cam_list.append(cam_verts)
            proj_list.append(projected)
            # offset indices
            if f_idx.size > 0:
                face_idx_list.append(f_idx + vert_offset)
                face_col_list.append(f_col)
                layer_list.extend([layer] * f_idx.shape[0])
            offsets.append((vert_offset, n_verts))
            vert_offset += n_verts

        # Build concatenated arrays
        big_cam = np.vstack(cam_list)
        big_proj = np.vstack(proj_list)
        if face_idx_list:
            big_face_idx = np.vstack(face_idx_list).astype(np.int32)
            big_face_col = np.vstack(face_col_list).astype(np.int32)
        else:
            big_face_idx = np.zeros((0,3), dtype=np.int32)
            big_face_col = np.zeros((0,3), dtype=np.int32)

        # Call numba once for all faces
        valid_mask, shaded_colors, avg_zs = process_faces_batch_numba(big_cam, big_proj, big_face_idx, big_face_col)

        # Split results back per-face and append into layer buffers
        layer_lists = self._layers
        for i in range(big_face_idx.shape[0]):
            if not valid_mask[i]:
                continue
            idx0 = big_face_idx[i, 0]
            idx1 = big_face_idx[i, 1]
            idx2 = big_face_idx[i, 2]
            pts = [
                (big_proj[idx0, 0], big_proj[idx0, 1]),
                (big_proj[idx1, 0], big_proj[idx1, 1]),
                (big_proj[idx2, 0], big_proj[idx2, 1])
            ]
            color = tuple(shaded_colors[i])
            layer = layer_list[i]
            layer_lists[layer].append((avg_zs[i], 'poly', pts, color))

        # Clear submissions
        self._mesh_submissions.clear()

