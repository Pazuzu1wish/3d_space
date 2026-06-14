import pygame
import math
import numpy as np
import moderngl

# Numba transforms won't be needed for 3D meshes anymore, but let's keep them if needed elsewhere.
from numba import njit

VERTEX_SHADER_3D = """
#version 330
uniform mat4 view;
uniform mat4 proj;
uniform mat4 model;

in vec3 in_vert;
in vec3 in_color;

out vec3 v_view_pos;
out vec3 v_color;

void main() {
    vec4 view_pos = view * model * vec4(in_vert, 1.0);
    v_view_pos = view_pos.xyz;
    gl_Position = proj * view_pos;
    v_color = in_color;
}
"""

FRAGMENT_SHADER_3D = """
#version 330
in vec3 v_view_pos;
in vec3 v_color;
out vec4 f_color;

void main() {
    vec3 dx = dFdx(v_view_pos);
    vec3 dy = dFdy(v_view_pos);
    vec3 normal = normalize(cross(dx, dy));
    // light dir is towards camera, i.e., positive Z in view space?
    // Wait, cross(dx,dy) could be pointing away depending on winding.
    // If we assume consistent CCW winding:
    float shade = max(0.2, normal.z); // Or -normal.z, we'll try abs(normal.z) if winding is mixed.
    shade = max(0.2, abs(normal.z)); // Safe fallback for mixed winding

    f_color = vec4(v_color * shade, 1.0);
}
"""

VERTEX_SHADER_2D = """
#version 330
in vec2 in_vert;
in vec2 in_texcoord;
out vec2 v_texcoord;
void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
    v_texcoord = in_texcoord;
}
"""

FRAGMENT_SHADER_2D = """
#version 330
uniform sampler2D tex;
in vec2 v_texcoord;
out vec4 f_color;
void main() {
    f_color = texture(tex, v_texcoord);
}
"""

def create_vao_for_mesh(ctx, prog, v_data, f_idx, f_col):
    flat_verts = v_data[f_idx.flatten()].astype('f4')
    flat_colors = np.repeat(f_col, 3, axis=0).astype('f4') / 255.0
    
    vbo_vert = ctx.buffer(flat_verts.tobytes())
    vbo_col = ctx.buffer(flat_colors.tobytes())
    
    vao = ctx.vertex_array(prog, [
        (vbo_vert, '3f', 'in_vert'),
        (vbo_col, '3f', 'in_color')
    ])
    return vao, vbo_vert, vbo_col

class RenderPipeline:
    def __init__(self, camera):
        self.camera = camera
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.BLEND)
        
        self.prog_3d = self.ctx.program(
            vertex_shader=VERTEX_SHADER_3D,
            fragment_shader=FRAGMENT_SHADER_3D
        )
        self.prog_2d = self.ctx.program(
            vertex_shader=VERTEX_SHADER_2D,
            fragment_shader=FRAGMENT_SHADER_2D
        )
        
        # 2D Screen Quad
        quad_verts = np.array([
            -1.0,  1.0, 0.0, 1.0,
            -1.0, -1.0, 0.0, 0.0,
             1.0, -1.0, 1.0, 0.0,
            -1.0,  1.0, 0.0, 1.0,
             1.0, -1.0, 1.0, 0.0,
             1.0,  1.0, 1.0, 1.0,
        ], dtype='f4')
        self.quad_vbo = self.ctx.buffer(quad_verts.tobytes())
        self.quad_vao = self.ctx.vertex_array(self.prog_2d, [
            (self.quad_vbo, '2f 2f', 'in_vert', 'in_texcoord')
        ])
        
        # Offscreen surface for 2D stuff
        # Wait, how do we get surface size? From display?
        W, H = pygame.display.get_window_size()
        self.offscreen = pygame.Surface((W, H), pygame.SRCALPHA)
        
        self.screen_tex = self.ctx.texture((W, H), 4)
        self.screen_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        
        self._layers = {
            'background': [],  # Stars
            'opaque': [],      # Pygame polygons if any
            'alpha': [],       # Nebula, Particles, Lasers
            'overlay': []      # HUD
        }
        
        self._puff_cache = self._create_puff_texture(128)
        self._tinted_puffs = {}
        self._scaled_nebulae = {}
        
        # ModernGL VAO Cache
        # mesh_id -> (vao, vbo_vert, vbo_col)
        self._mgl_cache = {}
        
        # Batched submissions for ModernGL
        self._mgl_submissions = [] # list of (vao, model_matrix)

    def _create_puff_texture(self, size):
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        center = size // 2
        for r in range(center, 0, -1):
            alpha = int(180 * (1.0 - (r / center) ** 1.5))
            pygame.draw.circle(surf, (255, 255, 255, alpha), (center, center), r)
        return surf

    def clear(self):
        for layer in self._layers.values():
            layer.clear()
        self._mgl_submissions.clear()
        self.offscreen.fill((0, 0, 0, 0)) # Clear offscreen

        if len(self._tinted_puffs) > 100:
            self._tinted_puffs.clear()
        if len(self._scaled_nebulae) > 200:
            self._scaled_nebulae.clear()

    def get_view_matrix(self):
        # view matrix
        px, py, pz = self.camera.pos
        # Camera conjugates
        r00, r01, r02 = self.camera._r00, self.camera._r01, self.camera._r02
        r10, r11, r12 = self.camera._r10, self.camera._r11, self.camera._r12
        r20, r21, r22 = self.camera._r20, self.camera._r21, self.camera._r22
        
        # rotation matrix
        R = np.array([
            [r00, r01, r02, 0],
            [r10, r11, r12, 0],
            [r20, r21, r22, 0],
            [0,     0,   0, 1]
        ], dtype='f4')
        # translation matrix
        T = np.array([
            [1, 0, 0, -px],
            [0, 1, 0, -py],
            [0, 0, 1, -pz],
            [0, 0, 0, 1]
        ], dtype='f4')
        
        return R @ T

    def get_proj_matrix(self):
        # We need a standard perspective projection matrix
        # game does: sx = x * (fov / z) + cx, sy = -y * (fov / z) + cy
        # ModernGL / OpenGL wants clip space: x in [-1, 1], y in [-1, 1], z in [-1, 1] (or 0, 1)
        # fov in game is scaling factor (e.g. 400).
        # We can construct the projection matrix manually.
        n = self.camera.near_clip
        f = 100000.0 # far clip
        
        # game projection is basically:
        # x_clip = (x * fov / z) / W * 2 = x * (2*fov/W) / z
        # y_clip = (-y * fov / z) / H * 2 = y * (-2*fov/H) / z
        # so matrix is:
        P = np.zeros((4, 4), dtype='f4')
        P[0, 0] = 2.0 * self.camera.fov / self.camera.W
        P[1, 1] = -2.0 * self.camera.fov / self.camera.H # y is flipped in screen coords, but openGL is bottom-up, game is top-down. 
        # Wait, if y_clip = -1 at bottom, y_clip = 1 at top. game screen Y: 0 at top, H at bottom.
        # gl_Position.y / w = y_clip. 
        # let's be careful. game sy = -c.y * (fov/z) + cy.
        # if sy = 0 (top), clip = 1.
        # if sy = H (bottom), clip = -1.
        # So clip = 1.0 - 2.0*(sy/H).
        # clip = 1.0 - 2.0 * (-c.y * fov/z + cy)/H 
        # since cy = H/2, this is 1.0 - 2.0 * (-c.y * fov/z) / H - 2.0*(H/2)/H
        # = 1.0 + c.y * (2*fov/H) / z - 1.0 = c.y * (2*fov/H) / z.
        # So P[1,1] should actually be 2.0 * fov / H !
        P[1, 1] = 2.0 * self.camera.fov / self.camera.H
        
        P[2, 2] = -(f + n) / (f - n)
        P[2, 3] = -2.0 * f * n / (f - n)
        P[3, 2] = -1.0 # This makes w = -z, standard right handed? No, wait. 
        # In software renderer, cz is positive forward. So w needs to be +z!
        P[3, 2] = 1.0
        P[2, 2] = (f + n) / (f - n)
        P[2, 3] = -2.0 * f * n / (f - n)
        # Wait, if z is positive forward, we map n to -1 (or 0) and f to 1.
        # Let's map n to -1 and f to 1.
        # z_clip = z * P[2,2] + P[2,3]
        # w = z
        # z_ndc = z_clip / z = P[2,2] + P[2,3]/z
        # 1 = P[2,2] + P[2,3]/f
        # -1 = P[2,2] + P[2,3]/n
        # P[2,2] = (f+n)/(f-n), P[2,3] = -2fn/(f-n)
        
        return P

    def submit_baked_mesh(self, pos, right, up, forward, baked_mesh, layer='opaque', scale=1.0):
        if not self.camera.sphere_in_frustum(pos[0], pos[1], pos[2], baked_mesh.radius * scale):
            return

        mesh_id = id(baked_mesh)
        if mesh_id not in self._mgl_cache:
            vao, vbo_v, vbo_c = create_vao_for_mesh(
                self.ctx, self.prog_3d, baked_mesh.v_data, baked_mesh.f_idx, baked_mesh.f_col
            )
            self._mgl_cache[mesh_id] = (vao, vbo_v, vbo_c)
        else:
            vao, _, _ = self._mgl_cache[mesh_id]

        model = np.eye(4, dtype='f4')
        model[0:3, 0] = right * scale
        model[0:3, 1] = up * scale
        model[0:3, 2] = forward * scale
        model[0:3, 3] = pos
        
        self._mgl_submissions.append((vao, model))

    def submit_polygon(self, world_verts, color, layer='opaque'):
        # Fallback to software for random polygons
        if len(world_verts) < 3: return
        v_data = np.array(world_verts, dtype=np.float64)
        cam_verts = self.camera.world_to_camera_batch(v_data)
        # Software backface culling
        v1, v2, v3 = cam_verts[0], cam_verts[1], cam_verts[2]
        ux, uy, uz = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        vx2, vy2, vz2 = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
        fnz = ux * vy2 - uy * vx2
        if fnz >= 0: return
        projected = self.camera.project_batch(cam_verts)
        pts = []
        avg_z = 0.0
        for i in range(len(cam_verts)):
            if projected[i, 0] <= -900000.0: return
            pts.append((projected[i, 0], projected[i, 1]))
            avg_z += cam_verts[i, 2]
        avg_z /= len(cam_verts)
        length = math.sqrt(fnz**2 + (ux*vz2 - uz*vx2)**2 + (uy*vz2 - uz*vy2)**2)
        nz = fnz / length if length > 0.0001 else 0
        shade = max(0, min(255, int(255 * max(0.2, -nz))))
        c = (int(color[0]*shade/255), int(color[1]*shade/255), int(color[2]*shade/255))
        self._layers[layer].append((avg_z, 'poly', pts, c))

    def submit_mesh(self, pos, right, up, forward, verts, faces, layer='opaque', radius=None, static=False):
        # We shouldn't use this if we convert everything to baked_mesh, 
        # but if we do, we need to handle it.
        pass

    def submit_sprite(self, x, y, z, color, size, is_glow=False, layer='alpha', cam_pos=None):
        if cam_pos:
            cx, cy, cz = cam_pos
        else:
            cx, cy, cz = self.camera.world_to_camera(x, y, z)
        proj = self.camera.project(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            scaled_size = max(1, int(scale * size))
            self._layers[layer].append((cz, 'sprite', (sx, sy), scaled_size, color, is_glow))

    def submit_nebula(self, x, y, z, color, size, alpha=40, layer='alpha'):
        cx, cy, cz = self.camera.world_to_camera(x, y, z)
        if cz < 10 or cz > 50000: return
        fade_start, fade_end = 3000.0, 800.0
        if cz < fade_start:
            fade_ratio = max(0.0, (cz - fade_end) / (fade_start - fade_end))
            alpha = int(alpha * fade_ratio)
        if alpha <= 0: return
        proj = self.camera.project(cx, cy, cz)
        if proj:
            sx, sy, scale = proj
            scaled_size = max(1, int(scale * size))
            self._layers[layer].append((cz, 'nebula', (sx, sy), scaled_size, color, alpha))

    def submit_line(self, p1, p2, color, thickness=1, layer='alpha'):
        c1x, c1y, c1z = self.camera.world_to_camera(p1[0], p1[1], p1[2])
        c2x, c2y, c2z = self.camera.world_to_camera(p2[0], p2[1], p2[2])
        proj1 = self.camera.project(c1x, c1y, c1z)
        proj2 = self.camera.project(c2x, c2y, c2z)
        if proj1 and proj2:
            s1x, s1y, _ = proj1
            s2x, s2y, _ = proj2
            self._layers[layer].append(((c1z + c2z)/2.0, 'line', (s1x, s1y), (s2x, s2y), color, thickness))

    def render(self, surface):
        self.ctx.clear(0.0, 0.0, 0.0) # Clear OpenGL buffer
        
        # Draw 3D Meshes
        view = self.get_view_matrix()
        proj = self.get_proj_matrix()
        
        # ModernGL matrices are provided column-major if read from tuple, 
        # but numpy uses row-major. ModernGL uniform write handles numpy properly?
        # Actually, numpy arrays need to be transposed or written as bytes.
        self.prog_3d['view'].write(view.T.tobytes())
        self.prog_3d['proj'].write(proj.T.tobytes())
        
        self.ctx.enable(moderngl.DEPTH_TEST)
        for vao, model in self._mgl_submissions:
            self.prog_3d['model'].write(model.T.tobytes())
            vao.render()
            
        self.ctx.disable(moderngl.DEPTH_TEST)

        # Render 2D layers to offscreen surface
        draw_poly = pygame.draw.polygon
        draw_circle = pygame.draw.circle
        draw_line = pygame.draw.line
        
        self._layers['background'].sort(key=lambda p: p[0], reverse=True)
        for p in self._layers['background']:
            draw_circle(self.offscreen, p[4], p[2], p[3])
            
        scene_primitives = self._layers['opaque'] + self._layers['alpha']
        scene_primitives.sort(key=lambda p: p[0], reverse=True)
        
        for p in scene_primitives:
            t = p[1]
            if t == 'poly': draw_poly(self.offscreen, p[3], p[2])
            elif t == 'sprite': draw_circle(self.offscreen, p[4], p[2], p[3])
            elif t == 'line': draw_line(self.offscreen, p[4], p[2], p[3], p[5])
            elif t == 'nebula':
                s = p[3] * 2
                if s < 2: continue
                s = min(s, 600)
                step = 4 if s < 128 else (16 if s < 256 else (32 if s < 512 else 128))
                s = (s // step) * step
                c, a = p[4], p[5]
                cache_key = (c[0], c[1], c[2], s, a)
                if cache_key not in self._scaled_nebulae:
                    if c not in self._tinted_puffs:
                        tinted = self._puff_cache.copy()
                        tint_surf = pygame.Surface(self._puff_cache.get_size(), pygame.SRCALPHA)
                        tint_surf.fill((c[0], c[1], c[2], 255))
                        tinted.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                        self._tinted_puffs[c] = tinted
                    try:
                        scaled = pygame.transform.scale(self._tinted_puffs[c], (s, s))
                    except: continue
                    scaled.fill((255, 255, 255, a), special_flags=pygame.BLEND_RGBA_MULT)
                    self._scaled_nebulae[cache_key] = scaled
                puff = self._scaled_nebulae[cache_key]
                px, py = p[2][0] - s // 2, p[2][1] - s // 2
                self.offscreen.blit(puff, (px, py))
                
        # Draw overlay/HUD directly to offscreen
        # (HUD is drawn by game logic passing 'surface', which is screen. Wait, we must pass 'offscreen'!)
        # Actually, `game.py` calls state_manager.draw(self.screen).
        # Which passes `screen` to states. States call `render(surface)`.
        # Then states draw UI on `surface`.
        # To fix this, renderer should NOT draw offscreen to Quad here. It should happen AFTER all drawing!
        # Wait, if states draw UI on `surface`, `surface` is `self.screen` which is OPENGL. Pygame software drawing to an OPENGL surface is forbidden and will throw an error or do nothing.
        pass

    def present(self, surface):
        # surface is the offscreen UI surface
        # We need to render the 3D scene AND the offscreen surface
        
        # Actually, self.render(surface) has already drawn 2D stuff to offscreen surface.
        # Now we upload self.offscreen to ModernGL
        view = self.offscreen.get_view('2')
        # Pygame surface to Moderngl texture: W, H are the size of self.offscreen
        # Data format is usually RGBA
        self.screen_tex.write(view.raw)
        
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.BLEND)
        self.screen_tex.use(0)
        self.prog_2d['tex'].value = 0
        self.quad_vao.render(moderngl.TRIANGLES)
