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

        v1x = cam_verts[idx0, 0]
        v1y = cam_verts[idx0, 1]
        v1z = cam_verts[idx0, 2]
        v2x = cam_verts[idx1, 0]
        v2y = cam_verts[idx1, 1]
        v2z = cam_verts[idx1, 2]
        v3x = cam_verts[idx2, 0]
        v3y = cam_verts[idx2, 1]
        v3z = cam_verts[idx2, 2]

        # Edge vectors
        ux = v2x - v1x
        uy = v2y - v1y
        uz = v2z - v1z
        vx = v3x - v1x
        vy = v3y - v1y
        vz = v3z - v1z

        # Cross product for normal (Z component determines facing)
        fnz = ux * vy - uy * vx
        if fnz >= 0:  # Backfacing
            continue

        # Normal vector
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz

        # Normalize and compute shade
        length = math.sqrt(nx * nx + ny * ny + fnz * fnz)
        if length > 0.0001:
            normalized_z = fnz / length
        else:
            normalized_z = 0.0

        shade = 255.0 * max(0.2, -normalized_z)
        if shade < 0:
            shade = 0
        elif shade > 255:
            shade = 255

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
    # Initial capacity for per-frame staging arrays (in vertices).
    # Doubled automatically when a frame needs more space.
    _STAGING_INITIAL = 8000

    def __init__(self, camera):
        self.camera = camera

        # Layered primitives
        self._layers = {
            'background': [],  # Stars
            'opaque': [],  # Ships, Asteroids
            'alpha': [],  # Nebula, Particles, Lasers
            'overlay': []  # HUD
        }

        # Cache for nebula/soft sprite rendering
        self._puff_cache = self._create_puff_texture(128)

        # Color tinted cache to avoid re-tinting every frame
        self._tinted_puffs = {}  # (r, g, b, alpha) -> surface

        # Scale cache for nebulae to avoid expensive transform.scale every frame
        self._scaled_nebulae = {}  # (cache_key, size) -> surface

        # Mesh cache: mesh_id -> (v_data_np, face_indices_np, face_colors_np)
        # v_data_np is the pre-converted vertex array so submit_mesh never
        # rebuilds it from a Python dict on cache-hit frames.
        self._mesh_cache = {}       # {mesh_id: (v_data, f_idx, f_col)}
        self._mesh_lru   = {}       # {mesh_id: frame_counter} for LRU eviction
        self._mesh_frame = 0        # incremented each clear()

        # Per-frame mesh submissions to be processed in a single batched numba call
        self._mesh_submissions = []  # list of (face_indices, face_colors, cam_verts, projected, layer)

        # Pre-allocated staging arrays for _flush_mesh_submissions.
        # Grown lazily (amortised O(1)) — no allocation on normal frames.
        cap = self._STAGING_INITIAL
        self._stg_cam  = np.empty((cap, 3), dtype=np.float64)
        self._stg_proj = np.empty((cap, 3), dtype=np.float64)
        self._stg_fidx = np.empty((cap, 3), dtype=np.int32)
        self._stg_fcol = np.empty((cap, 3), dtype=np.int32)
        self._stg_cap  = cap

    def _create_puff_texture(self, size):
        """Create a soft, radial gradient puff texture for nebulae."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2
        for r in range(center, 0, -1):
            alpha = int(180 * (1.0 - (r / center) ** 1.5))
            pygame.draw.circle(surf, (255, 255, 255, alpha), (center, center), r)
        return surf

    def clear(self):
        for layer in self._layers.values():
            layer.clear()
        self._mesh_frame += 1
        # Periodically clear sprite/nebula caches
        if len(self._tinted_puffs) > 100:
            self._tinted_puffs.clear()
        if len(self._scaled_nebulae) > 200:
            self._scaled_nebulae.clear()
        # LRU eviction for mesh cache: keep 5000 entries max.
        # Evict the half that were used least recently.
        if len(self._mesh_cache) > 5000:
            sorted_ids = sorted(self._mesh_lru, key=self._mesh_lru.__getitem__)
            for mid in sorted_ids[:len(sorted_ids) // 2]:
                del self._mesh_cache[mid]
                del self._mesh_lru[mid]

    def submit_mesh(self, pos, right, up, forward, verts, faces, layer='opaque', radius=None, static=False):
        """
        Submit a whole mesh for optimized rendering.
        Uses Numba-optimized batch transformations with pre-cached numpy data.
        Vertex arrays are converted from Python dicts only on the first call
        for each unique mesh (mesh_id cache-hit path allocates nothing).
        """
        # Fast frustum culling
        if radius is not None:
            if not self.camera.sphere_in_frustum(pos[0], pos[1], pos[2], radius):
                return

        # Determine whether verts is a dict or already a numpy/list array
        is_dict = isinstance(verts, dict)

        # Build a stable mesh_id from the faces list identity + shape.
        if faces:
            first_f = faces[0]
            first_v = tuple(first_f.get('v', ())) if isinstance(first_f, dict) else ()
            first_c = tuple(first_f.get('color', ())) if isinstance(first_f, dict) else ()
            mesh_id = (id(faces), len(faces), first_v, first_c)
        else:
            mesh_id = (id(faces), 0, (), ())

        # ── Cache-miss: build v_data + face arrays once, store everything ──
        if mesh_id not in self._mesh_cache:
            if is_dict:
                v_ids  = list(verts.keys())
                v_data = np.array([verts[vid] for vid in v_ids], dtype=np.float64)
                vid_map = {vid: i for i, vid in enumerate(v_ids)}
            else:
                v_data  = np.asarray(verts, dtype=np.float64)
                vid_map = None

            f_idx = []
            f_col = []
            for f in faces:
                fv = f['v'] if isinstance(f, dict) else f
                if len(fv) == 3:
                    if vid_map is not None:
                        f_idx.append([vid_map[fv[0]], vid_map[fv[1]], vid_map[fv[2]]])
                    else:
                        f_idx.append([fv[0], fv[1], fv[2]])
                    f_col.append(f['color'] if isinstance(f, dict) else (200, 200, 200))

            self._mesh_cache[mesh_id] = (
                v_data.copy(),
                np.array(f_idx, dtype=np.int32),
                np.array(f_col, dtype=np.int32),
            )

        # ── Cache-hit: zero allocation ──
        self._mesh_lru[mesh_id] = self._mesh_frame
        v_data, face_indices, face_colors = self._mesh_cache[mesh_id]

        # Local → World (vectorised)
        basis       = np.array([right, up, forward], dtype=np.float64)
        pos_arr     = np.array(pos,                  dtype=np.float64)
        world_verts = v_data @ basis + pos_arr

        # World → Camera (Numba batch)
        cam_verts = self.camera.world_to_camera_batch(world_verts)

        # Project (Numba batch)
        projected = self.camera.project_batch(cam_verts)

        # Enqueue for batched numba processing later in render()
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

        length = math.sqrt(fnz ** 2 + (ux * vz2 - uz * vx2) ** 2 + (uy * vz2 - uz * vy2) ** 2)
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
        """Submit a soft, semi-transparent nebula puff with proximity fading."""
        cx, cy, cz = self.camera.world_to_camera(x, y, z)

        if cz < 10 or cz > 50000:
            return

        # 1. PROXIMITY FADING (OPTIMIZED)
        # Fade out smoothly as we get close so they don't fill the entire screen.
        # Starts fading at 3000 units away, completely invisible by 800 units.
        fade_start = 3000.0
        fade_end = 800.0
        if cz < fade_start:
            fade_ratio = max(0.0, (cz - fade_end) / (fade_start - fade_end))
            alpha = int(alpha * fade_ratio)

        # Skip rendering entirely if it's invisible
        if alpha <= 0:
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

    def submit_baked_mesh(self, pos, right, up, forward, baked_mesh, layer='opaque', scale=1.0):
        """
        Hyper-fast submission of pre-compiled numpy meshes.
        Zero allocation path. Bypasses the LRU dictionary cache entirely.
        """
        # Fast frustum culling using precomputed radius
        if not self.camera.sphere_in_frustum(pos[0], pos[1], pos[2], baked_mesh.radius * scale):
            return

        # Local → World (vectorised)
        basis = np.array([right, up, forward], dtype=np.float64)
        pos_arr = np.array(pos, dtype=np.float64)

        # Apply scaling and rotation simultaneously
        world_verts = (baked_mesh.v_data * scale) @ basis + pos_arr

        # World → Camera (Numba batch)
        cam_verts = self.camera.world_to_camera_batch(world_verts)

        # Project (Numba batch)
        projected = self.camera.project_batch(cam_verts)

        # Enqueue for batched Numba processing
        self._mesh_submissions.append(
            (baked_mesh.f_idx, baked_mesh.f_col, cam_verts, projected, layer)
        )

    def render(self, surface):
        """Sort and render all submitted primitives by layer."""
        self._flush_mesh_submissions()
        draw_poly = pygame.draw.polygon
        draw_circle = pygame.draw.circle
        draw_line = pygame.draw.line

        # 1. Background (Stars, etc.)
        self._layers['background'].sort(key=lambda p: p[0], reverse=True)
        for p in self._layers['background']:
            draw_circle(surface, p[4], p[2], p[3])

        # 2 & 3. 3D Scene (Merge Opaque and Alpha for correct Painter's Algorithm depth)
        scene_primitives = self._layers['opaque'] + self._layers['alpha']
        scene_primitives.sort(key=lambda p: p[0], reverse=True)

        for p in scene_primitives:
            t = p[1]
            if t == 'poly':
                draw_poly(surface, p[3], p[2])
            elif t == 'sprite':
                draw_circle(surface, p[4], p[2], p[3])
            elif t == 'nebula':
                s = p[3] * 2

                if s < 2:
                    continue
                s = min(s, 600)

                # Adaptive binning
                if s < 128:
                    step = 4
                elif s < 256:
                    step = 16
                elif s < 512:
                    step = 32
                else:
                    step = 128
                s = (s // step) * step

                color_key = p[4]  # RGB tuple
                alpha_val = p[5]  # int 0-255

                # ⚡ KEY CHANGE: Include alpha in the cache key
                cache_key = (color_key[0], color_key[1], color_key[2], s, alpha_val)

                if cache_key not in self._scaled_nebulae:
                    # Get or create tinted base puff
                    if color_key not in self._tinted_puffs:
                        tinted = self._puff_cache.copy()
                        tint_surf = pygame.Surface(self._puff_cache.get_size(), pygame.SRCALPHA)
                        tint_surf.fill((color_key[0], color_key[1], color_key[2], 255))
                        tinted.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                        self._tinted_puffs[color_key] = tinted

                    # Scale the tinted puff
                    try:
                        scaled = pygame.transform.scale(self._tinted_puffs[color_key], (s, s))
                    except pygame.error:
                        continue

                    # ⚡ Pre-multiply alpha into the surface (no set_alpha() needed!)
                    scaled.fill((255, 255, 255, alpha_val), special_flags=pygame.BLEND_RGBA_MULT)
                    self._scaled_nebulae[cache_key] = scaled

                puff = self._scaled_nebulae[cache_key]

                # Screen culling
                px = p[2][0] - s // 2
                py = p[2][1] - s // 2
                W, H = surface.get_size()
                if px > W or px + s < 0 or py > H or py + s < 0:
                    continue

                # ⚡ Direct blit — alpha is already baked in
                surface.blit(puff, (px, py))
            elif t == 'line':
                draw_line(surface, p[4], p[2], p[3], p[5])

        # (If you have an Overlay section for UI, it would go here at the very end)

    def _ensure_staging(self, n_verts, n_faces):
        """Grow pre-allocated staging buffers if the current frame needs more space.
        Doubles capacity to amortise the cost (O(1) average)."""
        if n_verts > self._stg_cap:
            new_cap = max(n_verts, self._stg_cap * 2)
            self._stg_cam  = np.empty((new_cap, 3), dtype=np.float64)
            self._stg_proj = np.empty((new_cap, 3), dtype=np.float64)
            self._stg_cap  = new_cap
        if n_faces > self._stg_fidx.shape[0]:
            new_cap = max(n_faces, self._stg_fidx.shape[0] * 2)
            self._stg_fidx = np.empty((new_cap, 3), dtype=np.int32)
            self._stg_fcol = np.empty((new_cap, 3), dtype=np.int32)

    def _flush_mesh_submissions(self):
        """Batch all mesh submissions into a single numba call.
        Uses pre-allocated staging arrays written with slice-assignment to avoid
        np.vstack allocations on every frame.
        """
        if not self._mesh_submissions:
            return

        # First pass: count total verts and faces
        total_verts = 0
        total_faces = 0
        for (f_idx, f_col, cam_verts, projected, layer) in self._mesh_submissions:
            total_verts += cam_verts.shape[0]
            total_faces += f_idx.shape[0]

        if total_faces == 0:
            self._mesh_submissions.clear()
            return

        # Grow staging buffers if needed (amortised, rarely triggers)
        self._ensure_staging(total_verts, total_faces)

        # Second pass: fill staging arrays in-place (no allocation)
        layer_list  = []
        vert_offset = 0
        face_offset = 0
        for (f_idx, f_col, cam_verts, projected, layer) in self._mesh_submissions:
            nv = cam_verts.shape[0]
            nf = f_idx.shape[0]

            self._stg_cam [vert_offset:vert_offset + nv] = cam_verts
            self._stg_proj[vert_offset:vert_offset + nv] = projected

            if nf > 0:
                self._stg_fidx[face_offset:face_offset + nf] = f_idx + vert_offset
                self._stg_fcol[face_offset:face_offset + nf] = f_col
                layer_list.extend([layer] * nf)

            vert_offset += nv
            face_offset += nf

        # Use views into the staging arrays — zero extra allocation
        big_cam      = self._stg_cam [:total_verts]
        big_proj     = self._stg_proj[:total_verts]
        big_face_idx = self._stg_fidx[:total_faces]
        big_face_col = self._stg_fcol[:total_faces]

        # Single Numba call for all faces
        valid_mask, shaded_colors, avg_zs = process_faces_batch_numba(
            big_cam, big_proj, big_face_idx, big_face_col
        )

        # Dispatch visible faces into layer buffers
        layer_lists = self._layers
        for i in range(total_faces):
            if not valid_mask[i]:
                continue
            idx0 = big_face_idx[i, 0]
            idx1 = big_face_idx[i, 1]
            idx2 = big_face_idx[i, 2]
            pts = [
                (big_proj[idx0, 0], big_proj[idx0, 1]),
                (big_proj[idx1, 0], big_proj[idx1, 1]),
                (big_proj[idx2, 0], big_proj[idx2, 1]),
            ]
            layer_lists[layer_list[i]].append((avg_zs[i], 'poly', pts, tuple(shaded_colors[i])))

        self._mesh_submissions.clear()