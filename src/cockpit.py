
import pygame
import math
from .math_engine import (
    get_basis_from_quat,
    get_forward_from_quat,
    quat_rotate_vec,
    quat_conjugate,
    world_to_camera,
    project_to_screen,
    calculate_lead_position,
    is_in_front_of_camera,
)

# ── Palette (R, G, B, Alpha) ──────────────────
from .constants import HUD_GREEN, HUD_DIM, HUD_AMBER, HUD_RED

# ──────────────────────────────────────────────
#  COCKPIT HUD
#  - Heading Tape (Compass)
#  - Pitch Ladder
#  - 3D Radar disc with elevation ticks
#  - Throttle / speed bar
#  - Crosshair
# ──────────────────────────────────────────────

# -----------------------------------------------
# Font and Cache
# -----------------------------------------------

_FONT_CACHE = {}


def custom_font(size):
    if size not in _FONT_CACHE:
        try:
            _FONT_CACHE[size] = pygame.font.Font('./assets/fonts/interdictionexpand.ttf', size)
        except Exception:
            _FONT_CACHE[size] = pygame.font.SysFont(None, size)
    return _FONT_CACHE[size]


# ──────────────────────────────────────────────
#  HEADING TAPE (COMPASS)
# ──────────────────────────────────────────────

def draw_heading_tape(surface, cx, y, orientation):
    forward, right, up = get_basis_from_quat(orientation)

    heading_rad = math.atan2(forward[0], forward[2])
    heading_deg = math.degrees(heading_rad)
    if heading_deg < 0:
        heading_deg += 360

    tape_w = 400
    tape_h = 30
    x0 = cx - tape_w // 2

    tape_surf = pygame.Surface((tape_w, tape_h), pygame.SRCALPHA)
    tape_surf.fill((0, 30, 0, 40))  # Very subtle dark background
    pygame.draw.rect(tape_surf, HUD_DIM, (0, 0, tape_w, tape_h), 1)
    surface.blit(tape_surf, (x0, y))

    pygame.draw.polygon(surface, HUD_GREEN, [
        (cx, y + tape_h),
        (cx - 6, y + tape_h + 6),
        (cx + 6, y + tape_h + 6)
    ])

    px_per_deg = tape_w / 60.0
    font = custom_font(14)

    start_deg = int(heading_deg - 35)
    end_deg = int(heading_deg + 35)

    for d in range(start_deg, end_deg + 1):
        if d % 5 == 0:
            diff = d - heading_deg
            sx = cx + int(diff * px_per_deg)

            if x0 + 2 <= sx <= x0 + tape_w - 2:
                norm_d = d % 360
                #if norm_d < 0: norm_d += 360

                if norm_d % 15 == 0:
                    pygame.draw.line(surface, HUD_GREEN, (sx, y), (sx, y + 8), 2)

                    if norm_d == 0:
                        txt = "Fore"
                    elif norm_d == 90:
                        txt = "Star"
                    elif norm_d == 180:
                        txt = "Aft"
                    elif norm_d == 270:
                        txt = "Port"
                    else:
                        txt = f"{norm_d:03d}"

                    lbl = font.render(txt, True, HUD_GREEN)
                    surface.blit(lbl, (sx - lbl.get_width() // 2, y + 12))
                else:
                    pygame.draw.line(surface, HUD_DIM, (sx, y), (sx, y + 5), 1)


# ──────────────────────────────────────────────
#  PITCH LADDER
# ──────────────────────────────────────────────

def draw_pitch_ladder(surface, cx, cy, orientation):
    forward, right, up = get_basis_from_quat(orientation)

    pitch_angle = math.asin(max(-1.0, min(1.0, -forward[1])))
    roll_angle = math.atan2(right[1], up[1])

    px_per_rad = 400.0

    cos_r = math.cos(-roll_angle)
    sin_r = math.sin(-roll_angle)

    def rot(px, py):
        return (int(cx + px * cos_r - py * sin_r),
                int(cy + px * sin_r + py * cos_r))

    font = custom_font(12)
    gap = 160
    w = 90

    for deg in range(-90, 91, 10):
        if deg == 0:
            y_off = (pitch_angle - 0) * px_per_rad
            if abs(y_off) > 400: continue

            pygame.draw.line(surface, HUD_GREEN, rot(-200, y_off), rot(-gap, y_off), 2)
            pygame.draw.line(surface, HUD_GREEN, rot(gap, y_off), rot(200, y_off), 2)
            continue

        y_off = (pitch_angle - math.radians(deg)) * px_per_rad
        if abs(y_off) > 350: continue

        tail = 8 if deg > 0 else -8
        col = HUD_GREEN

        if deg > 0:
            pygame.draw.line(surface, col, rot(-(w + gap), y_off), rot(-gap, y_off), 2)
            pygame.draw.line(surface, col, rot(-(w + gap), y_off), rot(-(w + gap), y_off + tail), 2)

            pygame.draw.line(surface, col, rot((w + gap), y_off), rot(gap, y_off), 2)
            pygame.draw.line(surface, col, rot((w + gap), y_off), rot((w + gap), y_off + tail), 2)

        else:
            dash_len = 12
            space = 12

            pygame.draw.line(surface, col, rot(-(w + gap), y_off), rot(-(w + gap), y_off + tail), 2)
            for i in range(3):
                dx1 = -(w + gap) + i * (dash_len + space)
                dx2 = dx1 + dash_len
                pygame.draw.line(surface, col, rot(dx1, y_off), rot(dx2, y_off), 2)

            pygame.draw.line(surface, col, rot(w + gap, y_off), rot(w + gap, y_off + tail), 2)
            for i in range(3):
                dx1 = gap + i * (dash_len + space)
                dx2 = dx1 + dash_len
                pygame.draw.line(surface, col, rot(dx1, y_off), rot(dx2, y_off), 2)

        lbl = font.render(str(abs(deg)), True, col)

        lx, ly = rot(-(w + gap + 15), y_off)
        surface.blit(lbl, (lx - lbl.get_width() // 2, ly - lbl.get_height() // 2))

        rx, ry = rot((w + gap + 15), y_off)
        surface.blit(lbl, (rx - lbl.get_width() // 2, ry - lbl.get_height() // 2))


# ──────────────────────────────────────────────
#  RADAR
# ──────────────────────────────────────────────

# Cache dictionary to store the radar backgrounds
_RADAR_CACHE = {}


def draw_radar(surface, cx, cy, radius, orientation, player_pos, enemies, radar_range=6000):
    global _RADAR_CACHE

    forward, right, up = get_basis_from_quat(orientation)
    tilt_factor = 0.5  # How much the radar is tilted (0.0 = edge on, 1.0 = top down)

    # ─── 1. DRAW (OR BLIT CACHED) HOLOSPHERE WIREFRAME ────────────────────
    cache_key = (radius, tilt_factor)

    if cache_key not in _RADAR_CACHE:
        # Create the surface for the radar background ONCE
        disc = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)

        # Outer spherical boundary (Dark green glass effect)
        pygame.draw.circle(disc, (0, 30, 0, 50), (radius, radius), radius)
        pygame.draw.circle(disc, HUD_DIM, (radius, radius), radius, 1)

        # Equatorial Plane (Ellipse)
        eq_rect = pygame.Rect(0, radius - (radius * tilt_factor), radius * 2, radius * 2 * tilt_factor)
        pygame.draw.ellipse(disc, HUD_DIM, eq_rect, 1)

        # Mid-range Equatorial Ring
        mid_r = radius // 2
        mid_rect = pygame.Rect(radius - mid_r, radius - (mid_r * tilt_factor), mid_r * 2, mid_r * 2 * tilt_factor)
        pygame.draw.ellipse(disc, (HUD_DIM[0], HUD_DIM[1], HUD_DIM[2], 100), mid_rect, 1)

        # Crosshairs on the equatorial plane
        pygame.draw.line(disc, HUD_DIM, (0, radius), (radius * 2, radius), 1)  # X-axis
        pygame.draw.line(disc, HUD_DIM, (radius, radius - radius * tilt_factor),
                         (radius, radius + radius * tilt_factor), 1)  # Z-axis (tilted)

        # Polar Axis (Y-axis vertical line)
        pygame.draw.line(disc, HUD_DIM, (radius, 0), (radius, radius * 2), 1)

        _RADAR_CACHE[cache_key] = disc

    # Blit the cached base holosphere directly to the HUD
    surface.blit(_RADAR_CACHE[cache_key], (cx - radius, cy - radius))

    # ─── 2. PLOT THE ENTITIES ─────────────────────────────────────────────
    px, py, pz = player_pos

    # Math Optimization: Use squared distance to avoid math.sqrt in the loop
    radar_range_sq = radar_range * radar_range
    physical_bound_sq = (radius - 6) ** 2

    for e in enemies:
        dx, dy, dz = e.x - px, e.y - py, e.z - pz
        dist_sq = dx * dx + dy * dy + dz * dz

        if dist_sq > radar_range_sq:
            continue

        # Get local coordinates relative to ship orientation
        local_x = dx * right[0] + dy * right[1] + dz * right[2]
        local_y = dx * up[0] + dy * up[1] + dz * up[2]  # Elevation
        local_z = dx * forward[0] + dy * forward[1] + dz * forward[2]  # Depth

        # Scale to fit inside the sphere radius
        scale = (radius - 6) / radar_range
        scaled_x = local_x * scale
        scaled_y = local_y * scale
        scaled_z = local_z * scale

        # Apply Pseudo-3D Isometric Projection
        plane_x = cx + int(scaled_x)
        plane_y = cy - int(scaled_z * tilt_factor)

        true_x = plane_x
        true_y = plane_y - int(scaled_y)

        # Check if blip exceeds the visual 2D radius using squared distance
        if (true_x - cx) ** 2 + (true_y - cy) ** 2 > physical_bound_sq:
            continue

        # Depth Cueing: Brightness based on whether it is in front or behind us
        color = HUD_RED if dist_sq < (radar_range_sq * 0.09) else HUD_AMBER  # 0.09 is 0.3 squared
        alpha_color = color
        if scaled_z < 0:
            # Dim the color if the enemy is behind the player
            alpha_color = (int(color[0] * 0.4), int(color[1] * 0.4), int(color[2] * 0.4))

        # Draw the "Stem" (Drop-line from entity to the equatorial plane)
        pygame.draw.line(surface, HUD_DIM, (plane_x, plane_y), (true_x, true_y), 1)

        # Draw the plane marker (where the stem hits the equator)
        pygame.draw.rect(surface, HUD_DIM, (plane_x - 1, plane_y - 1, 3, 3))

        # Draw the actual Entity Blip
        pygame.draw.circle(surface, alpha_color, (true_x, true_y), 3)

    # ─── 3. 6D CARDINALITY (WORLD AXES ON RADAR EDGES) ────────────────────
    cardinals = (
        ("N", (0, 1, 0)),
        ("S", (0, -1, 0)),
        ("ST", (1, 0, 0)),
        ("P", (-1, 0, 0)),
        ("F", (0, 0, 1)),
        ("A", (0, 0, -1)),
    )

    cardinal_font = custom_font(10)
    edge_radius = radius - 8

    for label, (wx, wy, wz) in cardinals:
        local_x = wx * right[0] + wy * right[1] + wz * right[2]
        local_y = wx * up[0] + wy * up[1] + wz * up[2]
        local_z = wx * forward[0] + wy * forward[1] + wz * forward[2]

        scaled_x = local_x * edge_radius
        scaled_y = local_y * edge_radius
        scaled_z = local_z * edge_radius

        plane_x = cx + int(scaled_x)
        plane_y = cy - int(scaled_z * tilt_factor)
        true_x = plane_x
        true_y = plane_y - int(scaled_y)

        if scaled_z < 0:
            col = (HUD_GREEN[0] // 3, HUD_GREEN[1] // 3, HUD_GREEN[2] // 3)
        else:
            col = HUD_GREEN

        pygame.draw.circle(surface, col, (true_x, true_y), 2)
        lbl = cardinal_font.render(label, True, col)
        surface.blit(lbl, (true_x - lbl.get_width() // 2, true_y - lbl.get_height() - 4))

    # ─── 4. DRAW ABSOLUTE ORIGIN (HOME 0,0,0) ─────────────────────────────
    ox, oy, oz = -px, -py, -pz
    dist_to_origin_sq = ox * ox + oy * oy + oz * oz

    if dist_to_origin_sq <= radar_range_sq:
        local_ox = ox * right[0] + oy * right[1] + oz * right[2]
        local_oy = ox * up[0] + oy * up[1] + oz * up[2]
        local_oz = ox * forward[0] + oy * forward[1] + oz * forward[2]

        scale = (radius - 6) / radar_range
        scaled_ox = local_ox * scale
        scaled_oy = local_oy * scale
        scaled_oz = local_oz * scale

        plane_ox = cx + int(scaled_ox)
        plane_oy = cy - int(scaled_oz * tilt_factor)
        true_ox = plane_ox
        true_oy = plane_oy - int(scaled_oy)

        # Clip against physical sphere boundary using squared distance
        if (true_ox - cx) ** 2 + (true_oy - cy) ** 2 <= physical_bound_sq:
            orig_col = (0, 200, 255)  # Cyan
            if scaled_oz < 0:
                orig_col = (0, 80, 100)  # Dim Cyan

            # Draw distinctive Cross marker for Origin
            pygame.draw.line(surface, orig_col, (true_ox - 4, true_oy), (true_ox + 4, true_oy), 1)
            pygame.draw.line(surface, orig_col, (true_ox, true_oy - 4), (true_ox, true_oy + 4), 1)

            lbl_orig = custom_font(10).render("ORIGIN", True, orig_col)
            surface.blit(lbl_orig, (true_ox + 4, true_oy + 4))

    # ─── 5. DRAW THE PLAYER MARKER ────────────────────────────────────────
    pygame.draw.circle(surface, HUD_GREEN, (cx, cy), 3)

    ind_x = cx + int(forward[0] * 12)
    ind_y = cy - int(forward[2] * 12 * tilt_factor)
    pygame.draw.line(surface, HUD_GREEN, (cx, cy), (ind_x, ind_y), 2)

    lbl = custom_font(12).render("3D SENSOR", True, HUD_GREEN)
    surface.blit(lbl, (cx - lbl.get_width() // 2, cy + radius + 5))

# ──────────────────────────────────────────────
#  THROTTLE BAR
# ──────────────────────────────────────────────

def draw_throttle_bar(surface, x, y, h, throttle):
    w = 14
    half_h = h // 2
    center_y = y + half_h
    
    # Track outline
    pygame.draw.rect(surface, HUD_DIM, (x, y, w, h), 1)
    
    # Center line
    pygame.draw.line(surface, HUD_DIM, (x - 4, center_y), (x + w, center_y), 2)
    
    if throttle > 0:
        fill_h = int(half_h * throttle)
        col = HUD_RED if throttle > 0.85 else HUD_AMBER if throttle > 0.5 else HUD_GREEN
        pygame.draw.rect(surface, col, (x, center_y - fill_h, w, fill_h))
    elif throttle < 0:
        fill_h = int(half_h * abs(throttle))
        col = (0, 200, 255, 160) # Cyan for retro
        pygame.draw.rect(surface, col, (x, center_y, w, fill_h))

    for pct in (0.25, 0.5, 0.75):
        ty_up = int(center_y - half_h * pct)
        ty_down = int(center_y + half_h * pct)
        pygame.draw.line(surface, HUD_DIM, (x - 2, ty_up), (x, ty_up), 1)
        pygame.draw.line(surface, HUD_DIM, (x - 2, ty_down), (x, ty_down), 1)

    f = custom_font(10)
    surface.blit(f.render("THR", True, HUD_GREEN), (x - 8, y - 14))
    
    if throttle >= 0:
        col_throttle_per = HUD_RED if throttle > 0.85 else HUD_AMBER if throttle > 0.5 else HUD_GREEN
        txt = f"{int(throttle * 100):3d}%"
    else:
        col_throttle_per = (0, 200, 255, 160)
        txt = f"{int(abs(throttle) * 100):3d}%"
        
    surface.blit(f.render(txt, True, col_throttle_per),
                 (x - 10, y + h + 10))


# ──────────────────────────────────────────────
#  CROSSHAIR
# ──────────────────────────────────────────────

def draw_crosshair(surface, cx, cy, ready):
    col = HUD_GREEN if ready else HUD_AMBER
    gap = 10
    arm = 18
    thick = 1
    pygame.draw.line(surface, col, (cx - arm - gap, cy), (cx - gap, cy), thick)
    pygame.draw.line(surface, col, (cx + gap, cy), (cx + arm + gap, cy), thick)
    pygame.draw.line(surface, col, (cx, cy - arm - gap), (cx, cy - gap), thick)
    pygame.draw.line(surface, col, (cx, cy + gap), (cx, cy + arm + gap), thick)
    pygame.draw.circle(surface, col, (cx, cy), gap, thick)
    if not ready:
        pygame.draw.circle(surface, HUD_RED, (cx, cy), 3)


# ──────────────────────────────────────────────
#  TARGET BRACKETS + LEAD INDICATOR (PIP)
# ──────────────────────────────────────────────

_LASER_SPEED = 4000.0   # Must match Laser class speed

# Dim colour for untargeted enemies (slightly transparent red-brown)
_HUD_DIM_TARGET  = (180, 40, 40, 90)
# Bright red for the active target bracket
_HUD_ACT_BRACKET = (255, 60, 60, 220)
# Amber for the lead PIP circle + leash line
_HUD_LEAD_PIP    = (255, 200, 50, 200)
# Dim leash line colour
_HUD_LEASH       = (255, 80, 80, 70)


def _draw_dim_bracket(surface, sx, sy, half=14):
    """Faint corner-bracket [ ] for an untargeted enemy."""
    c = _HUD_DIM_TARGET
    t = 1
    # left vertical, right vertical
    pygame.draw.line(surface, c, (sx - half, sy - half), (sx - half, sy + half), t)
    pygame.draw.line(surface, c, (sx + half, sy - half), (sx + half, sy + half), t)
    # short horizontal serifs
    pygame.draw.line(surface, c, (sx - half, sy - half), (sx - half + 5, sy - half), t)
    pygame.draw.line(surface, c, (sx - half, sy + half), (sx - half + 5, sy + half), t)
    pygame.draw.line(surface, c, (sx + half, sy - half), (sx + half - 5, sy - half), t)
    pygame.draw.line(surface, c, (sx + half, sy + half), (sx + half - 5, sy + half), t)


def _draw_active_bracket(surface, sx, sy, half=18):
    """Bright angled bracket < > for the active/locked target."""
    c = _HUD_ACT_BRACKET
    t = 2
    # chevron-style corners
    arm = 8
    # top-left
    pygame.draw.line(surface, c, (sx - half + arm, sy - half), (sx - half, sy - half), t)
    pygame.draw.line(surface, c, (sx - half, sy - half),       (sx - half, sy - half + arm), t)
    # top-right
    pygame.draw.line(surface, c, (sx + half - arm, sy - half), (sx + half, sy - half), t)
    pygame.draw.line(surface, c, (sx + half, sy - half),       (sx + half, sy - half + arm), t)
    # bottom-left
    pygame.draw.line(surface, c, (sx - half, sy + half - arm), (sx - half, sy + half), t)
    pygame.draw.line(surface, c, (sx - half, sy + half),       (sx - half + arm, sy + half), t)
    # bottom-right
    pygame.draw.line(surface, c, (sx + half, sy + half - arm), (sx + half, sy + half), t)
    pygame.draw.line(surface, c, (sx + half, sy + half),       (sx + half - arm, sy + half), t)
    # corner pips
    for qx, qy in ((sx - half, sy - half), (sx + half, sy - half),
                   (sx - half, sy + half), (sx + half, sy + half)):
        pygame.draw.circle(surface, c, (qx, qy), 2)


def draw_target_brackets(
        surface, player_pos, player_vel, player_orientation,
        enemies, active_target, W, H):
    """
    Draw HUD brackets for every visible enemy:
      - Untargeted: dim [ ] bracket
      - Active target: bright < > bracket + distance / hull readout
      - Lead PIP: amber circle + leash line
    """
    font = custom_font(11)

    active_screen = None   # store for leash line later

    for enemy in enemies:
        # Project the enemy's world position to screen
        cx, cy, cz = world_to_camera(
            enemy.x, enemy.y, enemy.z,
            player_pos[0], player_pos[1], player_pos[2],
            player_orientation
        )
        if cz <= 0.1:
            continue   # behind the camera — skip

        proj = project_to_screen(cx, cy, cz)
        if proj is None:
            continue
        sx, sy, _ = proj

        # Clip to screen bounds (with a margin so partially-off labels render)
        if not (-120 <= sx <= W + 120 and -120 <= sy <= H + 120):
            continue

        if enemy is active_target:
            _draw_active_bracket(surface, sx, sy)
            active_screen = (sx, sy)

            # Distance & hull readout (using squared distance to avoid sqrt)
            dist_m = int(math.sqrt(
                (enemy.x - player_pos[0])**2 +
                (enemy.y - player_pos[1])**2 +
                (enemy.z - player_pos[2])**2
            ))
            # Get max HP from the enemy object
            max_hp = enemy.max_hp
            hull_pct = int(max(0, enemy.hp / max_hp) * 100)

            dist_lbl = font.render(f"{dist_m:,} m", True, _HUD_ACT_BRACKET)
            hull_lbl = font.render(f"HULL {hull_pct}%", True, _HUD_ACT_BRACKET)
            surface.blit(dist_lbl, (sx - dist_lbl.get_width() // 2, sy + 22))
            surface.blit(hull_lbl, (sx - hull_lbl.get_width() // 2, sy + 22 + 14))

        else:
            _draw_dim_bracket(surface, sx, sy)

    # ── LEAD INDICATOR (PIP) ──────────────────────────────────────────────
    if active_target is not None and active_screen is not None:
        target_vel = (active_target.vx, active_target.vy, active_target.vz)
        target_pos = (active_target.x, active_target.y, active_target.z)

        lead_3d = calculate_lead_position(
            player_pos, player_vel, target_pos, target_vel, _LASER_SPEED
        )

        if is_in_front_of_camera(lead_3d, player_pos, player_orientation):
            lcx, lcy, lcz = world_to_camera(
                lead_3d[0], lead_3d[1], lead_3d[2],
                player_pos[0], player_pos[1], player_pos[2],
                player_orientation
            )
            lproj = project_to_screen(lcx, lcy, lcz)
            if lproj is not None:
                lx, ly, _ = lproj

                # Faint leash line from target bracket to lead pip
                pygame.draw.line(surface, _HUD_LEASH, active_screen, (lx, ly), 1)

                # Lead pip: outer circle + cross-hair
                c = _HUD_LEAD_PIP
                pygame.draw.circle(surface, c, (lx, ly), 9, 1)
                pygame.draw.line(surface,   c, (lx - 5, ly), (lx + 5, ly), 1)
                pygame.draw.line(surface,   c, (lx, ly - 5), (lx, ly + 5), 1)
                pygame.draw.circle(surface, c, (lx, ly), 2)



# ──────────────────────────────────────────────
#  SPEED READOUT
# ──────────────────────────────────────────────

def print_spd(surface, x, y):
    f = custom_font(12)
    lbl = f.render("SPEED", True, HUD_DIM)
    surface.blit(lbl, (x, y))


def draw_speed(surface, x, y, current_speed):
    spd = int(current_speed)
    f = custom_font(14)
    col_speed = HUD_GREEN
    lbl = f.render(f"{spd:4d}", True, col_speed)
    surface.blit(lbl, (x, y))


def print_kph(surface, x, y):
    f = custom_font(10)
    lbl = f.render("K.P.H.", True, HUD_GREEN)
    surface.blit(lbl, (x, y))

# ──────────────────────────────────────────────
#  HULL INTEGRITY BAR  (center-bottom)
# ──────────────────────────────────────────────

def draw_hull_bar(surface, W, H, player_hp, max_hp=100):
    """
    Centered at the bottom of the screen.
    Uses the custom cockpit font and HUD colour palette.
    """
    ratio = max(0.0, player_hp / max_hp)
    bar_w = 260
    bar_h = 10
    bar_x = W // 2 - bar_w // 2
    bar_y = H - 28

    # Colour shifts green → amber → red as HP drops
    if ratio > 0.5:
        col = HUD_GREEN
    elif ratio > 0.25:
        col = HUD_AMBER
    else:
        col = HUD_RED

    # Track (empty bar)
    pygame.draw.rect(surface, (20, 40, 20), (bar_x, bar_y, bar_w, bar_h),
                     border_radius=3)
    pygame.draw.rect(surface, HUD_DIM, (bar_x, bar_y, bar_w, bar_h),
                     1, border_radius=3)

    # Fill
    fill_w = int(bar_w * ratio)
    if fill_w > 0:
        pygame.draw.rect(surface, col, (bar_x, bar_y, fill_w, bar_h),
                         border_radius=3)

    # Segment tick marks at 25 / 50 / 75 %
    for pct in (0.25, 0.50, 0.75):
        tx = bar_x + int(bar_w * pct)
        pygame.draw.line(surface, (5, 5, 15), (tx, bar_y + 1), (tx, bar_y + bar_h - 1), 1)

    # Label:  "HULL"  left of bar,  "xxx%" right of bar
    f_lbl = custom_font(11)
    f_val = custom_font(11)

    lbl = f_lbl.render("HULL", True, HUD_DIM)
    val = f_val.render(f"{int(ratio * 100):3d}%", True, col)

    surface.blit(lbl, (bar_x - lbl.get_width() - 8,
                       bar_y + bar_h // 2 - lbl.get_height() // 2))
    surface.blit(val, (bar_x + bar_w + 8,
                       bar_y + bar_h // 2 - val.get_height() // 2))


# ──────────────────────────────────────────────
#  MASTER DRAW CALL
# ──────────────────────────────────────────────

# Cache the overlay so we don't recreate it every frame
_HUD_OVERLAY = None
_LAST_SIZE = (0, 0)

def draw_cockpit_hud(surface, W, H, throttle, current_speed, weapons_ready,
                     orientation=None, player_pos=None, player_vel=None,
                     enemies=None, player_hp=100, active_target=None):
    global _HUD_OVERLAY, _LAST_SIZE

    # Create it only once, or if the screen size changes
    if _HUD_OVERLAY is None or _LAST_SIZE != (W, H):
        _HUD_OVERLAY = pygame.Surface((W, H), pygame.SRCALPHA)
        _LAST_SIZE = (W, H)
    else:
        # Clear the overlay with fully transparent pixels
        _HUD_OVERLAY.fill((0, 0, 0, 0))

    cx, cy = W // 2, H // 2

    # Draw everything onto the cached transparent overlay
    draw_crosshair(_HUD_OVERLAY, cx, cy, weapons_ready)

    draw_throttle_bar(_HUD_OVERLAY, W - 40, H - 180, 140, throttle)
    print_spd(_HUD_OVERLAY, W - 130, H - 120)
    draw_speed(_HUD_OVERLAY, W - 120, H - 100, current_speed)
    print_kph(_HUD_OVERLAY, W - 110, H - 80)

    draw_hull_bar(_HUD_OVERLAY, W, H, player_hp)

    if orientation is not None:
        draw_heading_tape(_HUD_OVERLAY, cx, 30, orientation)
        draw_pitch_ladder(_HUD_OVERLAY, cx, cy, orientation)

        r_cx, r_cy, r_r = 90, H - 95, 75
        draw_radar(_HUD_OVERLAY, r_cx, r_cy, r_r, orientation,
                   player_pos or [0, 0, 0],
                   enemies or [])

        # ── Target brackets and lead indicator
        if enemies and player_pos is not None:
            draw_target_brackets(
                _HUD_OVERLAY,
                player_pos,
                player_vel or (0.0, 0.0, 0.0),
                orientation,
                enemies,
                active_target,
                W, H
            )

    # Stamp the finished semi-transparent HUD onto the game screen
    surface.blit(_HUD_OVERLAY, (0, 0))

