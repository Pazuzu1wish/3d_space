import os
import numpy as np


class BakedMesh:
    def __init__(self, v_data, f_idx, f_col, radius):
        self.v_data = v_data  # np.float64 (N, 3)
        self.f_idx = f_idx  # np.int32 (M, 3)
        self.f_col = f_col  # np.int32 (M, 3)
        self.radius = radius  # float: bounding sphere radius for fast culling


def parse_mtl(mtl_path):
    """Parses a basic .mtl file and returns a dict of material_name -> (R, G, B)"""
    materials = {}
    current_mat = None
    if not os.path.exists(mtl_path):
        return materials

    with open(mtl_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            if parts[0] == 'newmtl':
                current_mat = parts[1]
            elif parts[0] == 'Kd' and current_mat:
                # Kd is diffuse color (0.0 to 1.0) -> Convert to 0-255
                r, g, b = float(parts[1]), float(parts[2]), float(parts[3])
                materials[current_mat] = (int(r * 255), int(g * 255), int(b * 255))
    return materials


def load_obj(obj_path, default_color=(200, 200, 200)):
    verts = []
    f_idx = []
    f_col = []

    materials = {}
    current_color = default_color

    base_dir = os.path.dirname(obj_path)

    with open(obj_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue

            if parts[0] == 'mtllib':
                mtl_path = os.path.join(base_dir, parts[1])
                materials.update(parse_mtl(mtl_path))

            elif parts[0] == 'usemtl':
                mat_name = parts[1]
                current_color = materials.get(mat_name, default_color)

            elif parts[0] == 'v':
                # Vertices in OBJ are x, y, z
                verts.append([float(parts[1]), float(parts[2]), float(parts[3])])

            elif parts[0] == 'f':
                # OBJ indices are 1-based, we need 0-based
                # Also handle v/vt/vn formatting by splitting by '/'
                idx = [int(p.split('/')[0]) - 1 for p in parts[1:]]

                # Triangulate n-gons (e.g. quads) automatically
                for i in range(1, len(idx) - 1):
                    f_idx.append([idx[0], idx[i], idx[i + 1]])
                    f_col.append(current_color)

    v_data = np.array(verts, dtype=np.float64)

    # Calculate bounding radius for frustum culling (furthest point from origin)
    max_radius = float(np.max(np.linalg.norm(v_data, axis=1))) if len(v_data) > 0 else 0.0

    return BakedMesh(
        v_data=v_data,
        f_idx=np.array(f_idx, dtype=np.int32),
        f_col=np.array(f_col, dtype=np.int32),
        radius=max_radius
    )