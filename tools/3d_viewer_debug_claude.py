"""
3d_viewer_debug.py
------------------
3D entity viewer with mesh debugging overlays.

Controls
--------
    Left-drag          Rotate (mouse)
    Scroll             Zoom
    L-Stick            Rotate (DS4)
    R-Stick Y          Zoom (DS4)
    C                  Toggle backface culling
    W                  Toggle wireframe
    N                  Toggle normal arrows
    F                  Toggle face winding colours
    I                  Toggle face index labels
    D                  Cycle debug modes (off / winding / normals / all)
    R                  Reset transform
    Q / Escape         Quit

Face selection & editing
------------------------
    Left / Right       Cycle selected face (± 1)
    Up / Down          Jump ± 10 faces
    Space / Enter      Flip selected face winding in place
    X                  Auto-flip ALL red (inward) faces
    P                  Print current faces[] list to stdout (copy-paste ready)

Debug colour key (winding mode)
--------------------------------
    GREEN   face normal points broadly outward (away from mesh centroid)
    RED     face normal points inward  (winding is wrong — fix_winding candidate)
    BLUE    face is perpendicular to centroid vector (edge case)
"""
import sys
import os

# Add parent directory to path so src module can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import math
import pygame
from src.cockpit import custom_font
import src.enemy as enemy


# ── try to import project modules; fall back to stubs ────────────────────────
try:
    from src.math_engine import (
        quat_identity, quat_rotate_vec, quat_conjugate,
        rotate_yaw, rotate_pitch,
        project_to_screen,
    )
    from src.enemy import Corvette
    _HAS_PROJECT = True
except ImportError:
    _HAS_PROJECT = False

# ── colours ───────────────────────────────────────────────────────────────────
BG          = (10, 10,  10)
GRID_MAJOR  = (25,  30,  45)
GRID_MINOR  = (15,  18,  28)
AXIS_X      = (180, 40,  40)
AXIS_Y      = (40, 180,  40)
AXIS_Z      = (40,  80, 200)
HUD_COL     = (140, 200, 255)
HUD_DIM     = (60,  90, 130)
ACCENT      = (80, 160, 255)
WARN        = (255, 180,  40)

COL_OUTWARD   = (40, 220,  80)   # correct winding
COL_INWARD    = (220, 40,  40)   # reversed winding
COL_EDGE      = (100, 100, 220)  # ambiguous
COL_WIREFRAME = (60, 140, 220)
COL_NORMAL    = (255, 220,  40)
COL_CENTROID  = (200,  80, 200)
COL_SELECTED  = (255, 255, 255)  # selected face highlight
COL_SEL_DIM   = (180, 180, 180)  # selected face outline pulse


# ── math helpers (self-contained so the file runs without project imports) ────

def _quat_identity():
    return (1.0, 0.0, 0.0, 0.0)

def _quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw*bw - ax*bx - ay*by - az*bz,
        aw*bx + ax*bw + ay*bz - az*by,
        aw*by - ax*bz + ay*bw + az*bx,
        aw*bz + ax*by - ay*bx + az*bw,
    )

def _quat_norm(q):
    w, x, y, z = q
    m = math.sqrt(w*w + x*x + y*y + z*z) or 1.0
    return (w/m, x/m, y/m, z/m)

def _quat_conj(q):
    w, x, y, z = q
    return (w, -x, -y, -z)

def _quat_from_axis_angle(ax, ay, az, a):
    h = a * 0.5
    s = math.sin(h)
    return (math.cos(h), ax*s, ay*s, az*s)

def _quat_rot_vec(q, v):
    vx, vy, vz = v
    p = (0.0, vx, vy, vz)
    r = _quat_mul(_quat_mul(q, p), _quat_conj(q))
    return r[1], r[2], r[3]

def _rotate_yaw(q, d):
    lu = _quat_rot_vec(q, (0.0, 1.0, 0.0))
    dq = _quat_from_axis_angle(*lu, d)
    return _quat_norm(_quat_mul(dq, q))

def _rotate_pitch(q, d):
    lr = _quat_rot_vec(q, (1.0, 0.0, 0.0))
    dq = _quat_from_axis_angle(*lr, d)
    return _quat_norm(_quat_mul(dq, q))

def _project(x, y, z, fov=600, cx=640, cy=380):
    if z <= 0.1:
        return None
    s = fov / z
    return int(x*s + cx), int(y*s + cy), s

def _norm3(v):
    x, y, z = v
    m = math.sqrt(x*x + y*y + z*z) or 1.0
    return x/m, y/m, z/m

def _cross(a, b):
    ax, ay, az = a
    bx, by, bz = b
    return (ay*bz - az*by, az*bx - ax*bz, ax*by - ay*bx)

def _dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def _sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def _add(a, b):
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])

def _scale(v, s):
    return (v[0]*s, v[1]*s, v[2]*s)


# ── mesh centroid ─────────────────────────────────────────────────────────────

def mesh_centroid(verts):
    if not verts:
        return (0.0, 0.0, 0.0)
    vals = list(verts.values())
    if not vals: return (0, 0, 0)
    cx = sum(v[0] for v in vals) / len(vals)
    cy = sum(v[1] for v in vals) / len(vals)
    cz = sum(v[2] for v in vals) / len(vals)
    return (cx, cy, cz)


# ── face geometry helpers ─────────────────────────────────────────────────────

def face_normal_and_center(verts, face):
    """Return (normal, center) for a triangular face."""
    v0, v1, v2 = [verts[i] for i in face['v']]
    e1 = _sub(v1, v0)
    e2 = _sub(v2, v0)
    n  = _cross(e1, e2)
    nm = math.sqrt(n[0]**2 + n[1]**2 + n[2]**2) or 1.0
    n  = (n[0]/nm, n[1]/nm, n[2]/nm)
    c  = ((v0[0]+v1[0]+v2[0])/3,
          (v0[1]+v1[1]+v2[1])/3,
          (v0[2]+v1[2]+v2[2])/3)
    return n, c


def winding_color(normal, center, centroid):
    """
    Compare face normal to vector from mesh centroid → face center.
    Outward-pointing = correct = green.
    """
    to_face = _sub(center, centroid)
    d = _dot(normal, to_face)
    if   d >  0.15: return COL_OUTWARD
    elif d < -0.15: return COL_INWARD
    else:           return COL_EDGE


# ── default fallback mesh (simple pointy ship if no project available) ─────────

class _FallbackShip:
    verts = {
        'v0': (0,    0,   80),
        'v1': (-30, -15, -40),
        'v2': ( 30, -15, -40),
        'v3': (  0,  25, -40),
        'v4': (  0,   0, -55),
    }
    faces = [
        {'v': ['v0', 'v3', 'v1']}, {'v': ['v0', 'v2', 'v3']}, {'v': ['v0', 'v1', 'v2']},
        {'v': ['v1', 'v3', 'v4']}, {'v': ['v3', 'v2', 'v4']}, {'v': ['v2', 'v1', 'v4']},
    ]
    base_color = (140, 160, 200)
    engine_offsets = [(0, 0, -55)]

    def get_mesh(self):
        return self.verts, self.faces

    def update(self, *a, **kw):
        pass


class PlayerMeshWrapper:
    def __init__(self):
        from src.player import Player
        self.player = Player()
        self.verts = self.player.verts

        accent_color = (0, 255, 200)   # default cyan accent
        C_BODY = (200, 200, 210)
        C_DARK = (45, 45, 50)

        self.faces = [
            # ── NOSE CONE ─────────────────────────────────────────────────────
            {'v': ['needle', 'fwd_top', 'fwd_l'],       'color': C_BODY},
            {'v': ['needle', 'fwd_r',   'fwd_top'],      'color': C_BODY},
            {'v': ['needle', 'fwd_bot', 'fwd_r'],        'color': C_DARK},
            {'v': ['needle', 'fwd_l',   'fwd_bot'],      'color': C_DARK},

            # ── DORSAL SPINE (accent surface) ────────────────────────────────
            {'v': ['fwd_top', 'spine_mid', 'spine_fwd'], 'color': accent_color},
            {'v': ['spine_fwd', 'spine_mid', 'mid_top'], 'color': accent_color},
            {'v': ['spine_mid', 'spine_aft', 'mid_top'], 'color': accent_color},
            {'v': ['spine_aft', 'aft_top',   'mid_top'], 'color': accent_color},

            # ── FWD FUSELAGE SIDES ────────────────────────────────────────────
            {'v': ['fwd_top', 'spine_fwd', 'fwd_l'],     'color': C_BODY},
            {'v': ['fwd_top', 'fwd_r',     'spine_fwd'], 'color': C_BODY},
            {'v': ['fwd_l',   'mid_l',     'fwd_bot'],   'color': C_DARK},
            {'v': ['fwd_r',   'fwd_bot',   'mid_r'],     'color': C_DARK},
            {'v': ['fwd_bot', 'mid_bot',   'mid_r'],     'color': C_DARK},
            {'v': ['fwd_bot', 'mid_l',     'mid_bot'],   'color': C_DARK},

            # ── MID-AFT FUSELAGE ─────────────────────────────────────────────
            {'v': ['mid_top', 'mid_l',  'aft_top'],      'color': C_BODY},
            {'v': ['aft_top', 'mid_l',  'aft_l'],        'color': C_BODY},
            {'v': ['mid_top', 'aft_top','mid_r'],        'color': C_BODY},
            {'v': ['aft_top', 'aft_r',  'mid_r'],        'color': C_BODY},
            {'v': ['mid_l',   'mid_bot','aft_l'],        'color': C_DARK},
            {'v': ['aft_l',   'mid_bot','aft_bot'],      'color': C_DARK},
            {'v': ['mid_r',   'aft_r',  'mid_bot'],      'color': C_DARK},
            {'v': ['aft_r',   'aft_bot','mid_bot'],      'color': C_DARK},

            # ── CANARDS ───────────────────────────────────────────────────────
            {'v': ['cl_base_f', 'cl_tip',    'cl_base_r'], 'color': accent_color},
            {'v': ['cl_base_r', 'cl_tip',    'cl_base_f'], 'color': accent_color},
            {'v': ['cr_base_f', 'cr_base_r', 'cr_tip'],    'color': accent_color},
            {'v': ['cr_base_r', 'cr_base_f', 'cr_tip'],    'color': accent_color},

            # ── INNER WING PANELS ────────────────────────────────────────────
            {'v': ['wrl_fwd', 'wml_le',  'wml_tip'],     'color': C_BODY},
            {'v': ['wrl_fwd', 'mid_l',   'wml_le'],      'color': C_BODY},
            {'v': ['wrl_fwd', 'wml_tip', 'wrl_aft'],     'color': C_DARK},
            {'v': ['wrl_aft', 'wml_tip', 'wml_te'],      'color': C_DARK},
            {'v': ['wrr_fwd', 'wmr_tip', 'wmr_le'],      'color': C_BODY},
            {'v': ['wrr_fwd', 'wmr_le',  'mid_r'],       'color': C_BODY},
            {'v': ['wrr_fwd', 'wrr_aft', 'wmr_tip'],     'color': C_DARK},
            {'v': ['wrr_aft', 'wmr_te',  'wmr_tip'],     'color': C_DARK},

            # ── OUTER WING SWEPT TIPS (accent) ───────────────────────────────
            {'v': ['wml_le',  'wtl',    'wml_tip'],      'color': accent_color},
            {'v': ['wml_tip', 'wtl',    'wtl_te'],       'color': accent_color},
            {'v': ['wml_tip', 'wtl_te', 'wml_te'],       'color': C_BODY},
            {'v': ['wmr_le',  'wmr_tip','wtr'],          'color': accent_color},
            {'v': ['wmr_tip', 'wtr_te', 'wtr'],          'color': accent_color},
            {'v': ['wmr_tip', 'wmr_te', 'wtr_te'],       'color': C_BODY},

            # ── ENGINE NACELLES — LEFT ────────────────────────────────────────
            {'v': ['enl_top_f','enl_in_f', 'enl_top_r'], 'color': C_BODY},
            {'v': ['enl_top_r','enl_in_f', 'enl_in_r'],  'color': C_BODY},
            {'v': ['enl_out_f','enl_top_f','enl_out_r'],  'color': C_BODY},
            {'v': ['enl_out_r','enl_top_f','enl_top_r'],  'color': C_BODY},
            {'v': ['enl_bot_f','enl_out_f','enl_bot_r'],  'color': C_DARK},
            {'v': ['enl_bot_r','enl_out_f','enl_out_r'],  'color': C_DARK},
            {'v': ['enl_in_f', 'enl_bot_f','enl_in_r'],   'color': C_DARK},
            {'v': ['enl_in_r', 'enl_bot_f','enl_bot_r'],  'color': C_DARK},
            {'v': ['enl_top_f','enl_bot_f','enl_in_f'],   'color': accent_color},
            {'v': ['enl_top_f','enl_out_f','enl_bot_f'],  'color': accent_color},

            # ── ENGINE NACELLES — RIGHT ───────────────────────────────────────
            {'v': ['enr_top_f','enr_top_r','enr_in_f'],   'color': C_BODY},
            {'v': ['enr_top_r','enr_in_r', 'enr_in_f'],   'color': C_BODY},
            {'v': ['enr_out_f','enr_out_r','enr_top_f'],   'color': C_BODY},
            {'v': ['enr_out_r','enr_top_r','enr_top_f'],   'color': C_BODY},
            {'v': ['enr_bot_f','enr_bot_r','enr_out_f'],   'color': C_DARK},
            {'v': ['enr_bot_r','enr_out_r','enr_out_f'],   'color': C_DARK},
            {'v': ['enr_in_f', 'enr_in_r', 'enr_bot_f'],  'color': C_DARK},
            {'v': ['enr_in_r', 'enr_bot_r','enr_bot_f'],   'color': C_DARK},
            {'v': ['enr_top_f','enr_in_f', 'enr_bot_f'],   'color': accent_color},
            {'v': ['enr_top_f','enr_bot_f','enr_out_f'],   'color': accent_color},

            # ── V-TAIL ────────────────────────────────────────────────────────
            {'v': ['vtl_base','vtl_tip','vtl_aft'],        'color': accent_color},
            {'v': ['vtl_aft', 'vtl_tip','vtl_base'],       'color': C_BODY},
            {'v': ['vtr_base','vtr_aft','vtr_tip'],        'color': accent_color},
            {'v': ['vtr_aft', 'vtr_base','vtr_tip'],       'color': C_BODY},
        ]
        self.base_color = C_BODY

    def get_mesh(self):
        return self.verts, self.faces

class MissileMeshWrapper:
    def __init__(self):
        from src.missile import PlayerMissile
        self.missile = PlayerMissile(0, 0, 0, 0, 0, 0, 1.0, 10.0)
        self.verts = self.missile.verts
        self.faces = self.missile.faces
        self.base_color = (170, 170, 180)
        
    def get_mesh(self):
        return self.verts, self.faces


# ── viewer ────────────────────────────────────────────────────────────────────

class DebugViewer:
    W, H = 1280, 760
    FPS  = 60

    # debug mode cycle
    DEBUG_MODES = ['off', 'winding', 'normals', 'all']

    def __init__(self, ship_factory=None):
        pygame.init()
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("3D Mesh Debug Viewer")
        self.clock  = pygame.time.Clock()
        _FONT_CACHE = {}
        self.font_sm  = custom_font(12)
        self.font_md  = custom_font(14)
        self.font_lg  = custom_font(16)

        # Available models registry
        import src.enemy as enemy
        self.models = [
            ("Corvette", lambda: enemy.Corvette(0, 0, 0)),
            ("StealthInterceptor", lambda: enemy.StealthInterceptor(0, 0, 0)),
            ("SuicideDrone", lambda: enemy.SuicideDrone(0, 0, 0)),
            ("Dogfighter", lambda: enemy.Dogfighter(0, 0, 0)),
            ("Sniper", lambda: enemy.Sniper(0, 0, 0)),
            ("Minelayer", lambda: enemy.Minelayer(0, 0, 0)),
            ("Carrier", lambda: enemy.Carrier(0, 0, 0)),
            ("Player", lambda: PlayerMeshWrapper()),
            ("PlayerMissile", lambda: MissileMeshWrapper()),
        ]
        self.current_model_idx = 0
        
        # Load first model
        self.load_model(0)

        # camera / transform
        self.obj_quat  = _quat_identity()
        self.camera_z  = 350.0
        self.fov       = 600

        # interaction
        self.is_dragging    = False
        self.last_mouse_pos = (0, 0)
        self.running        = True

        # debug toggles
        self.culling          = True
        self.show_wireframe   = False
        self.show_normals     = False
        self.show_winding     = False
        self.show_face_ids    = False
        self.show_vertex_ids  = False
        self.debug_mode_idx   = 0          # index into DEBUG_MODES
        self.normal_len       = 30.0       # arrow length in world units

        # face selection / editing
        self.selected_face    = 0          # currently highlighted face index
        self.flip_flash       = 0.0        # timer for flash feedback on flip
        self.flip_flash_col   = COL_OUTWARD

        # input for editing
        self.input_mode       = None       # 'add_vertex', 'del_vertex', 'add_face'
        self.input_string     = ""
        self.input_prompt     = ""

        # DS4 (optional)
        try:
            pygame.joystick.init()
            if pygame.joystick.get_count():
                self._joy = pygame.joystick.Joystick(0)
                self._joy.init()
            else:
                self._joy = None
        except Exception:
            self._joy = None

    # ── precompute ────────────────────────────────────────────────────────────

    def _precompute_face_data(self):
        """Cache face normals and winding colours in local (unrotated) space."""
        self._face_normals  = []   # unit normal per face (local)
        self._face_centers  = []   # centroid per face (local)
        self._face_wind_col = []   # winding color per face

        for face in self.faces:
            n, c = face_normal_and_center(self.verts, face)
            col  = winding_color(n, c, self.centroid)
            self._face_normals.append(n)
            self._face_centers.append(c)
            self._face_wind_col.append(col)

    def load_model(self, idx):
        self.current_model_idx = idx
        name, factory = self.models[idx]
        print(f"[mesh loader] Loading model: {name}")
        try:
            self.ship = factory()
            self.verts, self.faces = self.ship.get_mesh()
            self.centroid = mesh_centroid(self.verts)
            self._precompute_face_data()
            self.selected_face = 0
            print(f"[mesh loader] Loaded {name} successfully: {len(self.verts)} verts, {len(self.faces)} faces")
        except Exception as e:
            print(f"[mesh loader] Error loading {name}: {e}")
            import traceback
            traceback.print_exc()

    # ── rotation helpers using the local quat ─────────────────────────────────

    def _rotate_world_point(self, lx, ly, lz):
        """Rotate a local-space point by the current view quaternion."""
        rx, ry, rz = _quat_rot_vec(self.obj_quat, (lx, ly, lz))
        rz += self.camera_z
        return rx, ry, rz

    def _project_world(self, wx, wy, wz):
        return _project(wx, wy, wz, self.fov, self.W//2, self.H//2)

    # ── build render queue ────────────────────────────────────────────────────

    def _build_queue(self):
        """
        Returns list of render items sorted back-to-front.
        Each item: ('face', depth, screen_pts, fill_color, face_idx)
        """
        # rotate all verts
        rot_verts = {}
        for vid, (lx, ly, lz) in self.verts.items():
            rx, ry, rz = _quat_rot_vec(self.obj_quat, (lx, ly, lz))
            rz += self.camera_z
            rot_verts[vid] = (rx, ry, rz)

        queue = []
        cx_s, cy_s = self.W//2, self.H//2

        for fi, face in enumerate(self.faces):
            rv = [rot_verts[i] for i in face['v']]
            v0, v1, v2 = rv

            # face normal in view space
            e1 = _sub(v1, v0)
            e2 = _sub(v2, v0)
            n  = _cross(e1, e2)

            # back-face culling (dot with view-space centroid vector)
            vc = ((v0[0]+v1[0]+v2[0])/3,
                  (v0[1]+v1[1]+v2[1])/3,
                  (v0[2]+v1[2]+v2[2])/3)
            if self.culling and _dot(n, vc) > 0:
                continue

            # project
            pts_2d = []
            valid  = True
            for vx, vy, vz in rv:
                p = _project(vx, vy, vz, self.fov, cx_s, cy_s)
                if p is None:
                    valid = False
                    break
                pts_2d.append((p[0], p[1]))
            if not valid:
                continue

            # lighting
            nm = math.sqrt(n[0]**2+n[1]**2+n[2]**2) or 1.0
            light_dot = max(0.2, (n[0]*0.4 + n[1]*0.5 - n[2]*0.8) / nm)

            # choose fill colour
            if self.show_winding or self.debug_mode_idx in (1, 3):
                base = self._face_wind_col[fi]
            else:
                base = getattr(self.ship, 'base_color', (140, 160, 200))

            fill = tuple(min(255, int(c * light_dot)) for c in base)

            depth = max(v[2] for v in rv)
            queue.append(('face', depth, pts_2d, fill, fi, rv))

        queue.sort(key=lambda x: x[1], reverse=True)
        return queue, rot_verts

    # ── draw overlays ─────────────────────────────────────────────────────────

    def _draw_normal_arrow(self, fi, rot_verts):
        """Project a face's normal as an arrow in screen space."""
        face   = self.faces[fi]
        rv     = [rot_verts[i] for i in face['v']]
        v0, v1, v2 = rv

        # center of face in view space
        cx_w = (v0[0]+v1[0]+v2[0])/3
        cy_w = (v0[1]+v1[1]+v2[1])/3
        cz_w = (v0[2]+v1[2]+v2[2])/3

        # normal in local space, rotate to view space
        ln = self._face_normals[fi]
        rn = _quat_rot_vec(self.obj_quat, ln)

        # tip of arrow
        tip_x = cx_w + rn[0]*self.normal_len
        tip_y = cy_w + rn[1]*self.normal_len
        tip_z = cz_w + rn[2]*self.normal_len

        p0 = _project(cx_w, cy_w, cz_w, self.fov, self.W//2, self.H//2)
        p1 = _project(tip_x, tip_y, tip_z, self.fov, self.W//2, self.H//2)

        if p0 and p1:
            col = self._face_wind_col[fi] if (self.show_winding or self.debug_mode_idx in (1,3)) else COL_NORMAL
            pygame.draw.line(self.screen, col, (p0[0], p0[1]), (p1[0], p1[1]), 2)
            # arrowhead dot
            pygame.draw.circle(self.screen, col, (p1[0], p1[1]), 4)

    # ── face editing ─────────────────────────────────────────────────────────

    def _flip_face(self, fi):
        """Reverse the winding of face fi, update caches, print result."""
        a, b, c = self.faces[fi]['v']
        self.faces[fi]['v'] = [a, c, b]
        n, center = face_normal_and_center(self.verts, self.faces[fi])
        col = winding_color(n, center, self.centroid)
        self._face_normals[fi]  = n
        self._face_centers[fi]  = center
        self._face_wind_col[fi] = col
        self.flip_flash     = 0.4
        self.flip_flash_col = col
        tag = ('OUTWARD' if col == COL_OUTWARD else
               'INWARD'  if col == COL_INWARD  else 'EDGE')
        print(f"[flip] face {fi}: {self.faces[fi]['v']} winding now: {tag}")

    def _flip_all_red(self):
        """Flip every face whose winding colour is COL_INWARD."""
        flipped = []
        for fi in range(len(self.faces)):
            if self._face_wind_col[fi] == COL_INWARD:
                self._flip_face(fi)
                flipped.append(fi)
        print(f"[auto-flip] flipped {len(flipped)} inward faces: {flipped}")
        self.flip_flash     = 0.6
        self.flip_flash_col = COL_OUTWARD

    def _print_faces(self):
        """Dump the current faces list in copy-paste-ready Python syntax."""
        print("\n# ── faces (copy into your enemy class) ──")
        print("self.faces = [")
        for fi, f in enumerate(self.faces):
            col = self._face_wind_col[fi]
            tag = ('OK'   if col == COL_OUTWARD else
                   'FLIP?' if col == COL_INWARD  else 'EDGE')
            print(f"    {f},  # {fi} {tag}")
        print("]\n")
        print("# ── verts ──")
        print("self.verts = {")
        for k, v in self.verts.items():
            print(f"    '{k}': {v},")
        print("}")


    def _confirm_input(self):
        """Process the input string based on current input mode."""
        try:
            if self.input_mode == 'add_vertex':
                parts = self.input_string.split(',')
                if len(parts) == 3:
                    x, y, z = map(float, parts)
                    new_id = f"v{len(self.verts)}"
                    while new_id in self.verts:
                        new_id = f"v{int(new_id[1:])+1}"
                    self.verts[new_id] = (x, y, z)
                    self.centroid = mesh_centroid(self.verts)
                    self._precompute_face_data()
                    print(f"[add vertex] added {len(self.verts)-1}: ({x}, {y}, {z})")
            elif self.input_mode == 'del_vertex':
                idx = self.input_string.strip()
                if idx in self.verts:
                    del self.verts[idx]
                    # remove faces that use this vertex
                    new_faces = []
                    for face in self.faces:
                        if idx in face['v']:
                            continue
                        new_faces.append(face)
                    self.faces = new_faces
                    self.centroid = mesh_centroid(self.verts)
                    self._precompute_face_data()
                    self.selected_face = min(self.selected_face, len(self.faces)-1) if self.faces else 0
                    print(f"[del vertex] deleted {idx}, removed invalid faces")
            elif self.input_mode == 'add_face':
                parts = [p.strip() for p in self.input_string.split(',')]
                if len(parts) == 3:
                    if all(x in self.verts for x in parts):
                        self.faces.append({'v': parts})
                        self._precompute_face_data()
                        print(f"[add face] added {len(self.faces)-1}: ({i}, {j}, {k})")
        except ValueError:
            pass  # invalid input, ignore
        self.input_mode = None

    def _draw_selected_face(self, rot_verts):
        """Always draw selected face, even if backface-culled."""
        fi   = self.selected_face
        if not self.faces: return
        face = self.faces[fi]
        rv   = [rot_verts[i] for i in face['v']]

        pts_2d = []
        for vx, vy, vz in rv:
            p = _project(vx, vy, vz, self.fov, self.W//2, self.H//2)
            if p is None:
                return
            pts_2d.append((p[0], p[1]))

        # pulsing outline
        pulse = abs(math.sin(pygame.time.get_ticks() * 0.006))
        col   = tuple(int(c * (0.5 + 0.5 * pulse)) for c in COL_SELECTED)

        # translucent fill tint
        tint_surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        pygame.draw.polygon(tint_surf, (*COL_SELECTED, 40), pts_2d)
        self.screen.blit(tint_surf, (0, 0))

        # thick pulsing outline
        for i in range(len(pts_2d)):
            pygame.draw.line(self.screen, col,
                             pts_2d[i], pts_2d[(i+1) % len(pts_2d)], 3)

        # normal arrow always shown for selected face
        self._draw_normal_arrow(fi, rot_verts)

        # flash on flip
        if self.flip_flash > 0:
            alpha = int(min(255, self.flip_flash * 600))
            fs = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
            pygame.draw.polygon(fs, (*self.flip_flash_col, alpha), pts_2d)
            self.screen.blit(fs, (0, 0))

    def _draw_wireframe(self, pts_2d):
        for i in range(len(pts_2d)):
            a = pts_2d[i]
            b = pts_2d[(i+1) % len(pts_2d)]
            pygame.draw.line(self.screen, COL_WIREFRAME, a, b, 1)

    def _draw_face_id(self, fi, pts_2d):
        cx = sum(p[0] for p in pts_2d) // len(pts_2d)
        cy = sum(p[1] for p in pts_2d) // len(pts_2d)
        lbl = self.font_lg.render(str(fi), True, (220, 220, 80))
        self.screen.blit(lbl, (cx - lbl.get_width()//2, cy - lbl.get_height()//2))

    def _draw_vertex_id(self, vi, rot_verts):
        vx, vy, vz = rot_verts[vi]
        p = _project(vx, vy, vz, self.fov, self.W//2, self.H//2)
        if p:
            lbl = self.font_sm.render(str(vi), True, (100, 200, 255))
            self.screen.blit(lbl, (p[0] - lbl.get_width()//2, p[1] - lbl.get_height()//2))

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hud(self):
        mode_name = self.DEBUG_MODES[self.debug_mode_idx].upper()

        lines = [
            ("MODEL",    self.models[self.current_model_idx][0]),
            ("VERTS",    str(len(self.verts))),
            ("FACES",    str(len(self.faces))),
            ("",         ""),
            ("DEBUG",    mode_name),
            ("",         ""),
            ("[PgUp/Dn]", "Cycle active mesh"),
            ("[C]",      f"Culling {'ON' if self.culling else 'OFF'}"),
            ("[W]",      f"Wireframe {'ON' if self.show_wireframe else 'OFF'}"),
            ("[N]",      f"Normals {'ON' if self.show_normals else 'OFF'}"),
            ("[F]",      f"Winding col {'ON' if self.show_winding else 'OFF'}"),
            ("[I]",      f"Face IDs {'ON' if self.show_face_ids else 'OFF'}"),
            ("[V]",      f"Vertex IDs {'ON' if self.show_vertex_ids else 'OFF'}"),
            ("[D]",      "Cycle debug"),
            ("[R]",      "Reset"),
            ("",         ""),
            ("[</> arr]", "Select face"),
            ("[SPC/RET]", "Flip winding"),
            ("[X]",      "Flip all red"),
            ("[P]",      "Print faces[]"),
            ("[A]",      "Add vertex"),
            ("[Del]",    "Del vertex"),
            ("[Shift+F]", "Add face"),
            ("",         ""),
            ("[Q/ESC]",  "Quit"),
        ]

        x, y = 18, 18
        for label, value in lines:
            if not label and not value:
                y += 4
                continue
            self.screen.blit(self.font_sm.render(label, True, HUD_DIM),  (x, y))
            self.screen.blit(self.font_sm.render(value, True, HUD_COL),  (x + 115, y))
            y += 17

        # ── selected face panel (right side) ─────────────────────────────
        fi  = self.selected_face
        f   = self.faces[fi]
        col = self._face_wind_col[fi]
        tag = ('OUTWARD' if col == COL_OUTWARD else
               'INWARD'  if col == COL_INWARD  else 'EDGE')
        n   = self._face_normals[fi]

        px = self.W - 280
        py = 18
        panel = [
            ("SELECTED FACE",  ""),
            ("index",          str(fi)),
            ("tuple",          str(f['v'])),
            ("winding",        tag),
            ("normal",         f"({n[0]:+.2f} {n[1]:+.2f} {n[2]:+.2f})"),
        ]
        for label, value in panel:
            if not value:
                surf = self.font_md.render(label, True, ACCENT)
                self.screen.blit(surf, (px, py))
            else:
                self.screen.blit(self.font_sm.render(label + ":", True, HUD_DIM), (px, py))
                vcol = col if label == "winding" else HUD_COL
                self.screen.blit(self.font_sm.render(value, True, vcol), (px + 70, py))
            py += 18

        # ── available meshes selector panel (right side) ─────────────────
        py_m = 160
        surf_hdr = self.font_md.render("AVAILABLE MESHES", True, ACCENT)
        self.screen.blit(surf_hdr, (px, py_m))
        py_m += 24
        
        for idx, (name, _) in enumerate(self.models):
            is_curr = (self.current_model_idx == idx)
            y_item = py_m + idx * 26
            
            if is_curr:
                # Translucent hover highlight
                box_surf = pygame.Surface((260, 22), pygame.SRCALPHA)
                box_surf.fill((80, 160, 255, 35))
                self.screen.blit(box_surf, (px - 10, y_item - 3))
                pygame.draw.rect(self.screen, (80, 160, 255, 180), (px - 10, y_item - 3, 260, 22), 1, border_radius=3)
                
                lbl = self.font_md.render(f"> {name}", True, (255, 255, 255))
            else:
                lbl = self.font_sm.render(f"  {name}", True, (130, 130, 140))
                
            self.screen.blit(lbl, (px, y_item))

        # ── winding legend (bottom-left) ──────────────────────────────────
        lx, ly = 18, self.H - 72
        for lcol, txt in [(COL_OUTWARD, "OUTWARD (correct)"),
                          (COL_INWARD,  "INWARD  (wrong winding)"),
                          (COL_EDGE,    "EDGE CASE")]:
            pygame.draw.rect(self.screen, lcol, (lx, ly, 12, 12))
            self.screen.blit(self.font_sm.render(txt, True, HUD_DIM), (lx+16, ly))
            ly += 18

        # ── input prompt (center-bottom) ──────────────────────────────────
        if self.input_mode:
            prompt_surf = self.font_md.render(self.input_prompt, True, ACCENT)
            self.screen.blit(prompt_surf, (self.W//2 - prompt_surf.get_width()//2, self.H - 100))
            input_surf = self.font_md.render(self.input_string + "_", True, HUD_COL)
            self.screen.blit(input_surf, (self.W//2 - input_surf.get_width()//2, self.H - 80))

    # ── grid / axes ───────────────────────────────────────────────────────────

    def _draw_grid(self):
        cx_s, cy_s = self.W//2, self.H//2
        # draw world-space X and Y axes as projected lines
        origin = _project(0, 0, self.camera_z, self.fov, cx_s, cy_s)
        if not origin:
            return

        def axis_end(lx, ly, lz):
            rx, ry, rz = _quat_rot_vec(self.obj_quat, (lx, ly, lz))
            rz += self.camera_z
            return _project(rx, ry, rz, self.fov, cx_s, cy_s)

        length = max(60, self.camera_z * 0.25)
        for col, ldir in [(AXIS_X, (length, 0, 0)),
                          (AXIS_Y, (0, length, 0)),
                          (AXIS_Z, (0, 0, length))]:
            ep = axis_end(*ldir)
            if ep:
                pygame.draw.line(self.screen, col,
                                 (origin[0], origin[1]),
                                 (ep[0],     ep[1]),     2)

    # ── events ────────────────────────────────────────────────────────────────

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if self.input_mode:
                    k = event.key
                    if k == pygame.K_RETURN:
                        self._confirm_input()
                    elif k == pygame.K_ESCAPE:
                        self.input_mode = None
                    elif k == pygame.K_BACKSPACE:
                        self.input_string = self.input_string[:-1]
                    else:
                        self.input_string += event.unicode
                else:
                    k = event.key
                    n_faces = len(self.faces)
                    if k in (pygame.K_q, pygame.K_ESCAPE):
                        self.running = False
                    elif k == pygame.K_r:
                        self.obj_quat  = _quat_identity()
                        self.camera_z  = 350.0
                    elif k == pygame.K_c:
                        self.culling = not self.culling
                    elif k == pygame.K_w:
                        self.show_wireframe = not self.show_wireframe
                    elif k == pygame.K_n:
                        self.show_normals = not self.show_normals
                    elif k == pygame.K_f:
                        self.show_winding = not self.show_winding
                    elif k == pygame.K_i:
                        self.show_face_ids = not self.show_face_ids
                    elif k == pygame.K_v:
                        self.show_vertex_ids = not self.show_vertex_ids
                    elif k == pygame.K_d:
                        self.debug_mode_idx = (self.debug_mode_idx + 1) % len(self.DEBUG_MODES)
                        m = self.DEBUG_MODES[self.debug_mode_idx]
                        self.show_winding   = m in ('winding', 'all')
                        self.show_normals   = m in ('normals', 'all')
                        self.show_wireframe = m in ('all',)
                        self.show_face_ids  = m in ('all',)
                    # ── face selection ──────────────────────────────────────────
                    elif k == pygame.K_LEFT:
                        self.selected_face = (self.selected_face - 1) % n_faces
                    elif k == pygame.K_RIGHT:
                        self.selected_face = (self.selected_face + 1) % n_faces
                    elif k == pygame.K_UP:
                        self.selected_face = (self.selected_face - 10) % n_faces
                    elif k == pygame.K_DOWN:
                        self.selected_face = (self.selected_face + 10) % n_faces
                    # ── face editing ────────────────────────────────────────────
                    elif k in (pygame.K_SPACE, pygame.K_RETURN):
                        self._flip_face(self.selected_face)
                    elif k == pygame.K_x:
                        self._flip_all_red()
                    elif k == pygame.K_p:
                        self._print_faces()
                    # ── vertex/face editing ───────────────────────────────────────────
                    elif k == pygame.K_a:
                        self.input_mode = 'add_vertex'
                        self.input_string = ""
                        self.input_prompt = "Add vertex: x,y,z"
                    elif k == pygame.K_DELETE:
                        self.input_mode = 'del_vertex'
                        self.input_string = ""
                        self.input_prompt = "Delete vertex index:"
                    elif pygame.key.get_mods() & pygame.KMOD_SHIFT and k == pygame.K_f:
                        self.input_mode = 'add_face'
                        self.input_string = ""
                        self.input_prompt = "Add face: i,j,k"
                    elif k == pygame.K_PAGEUP:
                        self.load_model((self.current_model_idx - 1) % len(self.models))
                    elif k == pygame.K_PAGEDOWN:
                        self.load_model((self.current_model_idx + 1) % len(self.models))

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # Check if clicked inside the mesh selector panel
                    m_x, m_y = event.pos
                    px = self.W - 280
                    clicked_list = False
                    if px - 10 <= m_x <= px + 250:
                        for idx in range(len(self.models)):
                            y_item = 160 + 24 + idx * 26
                            if y_item - 3 <= m_y <= y_item + 19:
                                self.load_model(idx)
                                clicked_list = True
                                break
                    if not clicked_list:
                        self.is_dragging    = True
                        self.last_mouse_pos = event.pos
                elif event.button == 4:
                    self.camera_z = max(50, self.camera_z - 20)
                elif event.button == 5:
                    self.camera_z += 20

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.is_dragging = False

            elif event.type == pygame.MOUSEMOTION and self.is_dragging:
                dx = event.pos[0] - self.last_mouse_pos[0]
                dy = event.pos[1] - self.last_mouse_pos[1]
                self.last_mouse_pos = event.pos
                self.obj_quat = _rotate_yaw(self.obj_quat,   dx * 0.01)
                self.obj_quat = _rotate_pitch(self.obj_quat, dy * 0.01)

        # DS4 stick input
        if self._joy:
            try:
                lx = self._joy.get_axis(0)
                ly = self._joy.get_axis(1)
                ry = self._joy.get_axis(4)
                if abs(lx) > 0.1:
                    self.obj_quat = _rotate_yaw(self.obj_quat,   lx * 0.05)
                if abs(ly) > 0.1:
                    self.obj_quat = _rotate_pitch(self.obj_quat, ly * 0.05)
                if abs(ry) > 0.1:
                    self.camera_z = max(50, self.camera_z + ry * 8)
            except Exception:
                pass

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while self.running:
            dt = self.clock.tick(self.FPS) / 1000.0
            self._handle_events()
            self.screen.fill(BG)
            self._draw_grid()

            self.flip_flash = max(0.0, self.flip_flash - dt)

            queue, rot_verts = self._build_queue()

            for item in queue:
                _, depth, pts_2d, fill, fi, rv = item

                # filled polygon
                if len(pts_2d) >= 3:
                    pygame.draw.polygon(self.screen, fill, pts_2d)

                # wireframe overlay
                if self.show_wireframe or self.debug_mode_idx == 3:
                    self._draw_wireframe(pts_2d)

                # normals
                if self.show_normals or self.debug_mode_idx in (2, 3):
                    self._draw_normal_arrow(fi, rot_verts)

                # face IDs
                if self.show_face_ids or self.debug_mode_idx == 3:
                    self._draw_face_id(fi, pts_2d)

            # selected face always on top — drawn after queue so it's never buried
            self._draw_selected_face(rot_verts)

            if self.show_vertex_ids:
                for vi in range(len(rot_verts)):
                    self._draw_vertex_id(vi, rot_verts)

            self._draw_hud()
            pygame.display.flip()

        pygame.quit()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    viewer = DebugViewer()
    viewer.run()