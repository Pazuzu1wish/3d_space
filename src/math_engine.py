import math

# ──────────────────────────────────────────────
#  3D MATH ENGINE (FIXED)
# ──────────────────────────────────────────────
def get_forward_vector(pitch, yaw):
    """Returns a normalized 3D forward vector based on camera pitch/yaw."""
    fx = math.sin(yaw) * math.cos(pitch)
    fy = -math.sin(pitch)
    fz = math.cos(yaw) * math.cos(pitch)
    return fx, fy, fz


def world_to_camera(x, y, z, px, py, pz, pitch, yaw, roll):
    """Accurately transforms a World coordinate into a Camera-relative coordinate."""
    # 1. Translate point relative to camera position
    dx = x - px
    dy = y - py
    dz = z - pz

    # 2. Inverse Yaw (Y-axis rotation)
    x1 = dx * math.cos(yaw) - dz * math.sin(yaw)
    z1 = dx * math.sin(yaw) + dz * math.cos(yaw)

    # 3. Inverse Pitch (X-axis rotation)
    y2 = dy * math.cos(pitch) + z1 * math.sin(pitch)
    z2 = -dy * math.sin(pitch) + z1 * math.cos(pitch)

    # 4. Inverse Roll (Z-axis rotation)
    cx = x1 * math.cos(roll) + y2 * math.sin(roll)
    cy = -x1 * math.sin(roll) + y2 * math.cos(roll)
    cz = z2

    return cx, cy, cz


def project_to_screen(x, y, z, fov=400, cx=450, cy=310):
    if z <= 0.1:  # Behind camera
        return None
    scale = fov / z
    sx, sy = int(x * scale + cx), int(y * scale + cy)
    return sx, sy, scale