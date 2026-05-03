import pygame
import sys
import math
import os

# Ensure src is in the path so we can import from it when running standalone
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.camera import Camera
from src.renderer import RenderPipeline
from src.controller import DS4Input
from src.math_engine import (
    quat_identity, rotate_pitch, rotate_yaw, rotate_roll,
    get_forward_from_quat, get_basis_from_quat
)

# ─────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────
HOME_POS   = [0.0, 0.0, -200.0]
HOME_YAW   = 0.0
HOME_PITCH = 0.0

ORTHO_VIEWS = {
    # name : (yaw, pitch)
    "FRONT"  : (0.0,           0.0),
    "BACK"   : (math.pi,       0.0),
    "LEFT"   : (-math.pi / 2,  0.0),
    "RIGHT"  : ( math.pi / 2,  0.0),
    "TOP"    : (0.0,           math.pi / 2 - 0.01),
    "BOTTOM" : (0.0,          -math.pi / 2 + 0.01),
}

AXIS_COLORS = {
    None: (180, 180, 180),
    'X':  (255,  80,  80),
    'Y':  ( 80, 255,  80),
    'Z':  ( 80, 160, 255),
}


# ─────────────────────────────────────────────────────────────
#  MeshEditor
# ─────────────────────────────────────────────────────────────
class MeshEditor:
    def __init__(self):
        pygame.init()
        self.W, self.H = 1280, 760
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("3D Mesh Editor")
        self.clock  = pygame.time.Clock()
        self.font   = pygame.font.SysFont("Courier New", 14)
        self.font_s = pygame.font.SysFont("Courier New", 11)

        self.camera   = Camera(self.W, self.H)
        self.renderer = RenderPipeline(self.camera)

        self.handler = DS4Input()
        self.handler.init()

        # ── Camera state ──────────────────────────────────────
        self.cam_pos   = list(HOME_POS)
        self.cam_yaw   = HOME_YAW
        self.cam_pitch = HOME_PITCH
        self.cam_quat  = quat_identity()
        self.cam_speed = 500.0

        # ── Editor state ──────────────────────────────────────
        self.edit_mode   = "CREATE"   # "CREATE" | "SELECT"
        self.grid_size   = 1000
        self.snap        = 10
        self.cursor_pos  = [0.0, 0.0, 0.0]

        self.show_grid_xz  = True
        self.show_grid_xy  = False
        self.debug_winding = True
        self.show_vert_ids = True

        # Axis lock: None | 'X' | 'Y' | 'Z'
        self.axis_lock = None

        # Box-select state
        self.box_select_start  = None   # (cursor snapshot) world pos tuple
        self.box_select_active = False

        # Snap-to-vert highlight
        self.snap_target_vid = None

        # Face selection & extrude state
        self.selected_face_id  = None   # index into self.faces
        self.extrude_active    = False  # currently in extrude drag mode
        self.extrude_depth     = 0      # accumulated snap steps
        self.extrude_normal    = None   # (nx, ny, nz) unit normal of source face
        self.extrude_orig_vids = []     # vert ids of source face before extrude

        self.verts        = {}
        self.faces        = []
        self.next_v_id    = 0
        self.selected_verts = []

        self.current_color = (255, 255, 255)
        self.colors = [
            (255, 255, 255), (255,  80,  80), ( 80, 255,  80),
            ( 80, 160, 255), (255, 255,  80), ( 80, 255, 255),
            (255,  80, 255), (160, 160, 160),
        ]
        self.color_idx = 0

        # Status toast
        self._toast      = ""
        self._toast_timer = 0.0

        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        self.mouse_captured = True
        self.running = True

    # ─────────────────────────────────────────────────────────
    #  Toast helper
    # ─────────────────────────────────────────────────────────
    def _show_toast(self, msg, duration=1.5):
        self._toast       = msg
        self._toast_timer = duration

    # ─────────────────────────────────────────────────────────
    #  Camera helpers
    # ─────────────────────────────────────────────────────────
    def _rebuild_cam_quat(self):
        q = quat_identity()
        q = rotate_yaw(q, self.cam_yaw)
        self.cam_quat = rotate_pitch(q, self.cam_pitch)

    def _go_home(self):
        self.cam_pos   = list(HOME_POS)
        self.cam_yaw   = HOME_YAW
        self.cam_pitch = HOME_PITCH
        self._rebuild_cam_quat()
        self._show_toast("Camera → Home")

    def _set_ortho_view(self, name):
        yaw, pitch     = ORTHO_VIEWS[name]
        self.cam_yaw   = yaw
        self.cam_pitch = pitch
        self._rebuild_cam_quat()
        self._show_toast(f"View → {name}")

    def _frame_selection(self):
        """Move camera to look at centre of selected verts."""
        if not self.selected_verts:
            if self.verts:
                pts = list(self.verts.values())
            else:
                return
        else:
            pts = [self.verts[v] for v in self.selected_verts if v in self.verts]
        if not pts:
            return
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        cz = sum(p[2] for p in pts) / len(pts)
        # Step back along -forward
        fwd, _, _ = get_basis_from_quat(self.cam_quat)
        dist = 150.0
        self.cam_pos = [cx - fwd[0]*dist, cy - fwd[1]*dist, cz - fwd[2]*dist]
        self._show_toast("Framed selection")

    # ─────────────────────────────────────────────────────────
    #  Snap-to-vertex helper
    # ─────────────────────────────────────────────────────────
    def _update_snap_target(self):
        """Find vert closest to cursor; highlight it if within 1.5× snap."""
        best, best_d = None, float('inf')
        for vid, pos in self.verts.items():
            d = math.dist(pos, self.cursor_pos)
            if d < best_d:
                best, best_d = vid, d
        threshold = self.snap * 1.5
        self.snap_target_vid = best if (best and best_d <= threshold) else None

    def _apply_snap_to_vert(self):
        if self.snap_target_vid and self.snap_target_vid in self.verts:
            p = self.verts[self.snap_target_vid]
            self.cursor_pos = list(p)

    # ─────────────────────────────────────────────────────────
    #  Axis-locked cursor movement
    # ─────────────────────────────────────────────────────────
    def _move_cursor(self, dx, dy, dz):
        if self.axis_lock == 'X':
            self.cursor_pos[0] += dx
        elif self.axis_lock == 'Y':
            self.cursor_pos[1] += dy
        elif self.axis_lock == 'Z':
            self.cursor_pos[2] += dz
        else:
            self.cursor_pos[0] += dx
            self.cursor_pos[1] += dy
            self.cursor_pos[2] += dz

    # ─────────────────────────────────────────────────────────
    #  Input
    # ─────────────────────────────────────────────────────────
    def process_input(self, dt):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                k = event.key

                if k == pygame.K_ESCAPE:
                    self.mouse_captured = not self.mouse_captured
                    pygame.mouse.set_visible(not self.mouse_captured)
                    pygame.event.set_grab(self.mouse_captured)

                if self.mouse_captured:
                    # ── Place / Select ──────────────────────
                    if k == pygame.K_SPACE:
                        if self.extrude_active:
                            self._extrude_confirm()
                        else:
                            self._apply_snap_to_vert()
                            if self.edit_mode == "CREATE":
                                self._add_vertex_at_cursor()
                            else:
                                self._select_nearest_vertex()

                    # ── Extrude depth nudge ─────────────────
                    elif k == pygame.K_UP and self.extrude_active:
                        self._extrude_nudge(+1)
                    elif k == pygame.K_DOWN and self.extrude_active:
                        self._extrude_nudge(-1)

                    # ── Mode ────────────────────────────────
                    elif k == pygame.K_TAB:
                        self.edit_mode = "SELECT" if self.edit_mode == "CREATE" else "CREATE"

                    # ── Mesh ops ────────────────────────────
                    elif k == pygame.K_f:
                        if self.selected_verts:
                            self._create_face()
                        else:
                            self._frame_selection()
                    elif k == pygame.K_g:
                        if self.extrude_active:
                            self._extrude_confirm()
                        else:
                            self._select_nearest_face()
                    elif k == pygame.K_e:
                        if self.selected_face_id is not None:
                            self._extrude_begin()
                        else:
                            self._show_toast("Select a face first (G)")
                    elif k == pygame.K_c:
                        if self.extrude_active:
                            self._extrude_cancel()
                        else:
                            self._cycle_color()
                    elif k == pygame.K_p:
                        self._export_mesh()
                    elif k == pygame.K_BACKSPACE:
                        self._delete_last_vertex()
                    elif k == pygame.K_r:
                        self.selected_verts.clear()
                        self.selected_face_id = None
                    elif k == pygame.K_a:
                        self._select_all_toggle()
                    elif k == pygame.K_m:
                        self._merge_duplicate_verts()

                    # ── Grid / Display ──────────────────────
                    elif k == pygame.K_x:
                        self.show_grid_xz = not self.show_grid_xz
                    elif k == pygame.K_y:
                        self.show_grid_xy = not self.show_grid_xy
                    elif k == pygame.K_n:
                        self.debug_winding = not self.debug_winding
                    elif k == pygame.K_i:
                        self.show_vert_ids = not self.show_vert_ids

                    # ── Camera / View ───────────────────────
                    elif k == pygame.K_HOME:
                        self._go_home()
                    elif k == pygame.K_F1:
                        self._set_ortho_view("FRONT")
                    elif k == pygame.K_F2:
                        self._set_ortho_view("BACK")
                    elif k == pygame.K_F3:
                        self._set_ortho_view("LEFT")
                    elif k == pygame.K_F4:
                        self._set_ortho_view("RIGHT")
                    elif k == pygame.K_F5:
                        self._set_ortho_view("TOP")
                    elif k == pygame.K_F6:
                        self._set_ortho_view("BOTTOM")

                    # ── Axis lock ───────────────────────────
                    elif k == pygame.K_1:
                        self.axis_lock = None if self.axis_lock == 'X' else 'X'
                        self._show_toast(f"Axis lock: {self.axis_lock or 'OFF'}")
                    elif k == pygame.K_2:
                        self.axis_lock = None if self.axis_lock == 'Y' else 'Y'
                        self._show_toast(f"Axis lock: {self.axis_lock or 'OFF'}")
                    elif k == pygame.K_3:
                        self.axis_lock = None if self.axis_lock == 'Z' else 'Z'
                        self._show_toast(f"Axis lock: {self.axis_lock or 'OFF'}")

                    # ── Box select ──────────────────────────
                    elif k == pygame.K_b:
                        if not self.box_select_active:
                            self.box_select_start  = tuple(self.cursor_pos)
                            self.box_select_active = True
                            self._show_toast("Box select: move cursor, press B again")
                        else:
                            self._finish_box_select()

            self.handler.process_event(event)

        # ── Mouse look ────────────────────────────────────────
        if self.mouse_captured:
            mx, my = pygame.mouse.get_rel()
            self.cam_yaw   += -mx * 0.002
            self.cam_pitch += -my * 0.002

        # ── Controller look ───────────────────────────────────
        rx, ry = self.handler.stick_right()
        if abs(rx) > 0.1 or abs(ry) > 0.1:
            self.cam_yaw   += -rx * dt * 2.0
            self.cam_pitch +=  ry * dt * 2.0

        # Clamp pitch
        limit = math.pi / 2.0 - 0.01
        self.cam_pitch = max(-limit, min(limit, self.cam_pitch))
        self._rebuild_cam_quat()

        # ── Controller buttons ────────────────────────────────
        if self.handler.just_pressed('X'):
            self._apply_snap_to_vert()
            if self.edit_mode == "CREATE":
                self._add_vertex_at_cursor()
            else:
                self._select_nearest_vertex()

        if self.handler.just_pressed('L3'):
            self.edit_mode = "SELECT" if self.edit_mode == "CREATE" else "CREATE"
        if self.handler.just_pressed('Square'):
            self._create_face()
        if self.handler.just_pressed('Triangle'):
            self._cycle_color()
        if self.handler.just_pressed('Circle'):
            self.selected_verts.clear()
        if self.handler.just_pressed('Options'):
            self._export_mesh()
        if self.handler.just_pressed('PS'):
            self._go_home()
        if self.handler.just_pressed('R3'):
            self._frame_selection()

        self.handler.update()

        keys = pygame.key.get_pressed()
        fwd, right, up = get_basis_from_quat(self.cam_quat)

        # ── Camera movement ───────────────────────────────────
        move_x = move_y = move_z = 0.0
        if self.mouse_captured:
            if keys[pygame.K_w]: move_z += 1
            if keys[pygame.K_s]: move_z -= 1
            if keys[pygame.K_d]: move_x += 1
            if keys[pygame.K_a]: move_x -= 1
            if keys[pygame.K_e]: move_y += 1
            if keys[pygame.K_q]: move_y -= 1

        lx, ly = self.handler.stick_left()
        move_x += lx
        move_z -= ly
        move_y += self.handler.trigger_right() - self.handler.trigger_left()

        speed = self.cam_speed * (3.0 if keys[pygame.K_LSHIFT] else 1.0)
        self.cam_pos[0] += (move_x*right[0] + move_y*up[0] + move_z*fwd[0]) * speed * dt
        self.cam_pos[1] += (move_x*right[1] + move_y*up[1] + move_z*fwd[1]) * speed * dt
        self.cam_pos[2] += (move_x*right[2] + move_y*up[2] + move_z*fwd[2]) * speed * dt

        # ── Cursor movement ───────────────────────────────────
        s = self.snap
        if self.extrude_active:
            # Arrow up/down drives extrude depth instead of cursor — event driven via keydown
            if self.mouse_captured:
                pass  # handled in KEYDOWN block above
        else:
            if self.mouse_captured:
                if keys[pygame.K_UP]:       self._move_cursor(0,  0,  s)
                if keys[pygame.K_DOWN]:     self._move_cursor(0,  0, -s)
                if keys[pygame.K_RIGHT]:    self._move_cursor(s,  0,  0)
                if keys[pygame.K_LEFT]:     self._move_cursor(-s, 0,  0)
                if keys[pygame.K_PAGEUP]:   self._move_cursor(0,  s,  0)
                if keys[pygame.K_PAGEDOWN]: self._move_cursor(0, -s,  0)

        dpad = self.handler.dpad()
        if dpad[0] ==  1: self._move_cursor( s, 0, 0)
        if dpad[0] == -1: self._move_cursor(-s, 0, 0)
        if dpad[1] ==  1: self._move_cursor(0, 0,  s)
        if dpad[1] == -1: self._move_cursor(0, 0, -s)
        if self.handler.held('R1'): self._move_cursor(0,  s, 0)
        if self.handler.held('L1'): self._move_cursor(0, -s, 0)

        # Update snap-to-vert highlight every frame
        self._update_snap_target()

    # ─────────────────────────────────────────────────────────
    #  Vertex / face ops
    # ─────────────────────────────────────────────────────────
    def _add_vertex_at_cursor(self):
        pos = tuple(self.cursor_pos)
        for vid, vpos in self.verts.items():
            if vpos == pos:
                if vid not in self.selected_verts:
                    self.selected_verts.append(vid)
                    self._show_toast(f"Reused {vid}")
                return
        vid = f"v{self.next_v_id}"
        self.verts[vid] = pos
        self.selected_verts.append(vid)
        self.next_v_id += 1
        self._show_toast(f"Added {vid}")

    def _select_nearest_vertex(self):
        best, best_d = None, float('inf')
        for vid, pos in self.verts.items():
            d = math.dist(pos, self.cursor_pos)
            if d < best_d:
                best, best_d = vid, d
        if best and best_d <= self.snap * 5:
            if best in self.selected_verts:
                self.selected_verts.remove(best)
                self._show_toast(f"Deselected {best}")
            else:
                self.selected_verts.append(best)
                self._show_toast(f"Selected {best}")

    def _select_all_toggle(self):
        if len(self.selected_verts) == len(self.verts):
            self.selected_verts.clear()
            self._show_toast("Deselected all")
        else:
            self.selected_verts = list(self.verts.keys())
            self._show_toast(f"Selected all ({len(self.selected_verts)})")

    def _finish_box_select(self):
        if not self.box_select_start:
            return
        x0, y0, z0 = self.box_select_start
        x1, y1, z1 = self.cursor_pos
        mn = (min(x0, x1), min(y0, y1), min(z0, z1))
        mx = (max(x0, x1), max(y0, y1), max(z0, z1))
        count = 0
        for vid, pos in self.verts.items():
            if (mn[0] <= pos[0] <= mx[0] and
                mn[1] <= pos[1] <= mx[1] and
                mn[2] <= pos[2] <= mx[2]):
                if vid not in self.selected_verts:
                    self.selected_verts.append(vid)
                    count += 1
        self.box_select_start  = None
        self.box_select_active = False
        self._show_toast(f"Box selected {count} verts")

    def _delete_last_vertex(self):
        if self.next_v_id > 0:
            vid = f"v{self.next_v_id - 1}"
            if vid in self.verts:
                del self.verts[vid]
                # Remove from any faces that reference it
                self.faces = [f for f in self.faces if vid not in f['v']]
            if vid in self.selected_verts:
                self.selected_verts.remove(vid)
            self.next_v_id -= 1
            self._show_toast(f"Deleted {vid}")

    def _create_face(self):
        if len(self.selected_verts) < 3:
            self._show_toast("Need ≥ 3 verts for a face")
            return
        # Degenerate check: all same position?
        pts = [self.verts[v] for v in self.selected_verts if v in self.verts]
        if len(set(pts)) < 3:
            self._show_toast("Degenerate face — skipped")
            return
        face_id = len(self.faces)
        self.faces.append({
            'id':    face_id,
            'v':     list(self.selected_verts),
            'color': self.current_color,
        })
        self.selected_verts.clear()
        self._show_toast(f"Created face f{face_id}")

    def _cycle_color(self):
        self.color_idx     = (self.color_idx + 1) % len(self.colors)
        self.current_color = self.colors[self.color_idx]

    def _merge_duplicate_verts(self):
        """Merge verts that share the same world position."""
        pos_to_canonical = {}
        remap = {}
        new_verts = {}
        for vid, pos in self.verts.items():
            key = pos
            if key in pos_to_canonical:
                remap[vid] = pos_to_canonical[key]
            else:
                pos_to_canonical[key] = vid
                new_verts[vid]        = pos
        # Remap faces
        merged = 0
        for f in self.faces:
            new_v = []
            for v in f['v']:
                canonical = remap.get(v, v)
                if canonical not in new_v:
                    new_v.append(canonical)
            f['v']  = new_v
            merged += len(f['v']) - len(new_v)  # not quite right but gives idea
        self.verts = new_verts
        removed = len(remap)
        self._show_toast(f"Merged {removed} duplicate verts")

    # ─────────────────────────────────────────────────────────
    #  Face selection
    # ─────────────────────────────────────────────────────────
    def _select_nearest_face(self):
        """Select the face whose centre is closest to the cursor."""
        best_idx, best_d = None, float('inf')
        for i, f in enumerate(self.faces):
            pts = [self.verts[v] for v in f['v'] if v in self.verts]
            if not pts:
                continue
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            cz = sum(p[2] for p in pts) / len(pts)
            d  = math.dist((cx, cy, cz), self.cursor_pos)
            if d < best_d:
                best_d, best_idx = d, i
        if best_idx is not None:
            self.selected_face_id = best_idx
            f = self.faces[best_idx]
            self._show_toast(f"Selected face f{f['id']}")
        else:
            self._show_toast("No faces to select")

    # ─────────────────────────────────────────────────────────
    #  Extrude
    # ─────────────────────────────────────────────────────────
    def _face_normal(self, face):
        """Return unit normal for a face dict."""
        pts = [self.verts[v] for v in face['v'] if v in self.verts]
        if len(pts) < 3:
            return (0.0, 1.0, 0.0)
        p0, p1, p2 = pts[0], pts[1], pts[2]
        ux, uy, uz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
        vx, vy, vz = p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2]
        nx = uy*vz - uz*vy
        ny = uz*vx - ux*vz
        nz = ux*vy - uy*vx
        nl = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
        return (nx/nl, ny/nl, nz/nl)

    def _extrude_begin(self):
        if self.selected_face_id is None or self.selected_face_id >= len(self.faces):
            return
        src = self.faces[self.selected_face_id]
        self.extrude_normal    = self._face_normal(src)
        self.extrude_orig_vids = list(src['v'])
        self.extrude_depth     = 0
        self.extrude_active    = True

        # Duplicate the source face verts into new positions (depth=0 initially)
        self._extrude_new_vids = []
        for vid in self.extrude_orig_vids:
            orig = self.verts[vid]
            new_vid = f"v{self.next_v_id}"
            self.next_v_id += 1
            self.verts[new_vid] = orig   # starts coincident — nudge will move them
            self._extrude_new_vids.append(new_vid)

        self._show_toast("Extrude: UP/DOWN to set depth, SPACE to confirm, C to cancel")

    def _extrude_nudge(self, direction):
        """Called each frame arrow is held — moves new cap verts one snap step."""
        if not self.extrude_active:
            return
        self.extrude_depth += direction
        nx, ny, nz = self.extrude_normal
        total_offset = self.extrude_depth * self.snap
        # Reposition new verts relative to originals
        for orig_vid, new_vid in zip(self.extrude_orig_vids, self._extrude_new_vids):
            orig = self.verts[orig_vid]
            self.verts[new_vid] = (
                orig[0] + nx * total_offset,
                orig[1] + ny * total_offset,
                orig[2] + nz * total_offset,
            )

    def _extrude_confirm(self):
        """Commit the extrude: build side faces + new cap, replace source face."""
        if not self.extrude_active:
            return

        n       = len(self.extrude_orig_vids)
        orig    = self.extrude_orig_vids
        new     = self._extrude_new_vids
        color   = self.faces[self.selected_face_id]['color']

        # Side faces — one quad per edge of original face
        for i in range(n):
            a  = orig[i]
            b  = orig[(i + 1) % n]
            c  = new[(i + 1) % n]
            d  = new[i]
            fid = len(self.faces)
            self.faces.append({'id': fid, 'v': [a, b, c, d], 'color': color})

        # New cap face (the extruded top) — same winding as original
        cap_id = len(self.faces)
        self.faces.append({'id': cap_id, 'v': list(new), 'color': color})

        # Remove the original source face (it's now interior / sealed)
        self.faces.pop(self.selected_face_id)
        # Re-index all face ids
        for i, f in enumerate(self.faces):
            f['id'] = i

        self.selected_face_id  = None
        self.extrude_active    = False
        self.extrude_orig_vids = []
        self._extrude_new_vids = []
        self._show_toast(f"Extruded — {n} side faces + cap added")

    def _extrude_cancel(self):
        """Discard the in-progress extrude, delete the duplicate verts."""
        if not self.extrude_active:
            self._cycle_color()   # C with no extrude active still cycles color
            return
        for vid in self._extrude_new_vids:
            if vid in self.verts:
                del self.verts[vid]
        self.extrude_active    = False
        self.extrude_orig_vids = []
        self._extrude_new_vids = []
        self._show_toast("Extrude cancelled")

    # ─────────────────────────────────────────────────────────
    #  Export
    # ─────────────────────────────────────────────────────────
    def _export_mesh(self):
        lines = ["======== MESH EXPORT ========"]
        lines.append("verts = {")
        for vid, pos in self.verts.items():
            lines.append(f"    '{vid}': {pos},")
        lines.append("}")
        lines.append("faces = {")
        for i, f in enumerate(self.faces):
            lines.append(f"    'f{i}': {{'v': {f['v']}, 'color': {f['color']}}},")
        lines.append("}")

        # Also write OBJ
        obj_lines = ["# Exported mesh"]
        for vid, pos in self.verts.items():
            obj_lines.append(f"v {pos[0]} {pos[1]} {pos[2]}")
        vert_keys = list(self.verts.keys())
        for f in self.faces:
            indices = " ".join(str(vert_keys.index(v) + 1) for v in f['v'] if v in vert_keys)
            obj_lines.append(f"f {indices}")

        obj_path = os.path.join(os.path.dirname(__file__), "mesh_export.obj")
        try:
            with open(obj_path, "w") as fh:
                fh.write("\n".join(obj_lines))
            lines.append(f"\nOBJ written → {obj_path}")
        except Exception as e:
            lines.append(f"\nOBJ write failed: {e}")

        output = "\n".join(lines)
        print(output)
        lines.append("=============================")
        self._show_toast("Exported — see console + .obj")

    # ─────────────────────────────────────────────────────────
    #  Draw helpers
    # ─────────────────────────────────────────────────────────
    def draw_grid(self):
        col   = (40, 40, 40)
        ax_x  = (150, 50, 50)
        ax_y  = (50, 150, 50)
        ax_z  = (50, 50, 150)
        s     = self.grid_size
        step  = self.snap * 10

        if self.show_grid_xz:
            for i in range(-s, s + step, step):
                self.renderer.submit_line((i, 0, -s), (i, 0,  s), ax_z if i == 0 else col)
                self.renderer.submit_line((-s, 0, i), ( s, 0,  i), ax_x if i == 0 else col)

        if self.show_grid_xy:
            for i in range(-s, s + step, step):
                self.renderer.submit_line((i, -s, 0), (i,  s, 0), ax_y if i == 0 else col)
                self.renderer.submit_line((-s, i, 0), ( s,  i, 0), ax_x if i == 0 else col)

    def draw_box_select_preview(self):
        if not self.box_select_active or not self.box_select_start:
            return
        x0, y0, z0 = self.box_select_start
        x1, y1, z1 = self.cursor_pos
        # Draw bounding box edges
        col = (255, 200, 50)
        corners = [
            (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
        ]
        edges = [
            (0,1),(1,2),(2,3),(3,0),  # bottom face
            (4,5),(5,6),(6,7),(7,4),  # top face
            (0,4),(1,5),(2,6),(3,7),  # vertical edges
        ]
        for a, b in edges:
            self.renderer.submit_line(corners[a], corners[b], col, 1)

    def draw_cursor(self):
        cx, cy, cz = self.cursor_pos
        lock_col   = AXIS_COLORS[self.axis_lock]

        if self.edit_mode == "CREATE":
            s = 5
            # Colour each arm by axis lock status
            xc = lock_col if self.axis_lock == 'X' else (255,  80,  80)
            yc = lock_col if self.axis_lock == 'Y' else ( 80, 255,  80)
            zc = lock_col if self.axis_lock == 'Z' else ( 80, 160, 255)
            self.renderer.submit_line((cx-s, cy, cz), (cx+s, cy, cz), xc, 2)
            self.renderer.submit_line((cx, cy-s, cz), (cx, cy+s, cz), yc, 2)
            self.renderer.submit_line((cx, cy, cz-s), (cx, cy, cz+s), zc, 2)
        else:
            s   = self.snap * 2
            col = lock_col if self.axis_lock else (255, 255, 0)
            self.renderer.submit_line((cx-s, cy-s, cz), (cx+s, cy-s, cz), col, 2)
            self.renderer.submit_line((cx-s, cy+s, cz), (cx+s, cy+s, cz), col, 2)
            self.renderer.submit_line((cx, cy-s, cz),   (cx, cy+s, cz),   col, 2)
            self.renderer.submit_line((cx-s, cy, cz),   (cx+s, cy, cz),   col, 2)
            self.renderer.submit_line((cx, cy, cz-s),   (cx, cy, cz+s),   col, 2)

        # Snap-to-vert ring
        if self.snap_target_vid and self.snap_target_vid in self.verts:
            sp    = self.verts[self.snap_target_vid]
            r     = self.snap
            ring_col = (255, 200, 50)
            self.renderer.submit_line((sp[0]-r, sp[1], sp[2]-r),
                                      (sp[0]+r, sp[1], sp[2]-r), ring_col, 2)
            self.renderer.submit_line((sp[0]+r, sp[1], sp[2]-r),
                                      (sp[0]+r, sp[1], sp[2]+r), ring_col, 2)
            self.renderer.submit_line((sp[0]+r, sp[1], sp[2]+r),
                                      (sp[0]-r, sp[1], sp[2]+r), ring_col, 2)
            self.renderer.submit_line((sp[0]-r, sp[1], sp[2]+r),
                                      (sp[0]-r, sp[1], sp[2]-r), ring_col, 2)

    def draw_mesh(self):
        # Faces
        for i, f in enumerate(self.faces):
            pts = [self.verts[vid] for vid in f['v'] if vid in self.verts]
            if len(pts) < 3:
                continue

            # Highlight selected face
            if i == self.selected_face_id and not self.extrude_active:
                # Draw outline in bright cyan
                for j in range(len(pts)):
                    self.renderer.submit_line(pts[j], pts[(j+1) % len(pts)], (0, 255, 220), 2)
                self.renderer.submit_polygon(pts, (
                    min(f['color'][0] + 60, 255),
                    min(f['color'][1] + 60, 255),
                    min(f['color'][2] + 60, 255),
                ))
            else:
                self.renderer.submit_polygon(pts, f['color'])

            if self.debug_winding:
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                cz = sum(p[2] for p in pts) / len(pts)
                p0, p1, p2 = pts[0], pts[1], pts[2]
                ux, uy, uz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
                vx, vy, vz = p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2]
                nx = uy*vz - uz*vy
                ny = uz*vx - ux*vz
                nz = ux*vy - uy*vx
                nl = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
                nx, ny, nz = nx/nl*15, ny/nl*15, nz/nl*15
                self.renderer.submit_line((cx, cy, cz),
                                          (cx+nx, cy+ny, cz+nz), (255, 255, 0), 2)

        # Extrude preview — draw side quads as wireframe while dragging
        if self.extrude_active and hasattr(self, '_extrude_new_vids'):
            orig = self.extrude_orig_vids
            new  = self._extrude_new_vids
            n    = len(orig)
            col  = (0, 255, 180)
            for i in range(n):
                op = self.verts.get(orig[i])
                np_ = self.verts.get(new[i])
                op2 = self.verts.get(orig[(i+1) % n])
                np2 = self.verts.get(new[(i+1) % n])
                if op and np_:
                    self.renderer.submit_line(op, np_, col, 1)
                if np_ and np2:
                    self.renderer.submit_line(np_, np2, col, 2)
            # Cap outline
            for i in range(n):
                np_ = self.verts.get(new[i])
                np2 = self.verts.get(new[(i+1) % n])
                if np_ and np2:
                    self.renderer.submit_line(np_, np2, (0, 255, 255), 2)
            # Depth readout
            depth_px = self.extrude_depth * self.snap
            self._show_toast(f"Extrude depth: {depth_px}  (UP/DOWN, SPACE=confirm, C=cancel)")

        # Verts
        for vid, pos in self.verts.items():
            if vid == self.snap_target_vid:
                col = (255, 200, 50)
            elif vid in self.selected_verts:
                col = (255, 100, 100)
            else:
                col = (255, 255, 255)
            self.renderer.submit_sprite(pos[0], pos[1], pos[2], col, 3)

        # In-progress face preview edges
        if len(self.selected_verts) > 1:
            for i in range(len(self.selected_verts) - 1):
                p1 = self.verts.get(self.selected_verts[i])
                p2 = self.verts.get(self.selected_verts[i+1])
                if p1 and p2:
                    self.renderer.submit_line(p1, p2, (255, 100, 100), 2)

    def draw_vert_labels(self):
        """Screen-space vert ID labels — drawn after renderer.render() so they're on top."""
        if not self.show_vert_ids:
            return
        for vid, pos in self.verts.items():
            cam_pos = self.camera.world_to_camera(*pos)
            proj = self.camera.project(*cam_pos)
            if proj is None:
                continue
            sx, sy, _ = proj
            col = (255, 200, 50) if vid == self.snap_target_vid else \
                  (255, 130, 130) if vid in self.selected_verts else \
                  (140, 140, 140)
            lbl = self.font_s.render(vid, True, col)
            self.screen.blit(lbl, (int(sx) + 5, int(sy) - 5))

        # Face index labels at face centres
        for f in self.faces:
            pts = [self.verts[v] for v in f['v'] if v in self.verts]
            if not pts:
                continue
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            cz = sum(p[2] for p in pts) / len(pts)
            cam_pos = self.camera.world_to_camera(cx, cy, cz)
            proj = self.camera.project(*cam_pos)
            if proj is None:
                continue
            sx, sy, _ = proj
            lbl = self.font_s.render(f"f{f['id']}", True, (180, 180, 80))
            self.screen.blit(lbl, (int(sx) + 4, int(sy) + 4))

    def draw_ui(self):
        y = 10

        # ── Left panel ────────────────────────────────────────
        lock_str  = f"[{self.axis_lock}]" if self.axis_lock else "[ ]"
        face_str  = f"f{self.faces[self.selected_face_id]['id']}" if self.selected_face_id is not None and self.selected_face_id < len(self.faces) else "—"
        extr_str  = f"  EXTRUDING depth={self.extrude_depth * self.snap}" if self.extrude_active else ""
        texts = [
            f"FPS: {int(self.clock.get_fps())}",
            f"Mode: {self.edit_mode}  (TAB/L3)",
            f"Axis lock: {lock_str}  (1=X 2=Y 3=Z)",
            f"Camera: {int(self.cam_pos[0])}, {int(self.cam_pos[1])}, {int(self.cam_pos[2])}",
            f"Cursor: {int(self.cursor_pos[0])}, {int(self.cursor_pos[1])}, {int(self.cursor_pos[2])}",
            f"Verts: {len(self.verts)}  Faces: {len(self.faces)}",
            f"Selected verts: {len(self.selected_verts)}  {'BOX-SELECT' if self.box_select_active else ''}",
            f"Selected face: {face_str}{extr_str}",
            f"Snap target: {self.snap_target_vid or '—'}",
            f"Color: RGB{self.current_color}",
            "",
            "─── Controls ─────────────────",
            "ESC        Toggle mouse grab",
            "WASD/QE    Fly camera",
            "SHIFT      Speed boost",
            "Arrows/PgUpDn  Move cursor",
            "1/2/3      Lock axis X/Y/Z",
            "SPACE/(X)  Place/Select vert",
            "TAB/(L3)   Toggle mode",
            "A          Select all toggle",
            "B          Box select (start/end)",
            "F          Create face / frame sel",
            "G          Select nearest face",
            "E          Extrude selected face",
            "  UP/DOWN  Extrude depth",
            "  SPACE    Confirm extrude",
            "  C        Cancel extrude",
            "C/(Tri)    Cycle color",
            "R/(Circle) Clear selection",
            "M          Merge duplicate verts",
            "Backspace  Delete last vert",
            "P/(Opts)   Export mesh + OBJ",
            "HOME/(PS)  Camera home",
            "R3         Frame selection",
            "F1-F6      Ortho views",
            "I          Toggle vert ID labels",
            "N          Toggle normals",
            "X/Y        Toggle grids",
        ]

        for t in texts:
            col = (255, 255, 80)  if "Mode:" in t else \
                  (255, 130, 80)  if "Axis" in t and self.axis_lock else \
                  (255, 200, 80)  if "BOX-SELECT" in t else \
                  (0,   255, 180) if "EXTRUDING" in t else \
                  (0,   220, 255) if t.strip().startswith("E ") or "Extrude" in t else \
                  (200, 200, 200)
            img = self.font.render(t, True, col)
            self.screen.blit(img, (10, y))
            y += 18

        # Color swatch
        pygame.draw.rect(self.screen, self.current_color, (10, y + 4, 30, 18))
        pygame.draw.rect(self.screen, (255,255,255),       (10, y + 4, 30, 18), 1)

        # ── Face buffer strip (bottom) ────────────────────────
        if self.selected_verts:
            buf = "Face buffer: " + " → ".join(self.selected_verts)
            img = self.font.render(buf, True, (255, 130, 130))
            self.screen.blit(img, (10, self.H - 24))

        # ── Toast ─────────────────────────────────────────────
        if self._toast_timer > 0:
            alpha = min(255, int(self._toast_timer * 300))
            surf  = self.font.render(f"  {self._toast}  ", True, (20, 20, 20), (255, 220, 80))
            surf.set_alpha(alpha)
            tw    = surf.get_width()
            self.screen.blit(surf, (self.W // 2 - tw // 2, self.H - 50))

        # ── Ortho view label (top centre) ─────────────────────
        for name, (y_, p) in ORTHO_VIEWS.items():
            if (abs(self.cam_yaw % (2*math.pi) - y_ % (2*math.pi)) < 0.05 and
                    abs(self.cam_pitch - p) < 0.05):
                lbl = self.font.render(f"[ {name} ]", True, (100, 200, 255))
                self.screen.blit(lbl, (self.W//2 - lbl.get_width()//2, 10))
                break

    # ─────────────────────────────────────────────────────────
    #  Main loop
    # ─────────────────────────────────────────────────────────
    def main(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0

            self._toast_timer = max(0.0, self._toast_timer - dt)

            self.process_input(dt)

            self.screen.fill((20, 20, 30))
            self.camera.update(tuple(self.cam_pos), self.cam_quat)
            self.renderer.clear()

            self.draw_grid()
            self.draw_mesh()
            self.draw_box_select_preview()
            self.draw_cursor()

            self.renderer.render(self.screen)

            # 2-D overlay passes
            self.draw_vert_labels()
            self.draw_ui()

            pygame.display.flip()

        pygame.quit()


if __name__ == '__main__':
    MeshEditor().main()