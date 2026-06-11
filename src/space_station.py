import math
from src.mesh_loader import BakedMesh, get_ship_mesh


class SpaceStation:
    def __init__(self, x, y, z, scale=20.0):
        self.x, self.y, self.z = float(x), float(y), float(z)
        self.scale = scale

        # rotation
        self.angle_x = 0.0
        self.angle_y = 0.0
        self.angle_z = 0.0

        # rotation speed
        self.rot_vel_x = 0.0
        self.rot_vel_y = 0.1
        self.rot_vel_z = 0.0

        self.baked_mesh = get_ship_mesh('space_station')
        self.verts = {f'v{i}': tuple(row) for i, row in enumerate(self.baked_mesh.v_data)}
        self.faces = [
            {'v': [f'v{self.baked_mesh.f_idx[i, 0]}',
                   f'v{self.baked_mesh.f_idx[i, 1]}',
                   f'v{self.baked_mesh.f_idx[i, 2]}'],
             'color': tuple(self.baked_mesh.f_col[i])}
            for i in range(len(self.baked_mesh.f_idx))
        ]

    def update(self, dt):
        self.angle_x += self.rot_vel_x * dt
        self.angle_y += self.rot_vel_y * dt
        self.angle_z += self.rot_vel_z * dt

    def submit_to_renderer(self, renderer):
        cx, sx = math.cos(self.angle_x), math.sin(self.angle_x)
        cy, sy = math.cos(self.angle_y), math.sin(self.angle_y)
        cz, sz = math.cos(self.angle_z), math.sin(self.angle_z)

        # Right (1, 0, 0)
        rx = cy * cz - sy * sx * sz
        ry = cy * sz + sy * sx * cz
        rz = -sy * cx
        # Up (0, 1, 0)
        ux = -cx * sz
        uy = cx * cz
        uz = sx
        # Forward (0, 0, 1)
        fx = sy * cz + cy * sx * sz
        fy = sy * sz - cy * sx * cz
        fz = cy * cx

        renderer.submit_baked_mesh(
            (self.x, self.y, self.z),
            (rx, ry, rz),
            (ux, uy, uz),
            (fx, fy, fz),
            self.baked_mesh,
            layer='opaque',
            scale=self.scale
        )