import math
import numpy as np

# ──────────────────────────────────────────────
#  QUATERNION MATH ENGINE
#  Rotations are accumulated in body-local space,
#  so pitch/yaw/roll inputs always feel relative
#  to the cockpit regardless of current orientation.
# ──────────────────────────────────────────────


# ── Quaternion primitives ──────────────────────

def quat_identity():
    """w, x, y, z"""
    return (1.0, 0.0, 0.0, 0.0)


def quat_from_axis_angle(ax, ay, az, angle):
    """Create a unit quaternion representing a rotation of `angle` radians
    around the axis (ax, ay, az).  The axis must already be normalised."""
    half = angle * 0.5
    s = math.sin(half)
    return (math.cos(half), ax * s, ay * s, az * s)


def quat_mul(a, b):
    """Hamilton product of two quaternions."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw*bw - ax*bx - ay*by - az*bz,
        aw*bx + ax*bw + ay*bz - az*by,
        aw*by - ax*bz + ay*bw + az*bx,
        aw*bz + ax*by - ay*bx + az*bw,
    )


def quat_normalise(q):
    w, x, y, z = q
    mag = math.sqrt(w*w + x*x + y*y + z*z) or 1.0
    return (w/mag, x/mag, y/mag, z/mag)


def quat_conjugate(q):
    w, x, y, z = q
    return (w, -x, -y, -z)


def quat_rotate_vec(q, v):
    """Rotate vector v = (vx, vy, vz) by unit quaternion q."""
    vx, vy, vz = v
    # p = pure quaternion form of v
    p = (0.0, vx, vy, vz)
    # rotated = q * p * q*
    r = quat_mul(quat_mul(q, p), quat_conjugate(q))
    return r[1], r[2], r[3]


# ── Body-local rotation accumulation ──────────
#
# Call these every frame with the pilot's stick deltas.
# Each rotation is applied around the ship's OWN axes,
# so gimbal lock and world-relative weirdness disappear.

def rotate_pitch(q, delta):
    """Pitch: rotate around the ship's local X (right) axis."""
    # local right = q rotated (1,0,0)
    local_right = quat_rotate_vec(q, (1.0, 0.0, 0.0))
    dq = quat_from_axis_angle(*local_right, delta)
    return quat_normalise(quat_mul(dq, q))


def rotate_yaw(q, delta):
    """Yaw: rotate around the ship's local Y (up) axis."""
    local_up = quat_rotate_vec(q, (0.0, 1.0, 0.0))
    dq = quat_from_axis_angle(*local_up, delta)
    return quat_normalise(quat_mul(dq, q))


def rotate_roll(q, delta):
    """Roll: rotate around the ship's local Z (forward) axis."""
    local_fwd = quat_rotate_vec(q, (0.0, 0.0, 1.0))
    dq = quat_from_axis_angle(*local_fwd, delta)
    return quat_normalise(quat_mul(dq, q))


# ── Derived basis vectors ──────────────────────

def get_basis_from_quat(q):
    """Return (forward, right, up) unit vectors from orientation quaternion."""
    forward = quat_rotate_vec(q, (0.0, 0.0, 1.0))
    right   = quat_rotate_vec(q, (1.0, 0.0, 0.0))
    up      = quat_rotate_vec(q, (0.0, 1.0, 0.0))
    return forward, right, up


def get_forward_from_quat(q):
    return quat_rotate_vec(q, (0.0, 0.0, 1.0))


def get_right_from_quat(q):
    return quat_rotate_vec(q, (1.0, 0.0, 0.0))


# ── World → Camera transform ───────────────────

def world_to_camera(x, y, z, px, py, pz, q):
    """Transform world-space point (x,y,z) into camera space.

    px,py,pz  – camera/player world position
    q         – camera orientation quaternion (w,x,y,z)
    """
    # Translate
    dx, dy, dz = x - px, y - py, z - pz
    # Inverse-rotate by camera orientation (= conjugate rotation)
    return quat_rotate_vec(quat_conjugate(q), (dx, dy, dz))


# ── Projection ────────────────────────────────

def project_to_screen(x, y, z, fov=400, cx=450, cy=310):
    if z <= 0.1:
        return None
    scale = fov / z
    sx = int(x * scale + cx)
    sy = int(y * scale + cy)
    return sx, sy, scale


# ── Targeting math ────────────────────────────

def calculate_lead_position(player_pos, player_vel, target_pos, target_vel, proj_speed):
    """
    First-order kinematic intercept: returns the 3-D world coordinate
    the player should aim at so that a projectile (at proj_speed) will
    meet the target.

    Accounts for the player's own velocity because bullets inherit it.
    """
    rel_x = target_pos[0] - player_pos[0]
    rel_y = target_pos[1] - player_pos[1]
    rel_z = target_pos[2] - player_pos[2]
    dist = math.sqrt(rel_x**2 + rel_y**2 + rel_z**2) or 1.0

    # Time-of-flight approximation (first order)
    t = dist / proj_speed

    # Relative velocity (target minus player — bullets inherit our momentum)
    rel_vx = target_vel[0] - player_vel[0]
    rel_vy = target_vel[1] - player_vel[1]
    rel_vz = target_vel[2] - player_vel[2]

    return (
        target_pos[0] + rel_vx * t,
        target_pos[1] + rel_vy * t,
        target_pos[2] + rel_vz * t,
    )


def is_in_front_of_camera(world_pos, player_pos, player_orientation):
    """
    Returns True if world_pos is in the positive-Z half of camera space
    (i.e. the point is in front of the player).
    """
    cx, cy, cz = world_to_camera(
        world_pos[0], world_pos[1], world_pos[2],
        player_pos[0], player_pos[1], player_pos[2],
        player_orientation,
    )
    return cz > 0.1


# ── Legacy shims (kept so other modules don't break) ──────────────────────────
#  These are thin wrappers; prefer the quat versions for new code.

def get_forward_vector(pitch, yaw):
    """Legacy: forward from Euler pitch/yaw (no roll)."""
    fx = math.sin(yaw) * math.cos(pitch)
    fy = -math.sin(pitch)
    fz = math.cos(yaw) * math.cos(pitch)
    return fx, fy, fz


def get_right_vector(pitch, yaw):
    """Legacy: right from Euler pitch/yaw."""
    fx, fy, fz = get_forward_vector(pitch, yaw)
    rx, ry, rz = fz, 0.0, -fx
    length = math.sqrt(rx*rx + ry*ry + rz*rz) or 1.0
    return rx/length, ry/length, rz/length


def get_basis_vectors(pitch, yaw, roll):
    """Legacy Euler basis — prefer get_basis_from_quat."""
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw),   math.sin(yaw)
    cr, sr = math.cos(roll),  math.sin(roll)
    fx, fy, fz = sy*cp, -sp, cy*cp
    rx = cy*cr + sy*sp*sr
    ry = cp*sr
    rz = -sy*cr + cy*sp*sr
    ux = -cy*sr + sy*sp*cr
    uy = cp*cr
    uz = sy*sr + cy*sp*cr
    return (fx,fy,fz), (rx,ry,rz), (ux,uy,uz)

def basis_from_forward(forward):
    fx, fy, fz = forward
    flen = math.sqrt(fx*fx + fy*fy + fz*fz) or 1.0
    fx, fy, fz = fx/flen, fy/flen, fz/flen

    world_up = (0.0, 1.0, 0.0)

    # right = forward × up
    rx = fy * world_up[2] - fz * world_up[1]
    ry = fz * world_up[0] - fx * world_up[2]
    rz = fx * world_up[1] - fy * world_up[0]

    rlen = math.sqrt(rx*rx + ry*ry + rz*rz) or 1.0
    rx, ry, rz = rx/rlen, ry/rlen, rz/rlen

    # recompute up = right × forward
    ux = ry * fz - rz * fy
    uy = rz * fx - rx * fz
    uz = rx * fy - ry * fx

    return (fx, fy, fz), (rx, ry, rz), (ux, uy, uz)