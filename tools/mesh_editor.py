import pygame
import sys
import math
import os

# Ensure src is in the path so we can import from it when running standalone
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.camera import Camera
from src.renderer import RenderPipeline
from src.controller import DS4Input
from src.math_engine import quat_identity, rotate_pitch, rotate_yaw, rotate_roll, get_forward_from_quat, get_basis_from_quat

class MeshEditor:
    def __init__(self):
        pygame.init()
        self.W, self.H = 1280, 760
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("3D Mesh Editor")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Courier New", 14)

        self.camera = Camera(self.W, self.H)
        self.renderer = RenderPipeline(self.camera)
        
        self.handler = DS4Input()
        self.handler.init()
        
        # Camera state
        self.cam_pos = [0.0, 0.0, -200.0]
        self.cam_quat = quat_identity()
        self.cam_speed = 500.0
        
        # Editor State
        self.grid_size = 1000
        self.snap = 10
        self.cursor_pos = [0.0, 0.0, 0.0]
        
        self.show_grid_xz = True
        self.show_grid_xy = False
        self.debug_winding = True
        
        self.verts = {}
        self.faces = []
        
        self.next_v_id = 0
        self.selected_verts = [] # List of v_ids
        
        self.current_color = (255, 255, 255)
        self.colors = [
            (255, 255, 255),
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0),
            (0, 255, 255),
            (255, 0, 255),
            (100, 100, 100)
        ]
        self.color_idx = 0
        
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        self.mouse_captured = True
        
        self.running = True

    def process_input(self, dt):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.mouse_captured = not self.mouse_captured
                    pygame.mouse.set_visible(not self.mouse_captured)
                    pygame.event.set_grab(self.mouse_captured)
                
                if self.mouse_captured:
                    if event.key == pygame.K_SPACE:
                        self._add_vertex_at_cursor()
                    elif event.key == pygame.K_f:
                        self._create_face()
                    elif event.key == pygame.K_c:
                        self._cycle_color()
                    elif event.key == pygame.K_x:
                        self.show_grid_xz = not self.show_grid_xz
                    elif event.key == pygame.K_y:
                        self.show_grid_xy = not self.show_grid_xy
                    elif event.key == pygame.K_n:
                        self.debug_winding = not self.debug_winding
                    elif event.key == pygame.K_p:
                        self._export_mesh()
                    elif event.key == pygame.K_BACKSPACE:
                        self._delete_last_vertex()
                    elif event.key == pygame.K_r:
                        self.selected_verts.clear()
            
            self.handler.process_event(event)

        # Mouse look
        if self.mouse_captured:
            mx, my = pygame.mouse.get_rel()
            yaw_delta = -mx * 0.002
            pitch_delta = -my * 0.002
            self.cam_quat = rotate_yaw(self.cam_quat, yaw_delta)
            self.cam_quat = rotate_pitch(self.cam_quat, pitch_delta)
        
        # Controller look
        rx, ry = self.handler.stick_right()
        if abs(rx) > 0.1 or abs(ry) > 0.1:
            self.cam_quat = rotate_yaw(self.cam_quat, -rx * dt * 2.0)
            self.cam_quat = rotate_pitch(self.cam_quat, ry * dt * 2.0)
            
        # Controller actions
        if self.handler.just_pressed('X'):
            self._add_vertex_at_cursor()
        if self.handler.just_pressed('Square'):
            self._create_face()
        if self.handler.just_pressed('Triangle'):
            self._cycle_color()
        if self.handler.just_pressed('Circle'):
            self.selected_verts.clear()
        if self.handler.just_pressed('Options'):
            self._export_mesh()
            
        self.handler.update()

        keys = pygame.key.get_pressed()
        
        # Move Camera
        fwd, right, up = get_basis_from_quat(self.cam_quat)
        
        move_x = move_y = move_z = 0.0
        
        # Keyboard movement
        if self.mouse_captured:
            if keys[pygame.K_w]: move_z += 1
            if keys[pygame.K_s]: move_z -= 1
            if keys[pygame.K_d]: move_x += 1
            if keys[pygame.K_a]: move_x -= 1
            if keys[pygame.K_e]: move_y += 1
            if keys[pygame.K_q]: move_y -= 1
            
            if keys[pygame.K_UP]: self.cursor_pos[2] += self.snap
            if keys[pygame.K_DOWN]: self.cursor_pos[2] -= self.snap
            if keys[pygame.K_RIGHT]: self.cursor_pos[0] += self.snap
            if keys[pygame.K_LEFT]: self.cursor_pos[0] -= self.snap
            if keys[pygame.K_PAGEUP]: self.cursor_pos[1] += self.snap
            if keys[pygame.K_PAGEDOWN]: self.cursor_pos[1] -= self.snap
        
        # Controller movement
        lx, ly = self.handler.stick_left()
        move_x += lx
        move_z -= ly
        move_y += self.handler.trigger_right() - self.handler.trigger_left()
        
        dpad = self.handler.dpad()
        if dpad[0] == 1: self.cursor_pos[0] += self.snap
        if dpad[0] == -1: self.cursor_pos[0] -= self.snap
        if dpad[1] == 1: self.cursor_pos[2] += self.snap
        if dpad[1] == -1: self.cursor_pos[2] -= self.snap
        if self.handler.held('R1'): self.cursor_pos[1] += self.snap
        if self.handler.held('L1'): self.cursor_pos[1] -= self.snap
        
        # Apply movement
        speed = self.cam_speed
        if keys[pygame.K_LSHIFT]: speed *= 3.0
        
        self.cam_pos[0] += (move_x * right[0] + move_y * up[0] + move_z * fwd[0]) * speed * dt
        self.cam_pos[1] += (move_x * right[1] + move_y * up[1] + move_z * fwd[1]) * speed * dt
        self.cam_pos[2] += (move_x * right[2] + move_y * up[2] + move_z * fwd[2]) * speed * dt

    def _add_vertex_at_cursor(self):
        # Check if vertex already exists at cursor
        for vid, pos in self.verts.items():
            if pos == tuple(self.cursor_pos):
                if vid not in self.selected_verts:
                    self.selected_verts.append(vid)
                return
                
        vid = f"v{self.next_v_id}"
        self.verts[vid] = tuple(self.cursor_pos)
        self.selected_verts.append(vid)
        self.next_v_id += 1
        
    def _delete_last_vertex(self):
        if self.next_v_id > 0:
            vid = f"v{self.next_v_id - 1}"
            if vid in self.verts:
                del self.verts[vid]
            if vid in self.selected_verts:
                self.selected_verts.remove(vid)
            self.next_v_id -= 1

    def _create_face(self):
        if len(self.selected_verts) >= 3:
            self.faces.append({
                'v': list(self.selected_verts),
                'color': self.current_color
            })
            self.selected_verts.clear()
            
    def _cycle_color(self):
        self.color_idx = (self.color_idx + 1) % len(self.colors)
        self.current_color = self.colors[self.color_idx]
        
    def _export_mesh(self):
        print("======== MESH EXPORT ========")
        print("        self.verts = {")
        for vid, pos in self.verts.items():
            print(f"            '{vid}': {pos},")
        print("        }")
        print("        self.faces = [")
        for f in self.faces:
            print(f"            {{'v': {f['v']}, 'color': {f['color']}}},")
        print("        ]")
        print("=============================")

    def draw_grid(self):
        col = (40, 40, 40)
        axis_x = (150, 50, 50)
        axis_y = (50, 150, 50)
        axis_z = (50, 50, 150)
        
        s = self.grid_size
        step = self.snap * 10
        
        if self.show_grid_xz:
            for i in range(-s, s + step, step):
                c = axis_z if i == 0 else col
                self.renderer.submit_line((i, 0, -s), (i, 0, s), c)
                c = axis_x if i == 0 else col
                self.renderer.submit_line((-s, 0, i), (s, 0, i), c)
                
        if self.show_grid_xy:
            for i in range(-s, s + step, step):
                c = axis_y if i == 0 else col
                self.renderer.submit_line((i, -s, 0), (i, s, 0), c)
                c = axis_x if i == 0 else col
                self.renderer.submit_line((-s, i, 0), (s, i, 0), c)
                
    def draw_cursor(self):
        cx, cy, cz = self.cursor_pos
        s = 5
        self.renderer.submit_line((cx-s, cy, cz), (cx+s, cy, cz), (255,0,0), 2)
        self.renderer.submit_line((cx, cy-s, cz), (cx, cy+s, cz), (0,255,0), 2)
        self.renderer.submit_line((cx, cy, cz-s), (cx, cy, cz+s), (0,0,255), 2)
        
    def draw_mesh(self):
        # Draw Faces
        for f in self.faces:
            pts = [self.verts[vid] for vid in f['v']]
            self.renderer.submit_polygon(pts, f['color'])
            
            # Winding Debug (Normal vector)
            if self.debug_winding and len(pts) >= 3:
                # Center of face
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                cz = sum(p[2] for p in pts) / len(pts)
                
                # Normal calculation (assuming CCW)
                p0, p1, p2 = pts[0], pts[1], pts[2]
                ux, uy, uz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
                vx, vy, vz = p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2]
                nx = uy*vz - uz*vy
                ny = uz*vx - ux*vz
                nz = ux*vy - uy*vx
                
                nlen = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
                nx, ny, nz = nx/nlen * 15, ny/nlen * 15, nz/nlen * 15
                
                self.renderer.submit_line((cx, cy, cz), (cx+nx, cy+ny, cz+nz), (255, 255, 0), 2)

        # Draw Vertices
        for vid, pos in self.verts.items():
            color = (255, 255, 255)
            if vid in self.selected_verts:
                color = (255, 100, 100)
            self.renderer.submit_sprite(pos[0], pos[1], pos[2], color, 3)

        # Draw lines between selected verts to show the face being built
        if len(self.selected_verts) > 0:
            for i in range(len(self.selected_verts) - 1):
                p1 = self.verts[self.selected_verts[i]]
                p2 = self.verts[self.selected_verts[i+1]]
                self.renderer.submit_line(p1, p2, (255, 100, 100), 2)

    def draw_ui(self):
        y = 10
        texts = [
            f"FPS: {int(self.clock.get_fps())}",
            f"Camera: {int(self.cam_pos[0])}, {int(self.cam_pos[1])}, {int(self.cam_pos[2])}",
            f"Cursor: {self.cursor_pos}",
            f"Verts: {len(self.verts)} | Faces: {len(self.faces)}",
            f"Selected Verts: {len(self.selected_verts)}",
            f"Color: {self.current_color}",
            f"Grids (X/Y): XZ={self.show_grid_xz} XY={self.show_grid_xy}",
            f"Winding Debug (N): {self.debug_winding}",
            "",
            "Controls:",
            "ESC: Toggle Mouse Capture",
            "WASD/QE: Move Camera (Shift to boost)",
            "Mouse / R-Stick: Look",
            "Arrows/PgUp/PgDn / DPad/L1/R1: Move Cursor",
            "Space / (X): Place/Select Vertex",
            "Backspace: Delete Last Vertex",
            "R / (Circle): Clear Selection",
            "F / (Square): Create Face from Selection",
            "C / (Triangle): Cycle Color",
            "P / (Options): Print Mesh to Console",
        ]
        
        for t in texts:
            img = self.font.render(t, True, (200, 200, 200))
            self.screen.blit(img, (10, y))
            y += 20
            
        # Draw current color box
        pygame.draw.rect(self.screen, self.current_color, (10, y, 30, 30))

    def main(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            
            self.process_input(dt)
            
            self.screen.fill((20, 20, 30))
            self.camera.update(tuple(self.cam_pos), self.cam_quat)
            self.renderer.clear()
            
            self.draw_grid()
            self.draw_mesh()
            self.draw_cursor()
            
            self.renderer.render(self.screen)
            
            self.draw_ui()
            
            pygame.display.flip()
            
        pygame.quit()
        
if __name__ == '__main__':
    MeshEditor().main()
