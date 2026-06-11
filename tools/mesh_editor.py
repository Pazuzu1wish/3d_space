"""
mesh_editor.py
--------------
Standalone OBJ/MTL mesh editor for Redshift Serpens.
Controller-first design (DS4/Xbox via DS4Input), trackpad/keyboard fallback.

Modes
-----
  VIEW   — orbit, zoom, inspect
  VERT   — select + move vertices
  EDGE   — select edges, extrude, collapse
  FACE   — select faces, extrude, flip, subdivide, delete

Controller layout
-----------------
  L-stick          Orbit camera (all modes)
  R-stick Y        Zoom
  L2 / R2          Roll
  X (Cross)        VIEW mode
  Square           VERT mode
  Triangle         FACE mode
  Circle           EDGE mode
  D-pad Left/Right Cycle selection
  D-pad Up/Down    Jump selection ±10
  R1               Confirm / apply operation
  L1               Cancel / undo last op
  Options          Save OBJ
  Share            Load next OBJ in assets/
  L3 (click)       Toggle wireframe
  R3 (click)       Cycle debug overlay

Keyboard fallback
-----------------
  1/2/3/4          VIEW / VERT / EDGE / FACE mode
  Left/Right arr   Cycle selection
  Up/Down arr      Jump ±10
  Space/Enter      Confirm op
  U                Undo
  S                Save
  Tab              Load next OBJ
  W                Toggle wireframe
  D                Cycle debug
  C                Toggle backface culling
  N                Toggle normals
  F                Toggle winding colours
  I                Toggle face IDs
  V                Toggle vertex IDs
  R                Reset camera
  Q/Escape         Quit

Edit operations (VERT mode)
---------------------------
  L-stick (held)   Move selected vertex on screen plane
  R-stick Y        Move vertex along its normal
  D-pad Up/Down    Scale mesh up/down (uniform)
  R1               Confirm move
  L1               Cancel / revert vertex to pre-drag pos

Edit operations (FACE mode)
---------------------------
  R1               Flip selected face winding
  L1               Delete selected face
  D-pad Up         Extrude face (along face normal)
  X (auto)         Flip ALL inward faces

Edit operations (EDGE mode)
---------------------------
  R1               Subdivide selected edge (add midpoint vertex)
  L1               Collapse edge (merge endpoints to midpoint)
"""

import sys
import os
import math
import copy
import glob
import argparse
import pygame

#  Add parent directory to path so src module can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── try importing DS4Input from project; fall back to bundled minimal version ──
_HANDLER_IMPORTED = False
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tools.ds4_debugger import DS4Input
    _HANDLER_IMPORTED = True
except ImportError:
    pass

if not _HANDLER_IMPORTED:
    try:
        from ds4_debugger import DS4Input
        _HANDLER_IMPORTED = True
    except ImportError:
        pass

if not _HANDLER_IMPORTED:
    # Minimal inline DS4Input so the editor runs without the full controller file
    class DS4Input:
        DEADZONE_DEFAULT = 0.20
        def __init__(self, deadzone=0.20):
            self.deadzone = deadzone
            self.connected = False
            self.name = "No controller"
            self.num_buttons = self.num_axes = self.num_hats = 0
            self.rumble_supported = False
            self._held = set()
            self._just_pressed = set()
            self._just_released = set()
            self._axes = {}
            self._joy = None
            self.on_press = self.on_release = self.on_hat = None

        def init(self):
            pygame.joystick.init()
            if pygame.joystick.get_count():
                self._joy = pygame.joystick.Joystick(0)
                self._joy.init()
                self.connected = True
                self.name = self._joy.get_name()
                self.num_buttons = self._joy.get_numbuttons()
                self.num_axes = self._joy.get_numaxes()
            return self.connected

        def process_event(self, event):
            if event.type == pygame.JOYBUTTONDOWN:
                names = ['X','Circle','Triangle','Square','L1','R1','L2','R2',
                         'Share','Options','PS','L3','R3','Touchpad']
                n = names[event.button] if event.button < len(names) else f"Btn{event.button}"
                self._held.add(n); self._just_pressed.add(n)
                if self.on_press: self.on_press(n)
                return True
            if event.type == pygame.JOYBUTTONUP:
                names = ['X','Circle','Triangle','Square','L1','R1','L2','R2',
                         'Share','Options','PS','L3','R3','Touchpad']
                n = names[event.button] if event.button < len(names) else f"Btn{event.button}"
                self._held.discard(n); self._just_released.add(n)
                if self.on_release: self.on_release(n)
                return True
            if event.type == pygame.JOYAXISMOTION:
                self._axes[event.axis] = event.value
                return True
            return False

        def update(self):
            self._just_pressed.clear()
            self._just_released.clear()

        def held(self, b): return b in self._held
        def just_pressed(self, b): return b in self._just_pressed
        def just_released(self, b): return b in self._just_released

        def stick_left(self):
            x = self._axes.get(0, 0.0); y = self._axes.get(1, 0.0)
            return self._dz(x, y)
        def stick_right(self):
            x = self._axes.get(3, 0.0); y = self._axes.get(4, 0.0)
            return self._dz(x, y)
        def trigger_left(self):
            return (self._axes.get(2, -1.0) + 1.0) / 2.0
        def trigger_right(self):
            return (self._axes.get(5, -1.0) + 1.0) / 2.0
        def dpad(self): return (0, 0)

        def _dz(self, x, y):
            m = math.sqrt(x*x + y*y)
            if m < self.deadzone: return 0.0, 0.0
            s = (m - self.deadzone) / (1.0 - self.deadzone) / max(m, 1e-9)
            return x * s, y * s

        def rumble(self, *a, **kw): return False
        def pulse(self, *a, **kw): return False


# ──────────────────────────────────────────────────────────────────────────────
#  COLOURS
# ──────────────────────────────────────────────────────────────────────────────
BG           = (8,   8,  16)
GRID_MAJOR   = (22,  28,  42)
AXIS_X       = (180,  40,  40)
AXIS_Y       = (40,  180,  40)
AXIS_Z       = (40,   80, 200)
HUD_COL      = (140, 200, 255)
HUD_DIM      = (60,   90, 130)
ACCENT       = (80,  160, 255)
ACCENT2      = (255,  80, 140)
WARN         = (255, 180,  40)
GREEN        = (60,  220, 120)
WHITE        = (230, 230, 240)
GRAY         = (100, 100, 130)
DARK_GRAY    = (20,   20,  36)

COL_OUTWARD  = (40,  220,  80)
COL_INWARD   = (220,  40,  40)
COL_EDGE_AMB = (100, 100, 220)
COL_WIRE     = (60,  140, 220)
COL_NORMAL   = (255, 220,  40)
COL_SEL_FACE = (255, 255, 255)
COL_SEL_VERT = (255, 220,  40)
COL_SEL_EDGE = (80,  220, 255)

MODE_COLORS  = {
    'VIEW': (80,  160, 255),
    'VERT': (255, 220,  40),
    'EDGE': (80,  220, 255),
    'FACE': (255,  80, 140),
}

W, H = 1280, 760


# ──────────────────────────────────────────────────────────────────────────────
#  MATH HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def quat_identity():  return (1.0, 0.0, 0.0, 0.0)

def quat_mul(a, b):
    aw,ax,ay,az = a; bw,bx,by,bz = b
    return (aw*bw-ax*bx-ay*by-az*bz,
            aw*bx+ax*bw+ay*bz-az*by,
            aw*by-ax*bz+ay*bw+az*bx,
            aw*bz+ax*by-ay*bx+az*bw)

def quat_norm(q):
    w,x,y,z = q; m = math.sqrt(w*w+x*x+y*y+z*z) or 1.0
    return (w/m, x/m, y/m, z/m)

def quat_conj(q):
    w,x,y,z = q; return (w,-x,-y,-z)

def quat_from_axis_angle(ax,ay,az,a):
    h = a*0.5; s = math.sin(h)
    return (math.cos(h), ax*s, ay*s, az*s)

def quat_rot_vec(q, v):
    vx,vy,vz = v; p = (0.0,vx,vy,vz)
    r = quat_mul(quat_mul(q,p), quat_conj(q))
    return r[1], r[2], r[3]

def rotate_yaw(q, d):
    lu = quat_rot_vec(q, (0.0,1.0,0.0))
    return quat_norm(quat_mul(quat_from_axis_angle(*lu, d), q))

def rotate_pitch(q, d):
    lr = quat_rot_vec(q, (1.0,0.0,0.0))
    return quat_norm(quat_mul(quat_from_axis_angle(*lr, d), q))

def rotate_roll(q, d):
    lf = quat_rot_vec(q, (0.0,0.0,1.0))
    return quat_norm(quat_mul(quat_from_axis_angle(*lf, d), q))

def project(x, y, z, fov=600, cx=640, cy=380):
    if z <= 0.1: return None
    s = fov / z
    return int(x*s+cx), int(y*s+cy), s

def norm3(v):
    x,y,z = v; m = math.sqrt(x*x+y*y+z*z) or 1.0
    return x/m, y/m, z/m

def cross(a, b):
    ax,ay,az = a; bx,by,bz = b
    return (ay*bz-az*by, az*bx-ax*bz, ax*by-ay*bx)

def dot(a, b):  return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def sub(a, b):  return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def add(a, b):  return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def scale(v,s): return (v[0]*s, v[1]*s, v[2]*s)
def midpoint(a,b): return ((a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2)

def vec_len(v): return math.sqrt(v[0]**2+v[1]**2+v[2]**2)


# ──────────────────────────────────────────────────────────────────────────────
#  OBJ LOADER / WRITER
# ──────────────────────────────────────────────────────────────────────────────

def load_obj(path):
    """
    Load an OBJ file.
    Returns:
        verts  : list of (x,y,z) — 0-indexed internally
        faces  : list of {'v': [i,j,k], 'mat': str|None}
        mats   : dict of mat_name -> (r,g,b) diffuse colour (0..255)
        mtl_file: str|None — relative mtl filename referenced
    """
    verts = []
    faces = []
    mats  = {}
    mtl_file = None
    current_mat = None

    # Try to load companion MTL
    mtl_path = path.replace('.obj', '.mtl')
    if os.path.exists(mtl_path):
        mtl_file = os.path.basename(mtl_path)
        mats = _load_mtl(mtl_path)

    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            tok = parts[0].lower()

            if tok == 'mtllib' and len(parts) > 1:
                mtl_ref = parts[1]
                mtl_file = mtl_ref
                # try loading from same dir
                candidate = os.path.join(os.path.dirname(path), mtl_ref)
                if os.path.exists(candidate) and not mats:
                    mats = _load_mtl(candidate)

            elif tok == 'usemtl' and len(parts) > 1:
                current_mat = parts[1]

            elif tok == 'v' and len(parts) >= 4:
                verts.append((float(parts[1]), float(parts[2]), float(parts[3])))

            elif tok == 'f' and len(parts) >= 4:
                # support v, v/vt, v/vt/vn, v//vn formats; fan-triangulate quads+
                idxs = []
                for token in parts[1:]:
                    vi = int(token.split('/')[0])
                    # OBJ is 1-indexed, convert to 0-indexed
                    vi = vi - 1 if vi > 0 else len(verts) + vi
                    idxs.append(vi)
                # fan triangulate
                for k in range(1, len(idxs) - 1):
                    faces.append({'v': [idxs[0], idxs[k], idxs[k+1]],
                                  'mat': current_mat})

    return verts, faces, mats, mtl_file


def _load_mtl(path):
    mats = {}
    current = None
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if parts[0].lower() == 'newmtl' and len(parts) > 1:
                current = parts[1]
                mats[current] = (160, 170, 200)  # default
            elif parts[0].lower() == 'kd' and current and len(parts) >= 4:
                r = min(255, int(float(parts[1]) * 255))
                g = min(255, int(float(parts[2]) * 255))
                b = min(255, int(float(parts[3]) * 255))
                mats[current] = (r, g, b)
    return mats


def save_obj(path, verts, faces, mats, mtl_file):
    """Write verts+faces back to OBJ. Preserves material references."""
    lines = []
    if mtl_file:
        lines.append(f"mtllib {mtl_file}\n")
    lines.append("# Exported by mesh_editor.py\n")
    for v in verts:
        lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
    lines.append("\n")

    current_mat = None
    for face in faces:
        mat = face.get('mat')
        if mat != current_mat:
            if mat:
                lines.append(f"usemtl {mat}\n")
            current_mat = mat
        # OBJ is 1-indexed
        vi = face['v']
        lines.append(f"f {vi[0]+1} {vi[1]+1} {vi[2]+1}\n")

    with open(path, 'w') as f:
        f.writelines(lines)

    # Write MTL if we have material data and a filename
    if mtl_file and mats:
        mtl_path = os.path.join(os.path.dirname(path), mtl_file)
        with open(mtl_path, 'w') as f:
            f.write("# Exported by mesh_editor.py\n")
            for name, col in mats.items():
                f.write(f"newmtl {name}\n")
                f.write(f"Kd {col[0]/255:.4f} {col[1]/255:.4f} {col[2]/255:.4f}\n")
                f.write("Ka 0.1 0.1 0.1\n")
                f.write("Ks 0.0 0.0 0.0\n\n")

    print(f"[save] Wrote {len(verts)} verts, {len(faces)} faces → {path}")


# ──────────────────────────────────────────────────────────────────────────────
#  MESH HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def mesh_centroid(verts):
    if not verts: return (0.0, 0.0, 0.0)
    n = len(verts)
    return (sum(v[0] for v in verts)/n,
            sum(v[1] for v in verts)/n,
            sum(v[2] for v in verts)/n)

def face_normal_center(verts, face):
    v0,v1,v2 = [verts[i] for i in face['v']]
    e1 = sub(v1,v0); e2 = sub(v2,v0)
    n  = cross(e1,e2)
    nm = vec_len(n) or 1.0
    n  = (n[0]/nm, n[1]/nm, n[2]/nm)
    c  = ((v0[0]+v1[0]+v2[0])/3,
          (v0[1]+v1[1]+v2[1])/3,
          (v0[2]+v1[2]+v2[2])/3)
    return n, c

def winding_color(normal, center, centroid):
    d = dot(normal, sub(center, centroid))
    if   d >  0.15: return COL_OUTWARD
    elif d < -0.15: return COL_INWARD
    else:           return COL_EDGE_AMB

def precompute_faces(verts, faces):
    centroid = mesh_centroid(verts)
    normals   = []
    centers   = []
    wind_cols = []
    for face in faces:
        if len(face['v']) < 3 or any(i >= len(verts) for i in face['v']):
            normals.append((0,1,0)); centers.append((0,0,0))
            wind_cols.append(COL_EDGE_AMB)
            continue
        n, c = face_normal_center(verts, face)
        normals.append(n); centers.append(c)
        wind_cols.append(winding_color(n, c, centroid))
    return normals, centers, wind_cols, centroid

def build_edge_list(faces):
    """Return list of (i,j) edges (i<j), deduped."""
    seen = set()
    edges = []
    for fi, face in enumerate(faces):
        vs = face['v']
        for k in range(len(vs)):
            a, b = vs[k], vs[(k+1) % len(vs)]
            key = (min(a,b), max(a,b))
            if key not in seen:
                seen.add(key)
                edges.append(key)
    return edges

def scale_mesh(verts, factor, centroid=None):
    """Scale all verts around centroid (or origin)."""
    if centroid is None:
        centroid = mesh_centroid(verts)
    cx,cy,cz = centroid
    return [(cx + (v[0]-cx)*factor,
             cy + (v[1]-cy)*factor,
             cz + (v[2]-cz)*factor) for v in verts]


# ──────────────────────────────────────────────────────────────────────────────
#  UNDO STACK
# ──────────────────────────────────────────────────────────────────────────────

class UndoStack:
    def __init__(self, limit=32):
        self._stack = []
        self._limit = limit

    def push(self, verts, faces):
        self._stack.append((copy.deepcopy(verts), copy.deepcopy(faces)))
        if len(self._stack) > self._limit:
            self._stack.pop(0)

    def pop(self):
        if self._stack:
            return self._stack.pop()
        return None

    def __len__(self): return len(self._stack)


# ──────────────────────────────────────────────────────────────────────────────
#  EDITOR
# ──────────────────────────────────────────────────────────────────────────────

class MeshEditor:
    FPS = 60
    MODES = ['VIEW', 'VERT', 'EDGE', 'FACE']
    DEBUG_MODES = ['off', 'winding', 'normals', 'all']

    def __init__(self, assets_dir='assets'):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Mesh Editor — Redshift Serpens")
        self.clock  = pygame.time.Clock()

        try:
            self.font_sm = pygame.font.SysFont("Courier New", 11)
            self.font_md = pygame.font.SysFont("Courier New", 13, bold=True)
            self.font_lg = pygame.font.SysFont("Courier New", 15, bold=True)
        except:
            self.font_sm = pygame.font.SysFont(None, 12)
            self.font_md = pygame.font.SysFont(None, 14, bold=True)
            self.font_lg = pygame.font.SysFont(None, 16, bold=True)

        # ── controller ──
        self.ctrl = DS4Input()
        self.ctrl.init()

        # ── file list ──
        self.assets_dir = assets_dir
        self.obj_files  = sorted(glob.glob(os.path.join(assets_dir, '**', '*.obj'),
                                           recursive=True))
        if not self.obj_files:
            self.obj_files = sorted(glob.glob(os.path.join(assets_dir, '*.obj')))
        self.file_idx = 0

        # ── mesh state ──
        self.verts     = []
        self.faces     = []
        self.mats      = {}
        self.mtl_file  = None
        self.obj_path  = None
        self.normals   = []
        self.centers   = []
        self.wind_cols = []
        self.centroid  = (0,0,0)
        self.edges     = []

        self.undo = UndoStack()

        # ── camera ──
        self.obj_quat = quat_identity()
        self.camera_z = 350.0
        self.fov      = 600

        # ── interaction ──
        self.running         = True
        self.mode            = 'VIEW'
        self.debug_idx       = 0
        self.culling         = True
        self.show_wireframe  = False
        self.show_normals    = False
        self.show_winding    = False
        self.show_face_ids   = False
        self.show_vert_ids   = False

        # ── selection ──
        self.sel_face  = 0
        self.sel_vert  = 0
        self.sel_edge  = 0

        # ── drag state (VERT mode) ──
        self.dragging_vert   = False
        self.drag_origin     = None  # original vert pos before drag
        self.drag_screen_ref = None  # screen pos at drag start

        # ── mouse ──
        self.is_dragging    = False
        self.last_mouse_pos = (0, 0)

        # ── flash feedback ──
        self.flash_timer = 0.0
        self.flash_col   = COL_OUTWARD
        self.status_msg  = ""
        self.status_timer = 0.0

        # ── dpad held repeat ──
        self._dpad_repeat_timer = 0.0
        self._dpad_repeat_delay = 0.18
        self._dpad_last = (0, 0)

        # load first file or create empty mesh
        if self.obj_files:
            self._load_file(self.obj_files[0])
        else:
            self._new_mesh()
            self.status("No OBJ files found in assets/ — starting empty mesh")

    # ── status ───────────────────────────────────────────────────────────────

    def status(self, msg, col=None):
        self.status_msg   = msg
        self.status_timer = 3.0
        self.flash_col    = col or GREEN
        print(f"[editor] {msg}")

    # ── mesh management ───────────────────────────────────────────────────────

    def _new_mesh(self):
        self.verts    = []
        self.faces    = []
        self.mats     = {}
        self.mtl_file = None
        self.obj_path = None
        self._refresh()

    def _load_file(self, path):
        try:
            v, f, m, mtl = load_obj(path)
            self.verts    = v
            self.faces    = f
            self.mats     = m
            self.mtl_file = mtl
            self.obj_path = path
            self.sel_face = 0
            self.sel_vert = 0
            self.sel_edge = 0
            self._refresh()
            self.status(f"Loaded {os.path.basename(path)}: {len(v)}v {len(f)}f")
        except Exception as e:
            self.status(f"Load error: {e}", WARN)

    def _load_next(self):
        if not self.obj_files:
            self.status("No OBJ files found")
            return
        self.file_idx = (self.file_idx + 1) % len(self.obj_files)
        self._load_file(self.obj_files[self.file_idx])

    def _save(self):
        if not self.obj_path:
            self.status("No path — set obj_path first", WARN)
            return
        save_obj(self.obj_path, self.verts, self.faces, self.mats, self.mtl_file)
        self.status(f"Saved → {os.path.basename(self.obj_path)}")

    def _refresh(self):
        """Recompute derived data after any mesh change."""
        self.normals, self.centers, self.wind_cols, self.centroid = \
            precompute_faces(self.verts, self.faces)
        self.edges = build_edge_list(self.faces)
        # clamp selections
        if self.faces:
            self.sel_face = max(0, min(self.sel_face, len(self.faces)-1))
        if self.verts:
            self.sel_vert = max(0, min(self.sel_vert, len(self.verts)-1))
        if self.edges:
            self.sel_edge = max(0, min(self.sel_edge, len(self.edges)-1))

    # ── undo helpers ─────────────────────────────────────────────────────────

    def _push_undo(self):
        self.undo.push(self.verts, self.faces)

    def _do_undo(self):
        state = self.undo.pop()
        if state:
            self.verts, self.faces = state
            self._refresh()
            self.status(f"Undo ({len(self.undo)} left)")
        else:
            self.status("Nothing to undo", WARN)

    # ── edit operations ───────────────────────────────────────────────────────

    def _flip_face(self, fi):
        self._push_undo()
        f = self.faces[fi]
        f['v'] = [f['v'][0], f['v'][2], f['v'][1]]
        self._refresh()
        self.flash_timer = 0.5
        self.flash_col   = COL_OUTWARD
        self.status(f"Flipped face {fi}")

    def _flip_all_inward(self):
        self._push_undo()
        count = 0
        for fi, col in enumerate(self.wind_cols):
            if col == COL_INWARD:
                f = self.faces[fi]
                f['v'] = [f['v'][0], f['v'][2], f['v'][1]]
                count += 1
        self._refresh()
        self.status(f"Flipped {count} inward faces")

    def _delete_face(self, fi):
        self._push_undo()
        self.faces.pop(fi)
        self._refresh()
        self.status(f"Deleted face {fi}")

    def _extrude_face(self, fi, amount=8.0):
        """Extrude a face along its normal, creating side faces."""
        self._push_undo()
        face  = self.faces[fi]
        n, c  = face_normal_center(self.verts, face)
        offs  = scale(n, amount)
        old_v = face['v']
        mat   = face.get('mat')

        # add new verts offset along normal
        new_v = []
        for vi in old_v:
            nv = add(self.verts[vi], offs)
            self.verts.append(nv)
            new_v.append(len(self.verts)-1)

        # replace original face with new extruded cap
        self.faces[fi] = {'v': new_v, 'mat': mat}

        # build side quads as two triangles each
        for k in range(len(old_v)):
            a0 = old_v[k]; a1 = old_v[(k+1) % len(old_v)]
            b0 = new_v[k]; b1 = new_v[(k+1) % len(old_v)]
            self.faces.append({'v': [a0, a1, b1], 'mat': mat})
            self.faces.append({'v': [a0, b1, b0], 'mat': mat})

        self._refresh()
        self.status(f"Extruded face {fi} by {amount:.1f}")

    def _subdivide_edge(self, ei):
        """Add midpoint vertex and split all faces using this edge."""
        self._push_undo()
        if not self.edges: return
        a, b = self.edges[ei]
        mid = midpoint(self.verts[a], self.verts[b])
        self.verts.append(mid)
        mid_idx = len(self.verts) - 1

        new_faces = []
        for face in self.faces:
            vs = face['v']
            mat = face.get('mat')
            # find if this edge is in the face
            split = False
            for k in range(len(vs)):
                fa = vs[k]; fb = vs[(k+1) % len(vs)]
                if (min(fa,fb), max(fa,fb)) == (min(a,b), max(a,b)):
                    # split this triangle into two
                    third = vs[(k+2) % len(vs)]
                    new_faces.append({'v': [fa, mid_idx, third], 'mat': mat})
                    new_faces.append({'v': [mid_idx, fb, third], 'mat': mat})
                    split = True
                    break
            if not split:
                new_faces.append(face)

        self.faces = new_faces
        self._refresh()
        self.status(f"Subdivided edge {ei}")

    def _collapse_edge(self, ei):
        """Merge edge endpoints to midpoint, removing degenerate faces."""
        self._push_undo()
        if not self.edges: return
        a, b = self.edges[ei]
        mid = midpoint(self.verts[a], self.verts[b])
        # place midpoint at index a, remap b → a
        self.verts[a] = mid
        # remap all references: b → a
        new_faces = []
        for face in self.faces:
            vs = [a if vi == b else vi for vi in face['v']]
            # skip degenerate (two same indices)
            if len(set(vs)) == 3:
                new_faces.append({'v': vs, 'mat': face.get('mat')})
        # remove vertex b by remapping all higher indices down
        self.verts.pop(b)
        remapped = []
        for face in new_faces:
            vs = [vi if vi < b else vi-1 for vi in face['v']]
            remapped.append({'v': vs, 'mat': face.get('mat')})
        self.faces = remapped
        self._refresh()
        self.status(f"Collapsed edge {ei}")

    def _scale_uniform(self, factor):
        self._push_undo()
        self.verts = scale_mesh(self.verts, factor, self.centroid)
        self._refresh()
        self.status(f"Scale ×{factor:.2f}")

    # ── projection / rotation ─────────────────────────────────────────────────

    def _rot_verts(self):
        """Rotate all verts by current quat, return dict index→(rx,ry,rz)."""
        rv = []
        for vx,vy,vz in self.verts:
            rx,ry,rz = quat_rot_vec(self.obj_quat, (vx,vy,vz))
            rv.append((rx, ry, rz+self.camera_z))
        return rv

    def _proj(self, rx, ry, rz):
        return project(rx, ry, rz, self.fov, W//2, H//2)

    # ── render queue ──────────────────────────────────────────────────────────

    def _build_queue(self, rot_verts):
        queue = []
        cx_s, cy_s = W//2, H//2
        for fi, face in enumerate(self.faces):
            vs = face['v']
            if any(i >= len(rot_verts) for i in vs): continue
            rv = [rot_verts[i] for i in vs]
            v0,v1,v2 = rv
            e1 = sub(v1,v0); e2 = sub(v2,v0)
            n  = cross(e1,e2)
            vc = ((v0[0]+v1[0]+v2[0])/3,
                  (v0[1]+v1[1]+v2[1])/3,
                  (v0[2]+v1[2]+v2[2])/3)
            if self.culling and dot(n, vc) > 0:
                continue
            pts = []
            valid = True
            for vx,vy,vz in rv:
                p = project(vx, vy, vz, self.fov, cx_s, cy_s)
                if p is None: valid = False; break
                pts.append((p[0],p[1]))
            if not valid: continue
            nm = vec_len(n) or 1.0
            light = max(0.2, (n[0]*0.4+n[1]*0.5-n[2]*0.8) / nm)
            if self.show_winding or self.debug_idx in (1,3):
                base = self.wind_cols[fi] if fi < len(self.wind_cols) else (160,170,200)
            else:
                mat = face.get('mat')
                base = self.mats.get(mat, (140,160,200)) if mat else (140,160,200)
            fill = tuple(min(255, int(c*light)) for c in base)
            depth = max(v[2] for v in rv)
            queue.append((depth, pts, fill, fi, rv))
        queue.sort(key=lambda x: x[0], reverse=True)
        return queue

    # ── draw helpers ──────────────────────────────────────────────────────────

    def _draw_normal_arrow(self, fi, rot_verts):
        if fi >= len(self.faces): return
        face = self.faces[fi]
        vs = face['v']
        if any(i >= len(rot_verts) for i in vs): return
        rv = [rot_verts[i] for i in vs]
        cx_ = sum(v[0] for v in rv)/3
        cy_ = sum(v[1] for v in rv)/3
        cz_ = sum(v[2] for v in rv)/3
        n, _ = face_normal_center(self.verts, face)
        nr = quat_rot_vec(self.obj_quat, n)
        ex = cx_ + nr[0]*28
        ey = cy_ + nr[1]*28
        ez = cz_ + nr[2]*28 + self.camera_z - (cz_) # adjust
        # re-project properly
        pc = project(cx_, cy_, cz_, self.fov, W//2, H//2)
        pe = project(cx_+nr[0]*28, cy_+nr[1]*28, cz_+nr[2]*28,
                     self.fov, W//2, H//2)
        if pc and pe:
            pygame.draw.line(self.screen, COL_NORMAL, (pc[0],pc[1]), (pe[0],pe[1]), 2)
            pygame.draw.circle(self.screen, COL_NORMAL, (pe[0],pe[1]), 3)

    def _draw_vert(self, vi, rot_verts, color, r=5):
        if vi >= len(rot_verts): return
        vx,vy,vz = rot_verts[vi]
        p = project(vx, vy, vz, self.fov, W//2, H//2)
        if p:
            pygame.draw.circle(self.screen, color, (p[0],p[1]), r)
            pygame.draw.circle(self.screen, WHITE,  (p[0],p[1]), r, 1)

    def _draw_edge(self, ei, rot_verts, color, width=2):
        if not self.edges or ei >= len(self.edges): return
        a, b = self.edges[ei]
        if a >= len(rot_verts) or b >= len(rot_verts): return
        pa = project(*rot_verts[a], self.fov, W//2, H//2)
        pb = project(*rot_verts[b], self.fov, W//2, H//2)
        if pa and pb:
            pygame.draw.line(self.screen, color, (pa[0],pa[1]), (pb[0],pb[1]), width)

    def _draw_selected_face(self, fi, rot_verts):
        if not self.faces or fi >= len(self.faces): return
        face = self.faces[fi]
        vs = face['v']
        if any(i >= len(rot_verts) for i in vs): return
        rv = [rot_verts[i] for i in vs]
        pts = []
        for vx,vy,vz in rv:
            p = project(vx, vy, vz, self.fov, W//2, H//2)
            if p is None: return
            pts.append((p[0],p[1]))
        pulse = abs(math.sin(pygame.time.get_ticks() * 0.006))
        col   = tuple(int(c*(0.5+0.5*pulse)) for c in COL_SEL_FACE)
        tint  = pygame.Surface((W,H), pygame.SRCALPHA)
        pygame.draw.polygon(tint, (*COL_SEL_FACE, 35), pts)
        self.screen.blit(tint, (0,0))
        for k in range(len(pts)):
            pygame.draw.line(self.screen, col, pts[k], pts[(k+1)%len(pts)], 2)
        if self.flash_timer > 0:
            alpha = int(min(255, self.flash_timer * 500))
            fs = pygame.Surface((W,H), pygame.SRCALPHA)
            pygame.draw.polygon(fs, (*self.flash_col, alpha), pts)
            self.screen.blit(fs, (0,0))

    def _draw_axes(self):
        origin_local = (0,0,0)
        ox,oy,oz = quat_rot_vec(self.obj_quat, origin_local)
        oz += self.camera_z
        op = project(ox, oy, oz, self.fov, W//2, H//2)
        if not op: return
        length = max(40, self.camera_z * 0.12)
        for col, ldir in [(AXIS_X,(length,0,0)),
                          (AXIS_Y,(0,length,0)),
                          (AXIS_Z,(0,0,length))]:
            rx,ry,rz = quat_rot_vec(self.obj_quat, ldir)
            rz += self.camera_z
            ep = project(rx, ry, rz, self.fov, W//2, H//2)
            if ep:
                pygame.draw.line(self.screen, col, (op[0],op[1]), (ep[0],ep[1]), 2)

    def _draw_all_verts(self, rot_verts):
        for vi in range(len(rot_verts)):
            col = COL_SEL_VERT if vi == self.sel_vert else GRAY
            r   = 6 if vi == self.sel_vert else 3
            self._draw_vert(vi, rot_verts, col, r)

    def _draw_all_edges(self, rot_verts):
        for ei in range(len(self.edges)):
            col   = COL_SEL_EDGE if ei == self.sel_edge else (50, 90, 140)
            width = 3 if ei == self.sel_edge else 1
            self._draw_edge(ei, rot_verts, col, width)

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hud(self):
        mode_col = MODE_COLORS.get(self.mode, ACCENT)
        x, y = 14, 14

        def row(lbl, val, vcol=HUD_COL):
            nonlocal y
            if lbl == '---':
                y += 5; return
            self.screen.blit(self.font_sm.render(lbl, True, HUD_DIM), (x, y))
            self.screen.blit(self.font_sm.render(str(val), True, vcol), (x+110, y))
            y += 16

        # mode badge
        badge = self.font_lg.render(f"[ {self.mode} ]", True, mode_col)
        self.screen.blit(badge, (x, y)); y += 22

        row('FILE', os.path.basename(self.obj_path) if self.obj_path else '—')
        row('VERTS', len(self.verts))
        row('FACES', len(self.faces))
        row('EDGES', len(self.edges))
        row('UNDO', len(self.undo))
        row('---','')
        row('DEBUG', self.DEBUG_MODES[self.debug_idx].upper())
        row('---','')

        # mode-specific info
        if self.mode == 'VIEW':
            row('[1/X]',     'VIEW mode',   HUD_DIM)
            row('[2/Sq]',    'VERT mode',   HUD_DIM)
            row('[3/Tri]',   'FACE mode',   HUD_DIM)
            row('[4/Cir]',   'EDGE mode',   HUD_DIM)
        elif self.mode == 'VERT':
            row('SEL VERT',  self.sel_vert, COL_SEL_VERT)
            if self.verts and self.sel_vert < len(self.verts):
                v = self.verts[self.sel_vert]
                row('pos', f"({v[0]:.1f} {v[1]:.1f} {v[2]:.1f})")
            row('---','')
            row('[D</>]',    'Cycle vert',  HUD_DIM)
            row('[L-stick]', 'Move vert',   HUD_DIM)
            row('[D↑/↓]',    'Scale ±2%',  HUD_DIM)
            row('[R1]',      'Confirm',     HUD_DIM)
            row('[L1/U]',    'Undo',        HUD_DIM)
        elif self.mode == 'FACE':
            row('SEL FACE', self.sel_face, COL_SEL_FACE)
            if self.wind_cols and self.sel_face < len(self.wind_cols):
                wc = self.wind_cols[self.sel_face]
                tag = ('OUTWARD' if wc==COL_OUTWARD else
                       'INWARD'  if wc==COL_INWARD  else 'EDGE')
                row('winding', tag, wc)
            row('---','')
            row('[D</>]',   'Cycle face',  HUD_DIM)
            row('[R1/Spc]', 'Flip winding',HUD_DIM)
            row('[L1]',     'Delete face', HUD_DIM)
            row('[D↑]',     'Extrude',     HUD_DIM)
            row('[X key]',  'Flip all red',HUD_DIM)
        elif self.mode == 'EDGE':
            row('SEL EDGE', self.sel_edge, COL_SEL_EDGE)
            if self.edges and self.sel_edge < len(self.edges):
                e = self.edges[self.sel_edge]
                row('verts', f"{e[0]} — {e[1]}")
            row('---','')
            row('[D</>]',   'Cycle edge',  HUD_DIM)
            row('[R1]',     'Subdivide',   HUD_DIM)
            row('[L1]',     'Collapse',    HUD_DIM)

        row('---','')
        row('[Tab/Share]','Next OBJ',  HUD_DIM)
        row('[S/Opt]',    'Save',      HUD_DIM)
        row('[R]',        'Reset cam', HUD_DIM)
        row('[W]',        f"Wire {'ON' if self.show_wireframe else 'OFF'}", HUD_DIM)
        row('[C]',        f"Cull {'ON' if self.culling else 'OFF'}",       HUD_DIM)
        row('[D key]',    'Debug cycle',HUD_DIM)
        row('[Q/ESC]',    'Quit',       HUD_DIM)

        # status bar
        if self.status_timer > 0:
            alpha = min(1.0, self.status_timer) * 255
            msg_surf = self.font_md.render(self.status_msg, True, self.flash_col)
            self.screen.blit(msg_surf, (W//2 - msg_surf.get_width()//2, H-34))

        # controller indicator
        ctrl_col = GREEN if self.ctrl.connected else (80,80,80)
        ctrl_txt = f"ctrl: {self.ctrl.name[:30]}" if self.ctrl.connected else "ctrl: none"
        c_surf = self.font_sm.render(ctrl_txt, True, ctrl_col)
        self.screen.blit(c_surf, (14, H-20))

        # fps
        fps_surf = self.font_sm.render(f"{self.clock.get_fps():.0f}fps", True, HUD_DIM)
        self.screen.blit(fps_surf, (W-54, H-20))

        # file list panel (right side)
        px = W - 260
        py = 14
        hdr = self.font_md.render("OBJ FILES", True, ACCENT)
        self.screen.blit(hdr, (px, py)); py += 20
        for fi, fp in enumerate(self.obj_files[:20]):
            name = os.path.basename(fp)
            is_cur = fi == self.file_idx
            col = WHITE if is_cur else GRAY
            prefix = '> ' if is_cur else '  '
            lbl = self.font_sm.render(prefix + name[:28], True, col)
            self.screen.blit(lbl, (px, py)); py += 15

    # ── controller-driven vertex drag ─────────────────────────────────────────

    def _vert_move_controller(self, dt):
        """Move selected vertex with L-stick (screen plane) while in VERT mode."""
        lx, ly = self.ctrl.stick_left()
        if abs(lx) < 0.05 and abs(ly) < 0.05:
            return
        if not self.verts: return
        vi = self.sel_vert
        vx,vy,vz = self.verts[vi]
        # rotate vert to view space to get screen-plane axes
        rv = quat_rot_vec(self.obj_quat, (vx,vy,vz))
        rz = rv[2] + self.camera_z
        if rz < 0.5: return
        scale_factor = rz / self.fov  # screen units → world units
        # L-stick moves on screen plane — unproject into local space
        # right = screen +x; up = screen -y  (pygame y-down)
        right = quat_rot_vec(quat_conj(self.obj_quat), (1,0,0))
        up    = quat_rot_vec(quat_conj(self.obj_quat), (0,-1,0))
        speed = 80.0 * scale_factor * dt
        self.verts[vi] = (
            vx + (right[0]*lx + up[0]*ly) * speed,
            vy + (right[1]*lx + up[1]*ly) * speed,
            vz + (right[2]*lx + up[2]*ly) * speed,
        )
        self._refresh()

    # ── dpad selection with held repeat ──────────────────────────────────────

    def _sel_delta(self, delta):
        if self.mode == 'VERT' and self.verts:
            self.sel_vert = (self.sel_vert + delta) % len(self.verts)
        elif self.mode == 'FACE' and self.faces:
            self.sel_face = (self.sel_face + delta) % len(self.faces)
        elif self.mode == 'EDGE' and self.edges:
            self.sel_edge = (self.sel_edge + delta) % len(self.edges)

    def _handle_dpad_repeat(self, dt):
        dp = self.ctrl.dpad()
        dx, dy = dp
        if dx == 0 and dy == 0:
            self._dpad_repeat_timer = 0.0
            self._dpad_last = (0,0)
            return
        if dp != self._dpad_last:
            self._dpad_last = dp
            self._dpad_repeat_timer = self._dpad_repeat_delay
            self._fire_dpad(dx, dy)
        else:
            self._dpad_repeat_timer -= dt
            if self._dpad_repeat_timer <= 0:
                self._dpad_repeat_timer = 0.06  # fast repeat
                self._fire_dpad(dx, dy)

    def _fire_dpad(self, dx, dy):
        if dx > 0: self._sel_delta(1)
        if dx < 0: self._sel_delta(-1)
        if dy > 0:  # up
            if self.mode == 'VERT':
                self._scale_uniform(1.02)
            elif self.mode == 'FACE':
                self._extrude_face(self.sel_face)
            else:
                self._sel_delta(-10)
        if dy < 0:  # down
            if self.mode == 'VERT':
                self._scale_uniform(0.98)
            else:
                self._sel_delta(10)

    # ── confirm / cancel per mode ─────────────────────────────────────────────

    def _confirm(self):
        if self.mode == 'FACE':
            self._flip_face(self.sel_face)
        elif self.mode == 'EDGE':
            self._subdivide_edge(self.sel_edge)
        elif self.mode == 'VERT':
            self.dragging_vert = False
            self.status(f"Vert {self.sel_vert} committed")

    def _cancel(self):
        if self.mode == 'FACE':
            self._delete_face(self.sel_face)
        elif self.mode == 'EDGE':
            self._collapse_edge(self.sel_edge)
        elif self.mode == 'VERT':
            self._do_undo()
        else:
            self._do_undo()

    # ── event handling ────────────────────────────────────────────────────────

    def _handle_events(self, dt):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            self.ctrl.process_event(event)

            if event.type == pygame.KEYDOWN:
                k = event.key
                if k in (pygame.K_q, pygame.K_ESCAPE):
                    self.running = False
                elif k == pygame.K_1: self.mode = 'VIEW'
                elif k == pygame.K_2: self.mode = 'VERT'
                elif k == pygame.K_3: self.mode = 'FACE'
                elif k == pygame.K_4: self.mode = 'EDGE'
                elif k == pygame.K_r:
                    self.obj_quat = quat_identity()
                    self.camera_z = 350.0
                elif k == pygame.K_c: self.culling = not self.culling
                elif k == pygame.K_w: self.show_wireframe = not self.show_wireframe
                elif k == pygame.K_n: self.show_normals = not self.show_normals
                elif k == pygame.K_f: self.show_winding = not self.show_winding
                elif k == pygame.K_i: self.show_face_ids = not self.show_face_ids
                elif k == pygame.K_v: self.show_vert_ids = not self.show_vert_ids
                elif k == pygame.K_d:
                    self.debug_idx = (self.debug_idx + 1) % len(self.DEBUG_MODES)
                    m = self.DEBUG_MODES[self.debug_idx]
                    self.show_winding   = m in ('winding','all')
                    self.show_normals   = m in ('normals','all')
                    self.show_wireframe = m == 'all'
                    self.show_face_ids  = m == 'all'
                elif k == pygame.K_s: self._save()
                elif k == pygame.K_TAB: self._load_next()
                elif k == pygame.K_u: self._do_undo()
                elif k == pygame.K_x and self.mode == 'FACE':
                    self._flip_all_inward()
                elif k in (pygame.K_SPACE, pygame.K_RETURN):
                    self._confirm()
                elif k == pygame.K_DELETE and self.mode == 'FACE':
                    self._cancel()
                elif k == pygame.K_LEFT:  self._sel_delta(-1)
                elif k == pygame.K_RIGHT: self._sel_delta(1)
                elif k == pygame.K_UP:    self._sel_delta(-10)
                elif k == pygame.K_DOWN:  self._sel_delta(10)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.is_dragging    = True
                    self.last_mouse_pos = event.pos
                elif event.button == 4: self.camera_z = max(30, self.camera_z - 15)
                elif event.button == 5: self.camera_z = min(3000, self.camera_z + 15)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1: self.is_dragging = False

            elif event.type == pygame.MOUSEMOTION and self.is_dragging:
                dx_ = event.pos[0] - self.last_mouse_pos[0]
                dy_ = event.pos[1] - self.last_mouse_pos[1]
                self.last_mouse_pos = event.pos
                self.obj_quat = rotate_yaw(self.obj_quat,   dx_ * 0.01)
                self.obj_quat = rotate_pitch(self.obj_quat, dy_ * 0.01)

        # ── controller button actions (post-event) ──
        if self.ctrl.just_pressed('X'):       self.mode = 'VIEW'
        if self.ctrl.just_pressed('Square'):  self.mode = 'VERT'
        if self.ctrl.just_pressed('Triangle'):self.mode = 'FACE'
        if self.ctrl.just_pressed('Circle'):  self.mode = 'EDGE'
        if self.ctrl.just_pressed('R1'):      self._confirm()
        if self.ctrl.just_pressed('L1'):      self._cancel()
        if self.ctrl.just_pressed('Options'): self._save()
        if self.ctrl.just_pressed('Share'):   self._load_next()
        if self.ctrl.just_pressed('L3'):      self.show_wireframe = not self.show_wireframe
        if self.ctrl.just_pressed('R3'):
            self.debug_idx = (self.debug_idx + 1) % len(self.DEBUG_MODES)
            m = self.DEBUG_MODES[self.debug_idx]
            self.show_winding   = m in ('winding','all')
            self.show_normals   = m in ('normals','all')
            self.show_wireframe = m == 'all'

        if self.mode == 'FACE' and self.ctrl.just_pressed('X'):
            # X in face mode = flip all inward (reachable via keyboard too)
            pass  # X in controller is VIEW — use keyboard x for flip-all

        # ── controller analog ──
        lx, ly = self.ctrl.stick_left()
        ry_val = self.ctrl.stick_right()[1]
        l2 = self.ctrl.trigger_left()
        r2 = self.ctrl.trigger_right()

        # orbit only in VIEW / FACE / EDGE; in VERT L-stick moves vertex
        if self.mode == 'VERT':
            if self.verts:
                self._vert_move_controller(dt)
        else:
            if abs(lx) > 0.05:
                self.obj_quat = rotate_yaw(self.obj_quat,   lx * 0.05)
            if abs(ly) > 0.05:
                self.obj_quat = rotate_pitch(self.obj_quat, ly * 0.05)

        if abs(ry_val) > 0.05:
            self.camera_z = max(30, min(3000, self.camera_z + ry_val * 10))
        if l2 > 0.1:
            self.obj_quat = rotate_roll(self.obj_quat, -l2 * 0.04)
        if r2 > 0.1:
            self.obj_quat = rotate_roll(self.obj_quat,  r2 * 0.04)

        self._handle_dpad_repeat(dt)
        self.ctrl.update()

    # ── main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while self.running:
            dt = self.clock.tick(self.FPS) / 1000.0
            self.flash_timer  = max(0.0, self.flash_timer  - dt)
            self.status_timer = max(0.0, self.status_timer - dt)

            self._handle_events(dt)

            self.screen.fill(BG)
            self._draw_axes()

            rot_verts = self._rot_verts()
            queue     = self._build_queue(rot_verts)

            for depth, pts, fill, fi, rv in queue:
                if len(pts) >= 3:
                    pygame.draw.polygon(self.screen, fill, pts)
                if self.show_wireframe or self.debug_idx == 3:
                    for k in range(len(pts)):
                        pygame.draw.line(self.screen, COL_WIRE,
                                         pts[k], pts[(k+1)%len(pts)], 1)
                if self.show_normals or self.debug_idx in (2,3):
                    self._draw_normal_arrow(fi, rot_verts)
                if self.show_face_ids or self.debug_idx == 3:
                    cx_ = sum(p[0] for p in pts)//len(pts)
                    cy_ = sum(p[1] for p in pts)//len(pts)
                    lbl = self.font_sm.render(str(fi), True, (220,220,80))
                    self.screen.blit(lbl, (cx_-lbl.get_width()//2,
                                           cy_-lbl.get_height()//2))

            # selected overlays on top
            if self.mode in ('FACE', 'VIEW'):
                self._draw_selected_face(self.sel_face, rot_verts)
            if self.mode == 'VERT' or self.show_vert_ids:
                self._draw_all_verts(rot_verts)
            if self.mode == 'EDGE':
                self._draw_all_edges(rot_verts)
                self._draw_selected_face(self.sel_face, rot_verts)

            # face normals always shown for selected face
            if self.mode in ('FACE', 'EDGE'):
                self._draw_normal_arrow(self.sel_face, rot_verts)

            self._draw_hud()
            pygame.display.flip()

        pygame.quit()


# ──────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Redshift Serpens Mesh Editor')
    parser.add_argument('--assets', default='assets',
                        help='Path to assets directory containing OBJ files')
    parser.add_argument('--file', default=None,
                        help='Load a specific OBJ file directly')
    parser.add_argument('--deadzone', type=float, default=0.20,
                        help='Controller stick deadzone (default 0.20)')
    args = parser.parse_args()

    editor = MeshEditor(assets_dir=args.assets)

    if args.file:
        editor._load_file(args.file)

    editor.run()