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


# ── Ship-model cache ─────────────────────────────────────────────────────────
# Maps ship-type name -> BakedMesh loaded from assets/
_SHIP_MESH_CACHE: dict[str, BakedMesh] = {}

# Canonical map from ship-type name to OBJ file (relative to project root)
_SHIP_OBJ_MAP = {
    'carrier':    'assets/carrier.obj',
    'corvette':   'assets/corvette.obj',
    'dogfighter': 'assets/dogfighter.obj',
    'drone':      'assets/drone.obj',
    'interceptor':'assets/interceptor.obj',
    'minelayer':  'assets/minelayer.obj',
    'player':     'assets/player.obj',
    'sniper':     'assets/sniper.obj',
}


def get_ship_mesh(ship_type: str) -> BakedMesh:
    """Return the cached BakedMesh for *ship_type*.

    Loads and parses the OBJ/MTL on the first call; subsequent calls return the
    in-memory BakedMesh with zero I/O.

    Raises ``FileNotFoundError`` if the OBJ file is missing.
    """
    if ship_type in _SHIP_MESH_CACHE:
        return _SHIP_MESH_CACHE[ship_type]

    obj_path = _SHIP_OBJ_MAP.get(ship_type)
    if obj_path is None:
        raise KeyError(f"[mesh_loader] Unknown ship type '{ship_type}'. "
                       f"Valid types: {list(_SHIP_OBJ_MAP.keys())}")

    if not os.path.exists(obj_path):
        raise FileNotFoundError(f"[mesh_loader] OBJ file not found: '{obj_path}'. "
                                f"Run tools/mesh_exporter.py first.")

    mesh = load_obj(obj_path)
    _SHIP_MESH_CACHE[ship_type] = mesh
    return mesh


def preload_all_meshes() -> None:
    """Load every known ship OBJ/MTL into the cache up-front.

    Call this once during startup (e.g. in Game.__init__) so that spawning an
    enemy later never touches the disk.
    """
    for ship_type in _SHIP_OBJ_MAP:
        try:
            get_ship_mesh(ship_type)
        except FileNotFoundError as e:
            print(f"[mesh_loader] WARNING: {e}")