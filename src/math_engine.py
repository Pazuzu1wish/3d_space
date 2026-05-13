import math
import numpy as np
from numba import njit

# ──────────────────────────────────────────────
#  QUATERNION MATH ENGINE
#  Rotations are accumulated in body-local space,
#  so pitch/yaw/roll inputs always feel relative
#  to the cockpit regardless of current orientation.
# ──────────────────────────────────────────────


# ── Quaternion primitives ──────────────────────

@njit(fastmath=True, cache=True)
def quat_identity():
    """w, x, y, z"""
    return (1.0, 0.0, 0.0, 0.0)


@njit(fastmath=True, cache=True)
def quat_from_axis_angle(ax, ay, az, angle):
    """Create a unit quaternion representing a rotation of `angle` radians
    around the axis (ax, ay, az).  The axis must already be normalised."""
    half = angle * 0.5
    s = math.sin(half)
    return (math.cos(half), ax * s, ay * s, az * s)


@njit(fastmath=True, cache=True)
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


@njit(fastmath=True, cache=True)
def quat_normalise(q):
    w, x, y, z = q
    mag = math.sqrt(w*w + x*x + y*y + z*z) or 1.0
    return (w/mag, x/mag, y/mag, z/mag)


@njit(fastmath=True, cache=True)
def quat_conjugate(q):
    w, x, y, z = q
    return (w, -x, -y, -z)


@njit(fastmath=True, cache=True)
def quat_rotate_vec(q, v):
    """Rotate vector v = (vx, vy, vz) by unit quaternion q.
    Uses direct rotation matrix formula instead of q*p*q* (3x faster)."""
    w, qx, qy, qz = q
    vx, vy, vz = v
    # Pre-compute common terms
    xx = qx * qx; yy = qy * qy; zz = qz * qz
    xy = qx * qy; xz = qx * qz; yz = qy * qz
    wx = w * qx;  wy = w * qy;  wz = w * qz
    return (
        vx * (1.0 - 2.0*(yy + zz)) + vy * 2.0*(xy - wz) + vz * 2.0*(xz + wy),
        vx * 2.0*(xy + wz) + vy * (1.0 - 2.0*(xx + zz)) + vz * 2.0*(yz - wx),
        vx * 2.0*(xz - wy) + vy * 2.0*(yz + wx) + vz * (1.0 - 2.0*(xx + yy)),
    )


# ── Body-local rotation accumulation ──────────
#
# Call these every frame with the pilot's stick deltas.
# Each rotation is applied around the ship's OWN axes,
# so gimbal lock and world-relative weirdness disappear.

@njit(fastmath=True, cache=True)
def rotate_pitch(q, delta):
    """Pitch: rotate around the ship's local X (right) axis."""
    # local right = q rotated (1,0,0)
    local_right = quat_rotate_vec(q, (1.0, 0.0, 0.0))
    dq = quat_from_axis_angle(*local_right, delta)
    return quat_normalise(quat_mul(dq, q))


@njit(fastmath=True, cache=True)
def rotate_yaw(q, delta):
    """Yaw: rotate around the ship's local Y (up) axis."""
    local_up = quat_rotate_vec(q, (0.0, 1.0, 0.0))
    dq = quat_from_axis_angle(*local_up, delta)
    return quat_normalise(quat_mul(dq, q))


@njit(fastmath=True, cache=True)
def rotate_roll(q, delta):
    """Roll: rotate around the ship's local Z (forward) axis."""
    local_fwd = quat_rotate_vec(q, (0.0, 0.0, 1.0))
    dq = quat_from_axis_angle(*local_fwd, delta)
    return quat_normalise(quat_mul(dq, q))


# ── Derived basis vectors ──────────────────────

@njit(fastmath=True, cache=True)
def get_basis_from_quat(q):
    """Return (forward, right, up) unit vectors from orientation quaternion.
    Builds the rotation matrix once and extracts all 3 columns directly."""
    w, qx, qy, qz = q
    xx = qx * qx; yy = qy * qy; zz = qz * qz
    xy = qx * qy; xz = qx * qz; yz = qy * qz
    wx = w * qx;  wy = w * qy;  wz = w * qz
    # Right = column 0 (rotation of (1,0,0))
    right = (
        1.0 - 2.0*(yy + zz),
        2.0*(xy + wz),
        2.0*(xz - wy),
    )
    # Up = column 1 (rotation of (0,1,0))
    up = (
        2.0*(xy - wz),
        1.0 - 2.0*(xx + zz),
        2.0*(yz + wx),
    )
    # Forward = column 2 (rotation of (0,0,1))
    forward = (
        2.0*(xz + wy),
        2.0*(yz - wx),
        1.0 - 2.0*(xx + yy),
    )
    return forward, right, up


@njit(fastmath=True, cache=True)
def get_forward_from_quat(q):
    """Extract just the forward (Z) vector from a quaternion — avoids full basis build."""
    w, qx, qy, qz = q
    return (
        2.0*(qx*qz + w*qy),
        2.0*(qy*qz - w*qx),
        1.0 - 2.0*(qx*qx + qy*qy),
    )


@njit(fastmath=True, cache=True)
def get_right_from_quat(q):
    """Extract just the right (X) vector from a quaternion."""
    w, qx, qy, qz = q
    return (
        1.0 - 2.0*(qy*qy + qz*qz),
        2.0*(qx*qy + w*qz),
        2.0*(qx*qz - w*qy),
    )


# ── World → Camera transform ───────────────────

@njit(fastmath=True, cache=True)
def world_to_camera(x, y, z, px, py, pz, q):
    """Transform world-space point (x,y,z) into camera space.

    px,py,pz  – camera/player world position
    q         – camera orientation quaternion (w,x,y,z)

    Inlines conjugate + rotation to avoid intermediate tuple allocations.
    """
    # Translate
    dx, dy, dz = x - px, y - py, z - pz
    # Conjugate: negate x,y,z components of q
    w = q[0]; qx = -q[1]; qy = -q[2]; qz = -q[3]
    # Direct rotation matrix formula
    xx = qx * qx; yy = qy * qy; zz = qz * qz
    xy = qx * qy; xz = qx * qz; yz = qy * qz
    wx = w * qx;  wy = w * qy;  wz = w * qz
    return (
        dx * (1.0 - 2.0*(yy + zz)) + dy * 2.0*(xy - wz) + dz * 2.0*(xz + wy),
        dx * 2.0*(xy + wz) + dy * (1.0 - 2.0*(xx + zz)) + dz * 2.0*(yz - wx),
        dx * 2.0*(xz - wy) + dy * 2.0*(yz + wx) + dz * (1.0 - 2.0*(xx + yy)),
    )

@njit
def world_to_camera_batch(verts, px, py, pz, r_coeffs):
    """
    Numba-optimized batch world-to-camera transformation.
    verts: (N, 3) float64 array
    px, py, pz: camera position
    r_coeffs: (9,) array of rotation matrix coefficients [r00, r01, r02, r10, r11, r12, r20, r21, r22]
    """
    N = verts.shape[0]
    out = np.empty_like(verts)
    
    r00 = r_coeffs[0]; r01 = r_coeffs[1]; r02 = r_coeffs[2]
    r10 = r_coeffs[3]; r11 = r_coeffs[4]; r12 = r_coeffs[5]
    r20 = r_coeffs[6]; r21 = r_coeffs[7]; r22 = r_coeffs[8]
    
    for i in range(N):
        dx = verts[i, 0] - px
        dy = verts[i, 1] - py
        dz = verts[i, 2] - pz
        
        out[i, 0] = dx*r00 + dy*r01 + dz*r02
        out[i, 1] = dx*r10 + dy*r11 + dz*r12
        out[i, 2] = dx*r20 + dy*r21 + dz*r22
        
    return out


# ── Projection ────────────────────────────────

def project_to_screen(x, y, z, fov=400, cx=640, cy=370):
    if z <= 0.1:
        return None
    scale = fov / z
    sx = int(x * scale + cx)
    sy = int(y * scale + cy)
    return sx, sy, scale

@njit
def project_to_screen_batch(cam_verts, fov, cx, cy, ox, oy, near_clip):
    """
    Numba-optimized batch projection.
    cam_verts: (N, 3) float64 array
    returns: (N, 3) array [sx, sy, scale]. sx, sy are floats (must be cast to int later).
    """
    N = cam_verts.shape[0]
    out = np.empty((N, 3))
    
    for i in range(N):
        x = cam_verts[i, 0]
        y = cam_verts[i, 1]
        z = cam_verts[i, 2]
        
        if z <= near_clip:
            out[i, 0] = -1000000.0 # Sentinel for clipped
            out[i, 1] = -1000000.0
            out[i, 2] = 0.0
            continue
            
        scale = fov / z
        out[i, 0] = x * scale + cx + ox
        out[i, 1] = y * scale + cy + oy
        out[i, 2] = scale
        
    return out

# ── Targeting math ────────────────────────────

@njit(fastmath=True, cache=True)
def calculate_lead_position(player_pos, player_vel, target_pos, target_vel,
                            projectile_speed):

    # Convert inputs to vectors (assuming they're tuples/lists)
    px, py, pz = player_pos
    vpx, vpy, vpz = player_vel
    tx, ty, tz = target_pos
    vtx, vty, vtz = target_vel

    # Relative position and velocity
    rx = tx - px
    ry = ty - py
    rz = tz - pz
    rvx = vtx - vpx
    rvy = vty - vpy
    rvz = vtz - vpz

    # Dot products and magnitudes squared
    relative_pos_dot_relative_vel = rx * rvx + ry * rvy + rz * rvz
    relative_vel_mag_sq = rvx**2 + rvy**2 + rvz**2
    relative_pos_mag_sq = rx**2 + ry**2 + rz**2
    projectile_speed_sq = projectile_speed ** 2

    # Coefficients for quadratic equation: A*t^2 + B*t + C = 0
    A = relative_vel_mag_sq - projectile_speed_sq
    B = 2 * relative_pos_dot_relative_vel
    C = relative_pos_mag_sq

    # Discriminant
    discriminant = B**2 - 4 * A * C

    # No solution (target is too fast or moving away)
    if discriminant < 0 or A == 0:
        return target_pos  # Fallback: aim at current position

    # Solve for t (only positive root)
    t = (-B + math.sqrt(discriminant)) / (2 * A)
    if t < 0:
        t = (-B - math.sqrt(discriminant)) / (2 * A)
    if t < 0:
        return target_pos  # No valid intercept time

    # Calculate intercept position
    intercept_x = tx + vtx * t
    intercept_y = ty + vty * t
    intercept_z = tz + vtz * t

    return (intercept_x, intercept_y, intercept_z)

@njit(fastmath=True, cache=True)
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

@njit(fastmath=True, cache=True)
def get_forward_vector(pitch, yaw):
    """Legacy: forward from Euler pitch/yaw (no roll)."""
    fx = math.sin(yaw) * math.cos(pitch)
    fy = -math.sin(pitch)
    fz = math.cos(yaw) * math.cos(pitch)
    return fx, fy, fz


@njit(fastmath=True, cache=True)
def get_right_vector(pitch, yaw):
    """Legacy: right from Euler pitch/yaw."""
    fx, fy, fz = get_forward_vector(pitch, yaw)
    rx, ry, rz = fz, 0.0, -fx
    length = math.sqrt(rx*rx + ry*ry + rz*rz) or 1.0
    return rx/length, ry/length, rz/length


@njit(fastmath=True, cache=True)
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

@njit(fastmath=True, cache=True)
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

@njit(fastmath=True, cache=True)
def ray_sphere_intersection(ro, rd, sc, sr):
    """
    Ray-Sphere intersection test.
    ro: Ray origin (x, y, z)
    rd: Ray direction (normalized) (dx, dy, dz)
    sc: Sphere center (x, y, z)
    sr: Sphere radius
    Returns distance to hit, or -1.0 if no hit.
    """
    ocx, ocy, ocz = ro[0] - sc[0], ro[1] - sc[1], ro[2] - sc[2]
    
    # Quadratic coefficients: At^2 + Bt + C = 0
    # Since rd is normalized, A = rd.rd = 1
    b = 2.0 * (ocx * rd[0] + ocy * rd[1] + ocz * rd[2])
    c = (ocx*ocx + ocy*ocy + ocz*ocz) - sr*sr
    
    discriminant = b*b - 4.0*c
    
    if discriminant < 0:
        return -1.0
    
    sqrt_d = math.sqrt(discriminant)
    t1 = (-b - sqrt_d) / 2.0
    t2 = (-b + sqrt_d) / 2.0
    
    if t1 >= 0:
        return t1
    if t2 >= 0:
        return t2
        
    return -1.0