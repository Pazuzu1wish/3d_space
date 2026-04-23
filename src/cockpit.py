
import pygame
import math
from .math_engine import (
    get_basis_from_quat,
    get_forward_from_quat,
    quat_rotate_vec,
    quat_conjugate,
)

# ──────────────────────────────────────────────
#  COCKPIT HUD
#  - Heading Tape (Compass)
#  - Pitch Ladder
#  - 3D Radar disc with elevation ticks
#  - Throttle / speed bar
#  - Crosshair
# ──────────────────────────────────────────────

# ── Palette ───────────────────────────────────
HUD_GREEN = (0, 255, 140)
HUD_DIM = (0, 160, 90)
HUD_AMBER = (255, 180, 30)
HUD_RED = (255, 60, 60)
ALPHA_SURFACE = (0, 0, 0, 0)  # for per-surface alpha blits

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
    """Draws a fighter-style 0-360 degree horizontal compass tape at the top of the HUD."""
    forward, right, up = get_basis_from_quat(orientation)

    # Calculate heading: Z is forward, X is right in world axes.
    # atan2(X, Z) naturally maps to 0=North, 90=East, 180=South, 270=West
    heading_rad = math.atan2(forward[0], forward[2])
    heading_deg = math.degrees(heading_rad)
    if heading_deg < 0:
        heading_deg += 360

    tape_w = 400
    tape_h = 30
    x0 = cx - tape_w // 2

    # Draw semi-transparent background
    tape_surf = pygame.Surface((tape_w, tape_h), pygame.SRCALPHA)
    tape_surf.fill((0, 30, 0, 150))
    pygame.draw.rect(tape_surf, HUD_DIM, (0, 0, tape_w, tape_h), 1)
    surface.blit(tape_surf, (x0, y))

    # Center marker (triangle pointing down)
    pygame.draw.polygon(surface, HUD_GREEN, [
        (cx, y + tape_h),
        (cx - 6, y + tape_h + 6),
        (cx + 6, y + tape_h + 6)
    ])

    px_per_deg = tape_w / 60.0  # Show exactly 60 degrees of FOV
    font = custom_font(14)

    # Find the visible degree range
    start_deg = int(heading_deg - 35)
    end_deg = int(heading_deg + 35)

    for d in range(start_deg, end_deg + 1):
        if d % 5 == 0:
            diff = d - heading_deg
            sx = cx + int(diff * px_per_deg)

            # Only draw ticks that fit cleanly inside the tape
            if x0 + 2 <= sx <= x0 + tape_w - 2:
                norm_d = d % 360
                if norm_d < 0: norm_d += 360

                if norm_d % 15 == 0:
                    # Major tick + Label
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
                    # Minor tick
                    pygame.draw.line(surface, HUD_DIM, (sx, y), (sx, y + 5), 1)


# ──────────────────────────────────────────────
#  PITCH LADDER
# ──────────────────────────────────────────────

def draw_pitch_ladder(surface, cx, cy, orientation):
    """Draws HUD pitch ladder lines locked to the world horizon."""
    forward, right, up = get_basis_from_quat(orientation)

    pitch_angle = math.asin(max(-1.0, min(1.0, -forward[1])))
    roll_angle = math.atan2(right[1], up[1])

    # Pixels per radian - align with visual FOV (matches default math_engine fov=400)
    px_per_rad = 400.0

    # Rotate contrary to aircraft roll to keep the ladder parallel with the ground
    cos_r = math.cos(-roll_angle)
    sin_r = math.sin(-roll_angle)

    def rot(px, py):
        return (int(cx + px * cos_r - py * sin_r),
                int(cy + px * sin_r + py * cos_r))

    font = custom_font(12)
    gap = 40  # Clear space for the crosshair
    w = 60  # Width of the pitch ladder lines

    for deg in range(-90, 91, 10):
        # ── Horizon Line (0 degrees) ──
        if deg == 0:
            y_off = (pitch_angle - 0) * px_per_rad
            # Exclude lines completely off screen
            if abs(y_off) > 400: continue

            # Left half
            pygame.draw.line(surface, HUD_GREEN, rot(-200, y_off), rot(-gap, y_off), 2)
            # Right half
            pygame.draw.line(surface, HUD_GREEN, rot(gap, y_off), rot(200, y_off), 2)
            continue

        # ── Pitch Lines ──
        y_off = (pitch_angle - math.radians(deg)) * px_per_rad
        if abs(y_off) > 350: continue

        # Tails point toward horizon. (Sky > 0: point down. Ground < 0: point up)
        tail = 8 if deg > 0 else -8
        col = HUD_GREEN

        if deg > 0:
            # Positive pitch (Solid lines)
            # Left side
            pygame.draw.line(surface, col, rot(-(w + gap), y_off), rot(-gap, y_off), 2)
            pygame.draw.line(surface, col, rot(-(w + gap), y_off), rot(-(w + gap), y_off + tail), 2)

            # Right side
            pygame.draw.line(surface, col, rot((w + gap), y_off), rot(gap, y_off), 2)
            pygame.draw.line(surface, col, rot((w + gap), y_off), rot((w + gap), y_off + tail), 2)

        else:
            # Negative pitch (Dashed lines)
            dash_len = 12
            space = 12

            # Left side
            pygame.draw.line(surface, col, rot(-(w + gap), y_off), rot(-(w + gap), y_off + tail), 2)
            for i in range(3):
                dx1 = -(w + gap) + i * (dash_len + space)
                dx2 = dx1 + dash_len
                pygame.draw.line(surface, col, rot(dx1, y_off), rot(dx2, y_off), 2)

            # Right side
            pygame.draw.line(surface, col, rot(w + gap, y_off), rot(w + gap, y_off + tail), 2)
            for i in range(3):
                dx1 = gap + i * (dash_len + space)
                dx2 = dx1 + dash_len
                pygame.draw.line(surface, col, rot(dx1, y_off), rot(dx2, y_off), 2)

        # ── Text Labels ──
        lbl = font.render(str(abs(deg)), True, col)

        lx, ly = rot(-(w + gap + 15), y_off)
        surface.blit(lbl, (lx - lbl.get_width() // 2, ly - lbl.get_height() // 2))

        rx, ry = rot((w + gap + 15), y_off)
        surface.blit(lbl, (rx - lbl.get_width() // 2, ry - lbl.get_height() // 2))


# ──────────────────────────────────────────────
#  RADAR
# ──────────────────────────────────────────────

def draw_radar(surface, cx, cy, radius, orientation, player_pos, enemies,
               radar_range=6000):
    """Flat-disc radar with elevation ticks."""
    forward, right, up = get_basis_from_quat(orientation)

    disc = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    pygame.draw.circle(disc, (0, 30, 0, 180), (radius, radius), radius)
    pygame.draw.circle(disc, HUD_DIM, (radius, radius), radius, 1)
    pygame.draw.circle(disc, HUD_DIM, (radius, radius), radius // 2, 1)

    pygame.draw.line(disc, HUD_DIM, (radius, 0), (radius, radius * 2), 1)
    pygame.draw.line(disc, HUD_DIM, (0, radius), (radius * 2, radius), 1)
    surface.blit(disc, (cx - radius, cy - radius))

    px, py, pz = player_pos

    for e in enemies:
        dx, dy, dz = e.x - px, e.y - py, e.z - pz
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist > radar_range:
            continue

        local_x = dx * right[0] + dy * right[1] + dz * right[2]
        local_y = dx * up[0] + dy * up[1] + dz * up[2]
        local_z = dx * forward[0] + dy * forward[1] + dz * forward[2]

        scale = (radius - 6) / radar_range
        dot_x = int(local_x * scale) + cx
        dot_z = int(-local_z * scale) + cy

        ddx, ddy = dot_x - cx, dot_z - cy
        ddist = math.sqrt(ddx * ddx + ddy * ddy)
        if ddist > radius - 4:
            f = (radius - 4) / ddist
            dot_x = int(cx + ddx * f)
            dot_z = int(cy + ddy * f)

        elev_px = int(local_y * scale * 0.5)
        elev_px = max(-12, min(12, elev_px))

        color = HUD_RED if dist < radar_range * 0.3 else HUD_AMBER
        pygame.draw.circle(surface, color, (dot_x, dot_z), 3)
        if elev_px != 0:
            pygame.draw.line(surface, color,
                             (dot_x, dot_z),
                             (dot_x, dot_z - elev_px), 1)

    pygame.draw.circle(surface, HUD_GREEN, (cx, cy), 3)
    fwd_px = cy - (radius - 8)
    pygame.draw.line(surface, HUD_GREEN, (cx, cy), (cx, fwd_px), 1)

    lbl = custom_font(12).render("RADAR", True, HUD_DIM)
    surface.blit(lbl, (cx - lbl.get_width() // 2, cy + radius + 3))


# ──────────────────────────────────────────────
#  THROTTLE BAR
# ──────────────────────────────────────────────

def draw_throttle_bar(surface, x, y, h, throttle):
    w = 14
    pygame.draw.rect(surface, HUD_DIM, (x, y, w, h), 1)
    fill_h = int(h * throttle)
    if fill_h > 0:
        col = HUD_RED if throttle > 0.85 else HUD_AMBER if throttle > 0.5 else HUD_GREEN
        pygame.draw.rect(surface, col, (x, y + h - fill_h, w, fill_h))

    for pct in (0.25, 0.5, 0.75):
        ty = int(y + h * (1 - pct))
        pygame.draw.line(surface, HUD_DIM, (x - 4, ty), (x, ty), 1)

    f = custom_font(10)
    surface.blit(f.render("THR", True, HUD_GREEN), (x - 8, y - 14))
    col_throttle_per = HUD_RED if throttle > 0.85 else HUD_AMBER if throttle > 0.5 else HUD_GREEN

    surface.blit(f.render(f"{int(throttle * 100):3d}%", True, col_throttle_per),
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
#  SPEED READOUT
# ──────────────────────────────────────────────

def print_spd(surface, x, y):
    f = custom_font(12)
    lbl = f.render("SPEED", True, HUD_DIM)
    surface.blit(lbl, (x, y))


def draw_speed(surface, x, y, throttle):
    spd = int(throttle * 1500)
    f = custom_font(14)
    col_speed = HUD_RED if throttle > 0.85 else HUD_AMBER if throttle > 0.5 else HUD_GREEN
    lbl = f.render(f"{spd:4d}", True, col_speed)
    surface.blit(lbl, (x, y))


def print_kph(surface, x, y):
    f = custom_font(10)
    lbl = f.render("K.P.H.", True, HUD_GREEN)
    surface.blit(lbl, (x, y))


# ──────────────────────────────────────────────
#  MASTER DRAW CALL
# ──────────────────────────────────────────────

def draw_cockpit_hud(surface, W, H, throttle, weapons_ready,
                     orientation=None, player_pos=None, enemies=None):
    """Draws the fully modernized 3D fighter HUD."""
    cx, cy = W // 2, H // 2

    # ── Crosshair ──
    draw_crosshair(surface, cx, cy, weapons_ready)

    # ── Throttle bar & Speed ──
    draw_throttle_bar(surface, W - 40, H - 180, 140, throttle)
    print_spd(surface, W - 130, H - 120)
    draw_speed(surface, W - 120, H - 100, throttle)
    print_kph(surface, W - 110, H - 80)

    if orientation is None:
        return  # legacy fallback — skip 3D instruments

    # ── Heading Tape (Top Center) ──
    draw_heading_tape(surface, cx, 30, orientation)

    # ── Pitch Ladder (Center, locked to horizon) ──
    draw_pitch_ladder(surface, cx, cy, orientation)

    # ── Radar (Now nicely anchored in the bottom-left replacing the ball) ──
    r_cx = 90
    r_cy = H - 95
    r_r = 75
    draw_radar(surface, r_cx, r_cy, r_r, orientation,
               player_pos or [0, 0, 0],
               enemies or [])