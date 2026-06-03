import os
import sys

# Add parent directory to path so src module can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Import your ship classes
from src.enemy import SuicideDrone, Dogfighter, Sniper, Corvette, Minelayer, Carrier, StealthInterceptor
from src.player import Player


def export_to_obj_mtl(name, verts_dict, faces_list, output_dir="assets"):
    # Ensure the assets folder exists
    os.makedirs(output_dir, exist_ok=True)

    obj_path = os.path.join(output_dir, f"{name}.obj")
    mtl_path = os.path.join(output_dir, f"{name}.mtl")

    # 1. Map string vertex keys (e.g. 'v0') to 1-based indices used by OBJ
    vert_keys = list(verts_dict.keys())
    vert_map = {key: i + 1 for i, key in enumerate(vert_keys)}

    # 2. Extract unique colors to generate materials
    unique_colors = {}
    mat_counter = 1
    for face in faces_list:
        color = tuple(face['color'])
        if color not in unique_colors:
            unique_colors[color] = f"{name}_mat_{mat_counter}"
            mat_counter += 1

    # 3. Write the .mtl (Material) file
    with open(mtl_path, 'w') as f:
        for color, mat_name in unique_colors.items():
            f.write(f"newmtl {mat_name}\n")
            # Convert 0-255 RGB to 0.0-1.0 format used by MTL
            r, g, b = color[0] / 255.0, color[1] / 255.0, color[2] / 255.0
            f.write(f"Kd {r:.4f} {g:.4f} {b:.4f}\n\n")

    # 4. Write the .obj (Geometry) file
    with open(obj_path, 'w') as f:
        # Link the material file
        f.write(f"mtllib {name}.mtl\n\n")

        # Write all vertices (v x y z)
        for key in vert_keys:
            vx, vy, vz = verts_dict[key]
            f.write(f"v {vx} {vy} {vz}\n")
        f.write("\n")

        # Write all faces (f v1 v2 v3) grouped by material
        current_mat = None
        for face in faces_list:
            color = tuple(face['color'])
            mat_name = unique_colors[color]

            # Switch material if needed
            if current_mat != mat_name:
                f.write(f"usemtl {mat_name}\n")
                current_mat = mat_name

            # Write the face indices
            v_indices = [str(vert_map[v_key]) for v_key in face['v']]
            f.write(f"f {' '.join(v_indices)}\n")

    print(f"Exported: {obj_path} and {mtl_path}")


if __name__ == "__main__":
    print("Exporting meshes...")

    # 1. Instantiate the ships (position 0,0,0 doesn't matter)
    drone = SuicideDrone(0, 0, 0)
    dogfighter = Dogfighter(0, 0, 0)
    sniper = Sniper(0, 0, 0)
    corvette = Corvette(0, 0, 0)
    minelayer = Minelayer(0, 0, 0)
    interceptor = StealthInterceptor(0, 0, 0)
    carrier = Carrier(0, 0, 0)
    player = Player()

    # 2. Export them
    export_to_obj_mtl("drone", drone.verts, drone.faces)
    export_to_obj_mtl("dogfighter", dogfighter.verts, dogfighter.faces)
    export_to_obj_mtl("sniper", sniper.verts, sniper.faces)
    export_to_obj_mtl("corvette", corvette.verts, corvette.faces)
    export_to_obj_mtl("minelayer", minelayer.verts, minelayer.faces)
    export_to_obj_mtl("interceptor", interceptor.verts, interceptor.faces)
    export_to_obj_mtl("carrier", carrier.verts, carrier.faces)
    export_to_obj_mtl("player", player.verts, player.faces)

    print("Done! You can now use these in the mesh loader.")