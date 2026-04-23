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
#  - Attitude Indicator (artificial horizon)
#  - 3D Radar disc with elevation ticks
#  - Throttle / speed bar
#  - Crosshair
# ──────────────────────────────────────────────

# ── Palette ───────────────────────────────────
HUD_GREEN     = (0,   255, 140)
HUD_DIM       = (0,   160,  90)
HUD_AMBER     = (255, 180,  30)
HUD_RED       = (255,  60,  60)
HUD_SKY       = (60,  140, 220)
HUD_GROUND    = (160, 100,  40)
ALPHA_SURFACE = (0, 0, 0, 0)   # for per-surface alpha blits

_FONT_CACHE = {}

# def _font(size):
#     if size not in _FONT_CACHE:
#         try:
#             _FONT_CACHE[size] = pygame.font.SysFont("Courier New", size, bold=True)
#         except Exception:
#             _FONT_CACHE[size] = pygame.font.SysFont(None, size)
#     return _FONT_CACHE[size]

def custom_font(size):
    if size not in _FONT_CACHE:
        try:
            _FONT_CACHE[size] = pygame.font.Font('./assets/fonts/interdictionexpand.ttf', size)
        except Exception:
            _FONT_CACHE[size] = pygame.font.SysFont(None, size)
    return _FONT_CACHE[size]


# ──────────────────────────────────────────────
#  ATTITUDE INDICATOR
# ──────────────────────────────────────────────

def draw_attitude_indicator(surface, cx, cy, radius, orientation):
    """Draw a classic artificial-horizon / attitude indicator.

    cx, cy    – centre of the instrument on `surface`
    radius    – pixel radius of the circular gauge
    orientation – player quaternion
    """
    forward, right, up = get_basis_from_quat(orientation)

    # ── Pitch angle: angle between forward and the world horizontal plane ──
    # forward.y is sin(pitch) in world space
    pitch_angle = math.asin(max(-1.0, min(1.0, -forward[1])))

    # ── Roll angle: how much the cockpit's 'up' is tilted from world vertical ──
    # Project world-up (0,1,0) into the camera's right/up plane.
    # up_world dot camera_right  → sin(roll)
    # up_world dot camera_up     → cos(roll)
    roll_sin = up[0] * right[0] + up[1] * right[1] + up[2] * right[2]
    roll_cos = up[0] * up[0]    + up[1] * up[1]    + up[2] * up[2]
    # Simpler: roll is the angle of the ship's up-vector in the camera plane
    roll_angle = math.atan2(right[1], up[1])   # bank angle in world Y

    # ── Draw clipping circle ──
    clip_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
    pygame.draw.circle(clip_surf, (0, 0, 0, 0), (radius, radius), radius)

    # ── Sky / ground split ──
    # The horizon line is offset vertically by pitch and rotated by roll.
    pitch_px = int(pitch_angle * radius * 1.8)   # scale pitch to pixels

    # Draw sky (top half relative to horizon)
    sky_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
    # Fill entire thing with ground colour first, then overdraw sky above horizon
    pygame.draw.circle(sky_surf, (*HUD_GROUND, 160), (radius, radius), radius)

    # Build horizon polygon (rotated by roll, offset by pitch)
    cos_r = math.cos(roll_angle)
    sin_r = math.sin(roll_angle)

    def rot(x, y):
        return (int(x * cos_r - y * sin_r + radius),
                int(x * sin_r + y * cos_r + radius + pitch_px))

    # Sky polygon: a big rect above the tilted horizon line
    hw = radius * 3
    hh = radius * 3
    sky_pts = [rot(-hw, -hh), rot(hw, -hh), rot(hw, 0), rot(-hw, 0)]
    pygame.draw.polygon(sky_surf, (*HUD_SKY, 160), sky_pts)

    # Clip to circle
    mask = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (radius, radius), radius)
    sky_surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surface.blit(sky_surf, (cx - radius, cy - radius))

    # ── Pitch ladder lines ──
    for deg in range(-90, 91, 10):
        if deg == 0:
            continue
        rad_offset = int(math.radians(deg) * radius * 1.8)
        lw = radius // 3 if deg % 30 == 0 else radius // 5
        col = HUD_DIM
        # line endpoints in horizon-local space
        lx0, ly0 = rot(-lw, rad_offset)
        lx1, ly1 = rot( lw, rad_offset)
        # clip manually to circle
        if math.hypot(lx0 - radius, ly0 - radius) < radius or \
           math.hypot(lx1 - radius, ly1 - radius) < radius:
            pygame.draw.line(surface, col,
                             (cx - radius + lx0, cy - radius + ly0),
                             (cx - radius + lx1, cy - radius + ly1), 1)
            if deg % 30 == 0:
                txt = custom_font(12).render(f"{abs(deg)}", True, col)
                surface.blit(txt, (cx - radius + lx1 + 3, cy - radius + ly1 - 5))

    # ── Horizon line (bright) ──
    hx0, hy0 = rot(-radius, 0)
    hx1, hy1 = rot( radius, 0)
    pygame.draw.line(surface, HUD_GREEN,
                     (cx - radius + hx0, cy - radius + hy0),
                     (cx - radius + hx1, cy - radius + hy1), 2)

    # ── Outer ring ──
    pygame.draw.circle(surface, HUD_GREEN, (cx, cy), radius, 2)

    # ── Roll arc tick marks at top ──
    for tick_deg in (-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60):
        a = math.radians(tick_deg - 90)
        inner = radius - (8 if tick_deg % 30 == 0 else 4)
        ox0 = int(math.cos(a) * inner)       + cx
        oy0 = int(math.sin(a) * inner)       + cy
        ox1 = int(math.cos(a) * (radius-1))  + cx
        oy1 = int(math.sin(a) * (radius-1))  + cy
        pygame.draw.line(surface, HUD_GREEN, (ox0, oy0), (ox1, oy1), 1)

    # ── Roll pointer (triangle at top, rotated by roll) ──
    ptr_angle = math.radians(-90) - roll_angle
    pa = ptr_angle
    tip_r = radius - 2
    wing_r = radius - 10
    pts = [
        (cx + int(math.cos(pa)           * tip_r),
         cy + int(math.sin(pa)           * tip_r)),
        (cx + int(math.cos(pa + 0.15)    * wing_r),
         cy + int(math.sin(pa + 0.15)    * wing_r)),
        (cx + int(math.cos(pa - 0.15)    * wing_r),
         cy + int(math.sin(pa - 0.15)    * wing_r)),
    ]
    pygame.draw.polygon(surface, HUD_AMBER, pts)

    # ── Fixed aircraft symbol (centre) ──
    pygame.draw.line(surface, HUD_AMBER, (cx - 20, cy), (cx - 6, cy), 2)
    pygame.draw.line(surface, HUD_AMBER, (cx + 6,  cy), (cx + 20, cy), 2)
    pygame.draw.circle(surface, HUD_AMBER, (cx, cy), 4, 2)


# ──────────────────────────────────────────────
#  RADAR
# ──────────────────────────────────────────────

def draw_radar(surface, cx, cy, radius, orientation, player_pos, enemies,
               radar_range=6000):
    """Flat-disc radar with elevation ticks.

    Enemies are projected into the ship's local XZ plane (horizontal disc).
    A small vertical tick above/below the dot shows elevation.
    """
    forward, right, up = get_basis_from_quat(orientation)

    # Background disc
    disc = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
    pygame.draw.circle(disc, (0, 30, 0, 180), (radius, radius), radius)
    pygame.draw.circle(disc, HUD_DIM, (radius, radius), radius,       1)
    pygame.draw.circle(disc, HUD_DIM, (radius, radius), radius // 2,  1)
    # Cross-hairs
    pygame.draw.line(disc, HUD_DIM, (radius, 0), (radius, radius*2), 1)
    pygame.draw.line(disc, HUD_DIM, (0, radius), (radius*2, radius), 1)
    surface.blit(disc, (cx - radius, cy - radius))

    px, py, pz = player_pos

    for e in enemies:
        # Vector from player to enemy
        dx, dy, dz = e.x - px, e.y - py, e.z - pz
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if dist > radar_range:
            continue

        # Project onto ship-local axes
        local_x =  dx * right[0]   + dy * right[1]   + dz * right[2]
        local_y =  dx * up[0]      + dy * up[1]       + dz * up[2]
        local_z =  dx * forward[0] + dy * forward[1]  + dz * forward[2]

        # Normalise to radar disc (use XZ = right/forward plane)
        scale = (radius - 6) / radar_range
        dot_x = int(local_x * scale) + cx
        dot_z = int(-local_z * scale) + cy   # forward = up on disc

        # Clamp to disc
        ddx, ddy = dot_x - cx, dot_z - cy
        ddist = math.sqrt(ddx*ddx + ddy*ddy)
        if ddist > radius - 4:
            f = (radius - 4) / ddist
            dot_x = int(cx + ddx * f)
            dot_z = int(cy + ddy * f)

        # Elevation tick (local_y)
        elev_px = int(local_y * scale * 0.5)
        elev_px = max(-12, min(12, elev_px))

        color = HUD_RED if dist < radar_range * 0.3 else HUD_AMBER
        pygame.draw.circle(surface, color, (dot_x, dot_z), 3)
        if elev_px != 0:
            pygame.draw.line(surface, color,
                             (dot_x, dot_z),
                             (dot_x, dot_z - elev_px), 1)

    # Centre blip (player)
    pygame.draw.circle(surface, HUD_GREEN, (cx, cy), 3)
    # Forward tick
    fwd_px = cy - (radius - 8)
    pygame.draw.line(surface, HUD_GREEN, (cx, cy), (cx, fwd_px), 1)

    # Label
    lbl = custom_font(12).render("RADAR", True, HUD_DIM)
    surface.blit(lbl, (cx - lbl.get_width()//2, cy + radius + 3))


# ──────────────────────────────────────────────
#  THROTTLE BAR
# ──────────────────────────────────────────────

def draw_throttle_bar(surface, x, y, h, throttle):
    w = 14
    # Background
    pygame.draw.rect(surface, HUD_DIM, (x, y, w, h), 1)
    # Fill
    fill_h = int(h * throttle)
    if fill_h > 0:
        col = HUD_RED if throttle > 0.85 else HUD_AMBER if throttle > 0.5 else HUD_GREEN
        pygame.draw.rect(surface, col, (x, y + h - fill_h, w, fill_h))
    # Tick marks
    for pct in (0.25, 0.5, 0.75):
        ty = int(y + h * (1 - pct))
        pygame.draw.line(surface, HUD_DIM, (x - 4, ty), (x, ty), 1)
    # Labels
    f = custom_font(10)
    surface.blit(f.render("THR", True, HUD_GREEN), (x - 8, y - 14))
    col_throttle_per = HUD_RED if throttle > 0.85 else HUD_AMBER if throttle > 0.5 else HUD_GREEN

    surface.blit(f.render(f"{int(throttle*100):3d}%", True, col_throttle_per),
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
    pygame.draw.line(surface, col, (cx + gap, cy),       (cx + arm + gap, cy), thick)
    pygame.draw.line(surface, col, (cx, cy - arm - gap), (cx, cy - gap), thick)
    pygame.draw.line(surface, col, (cx, cy + gap),       (cx, cy + arm + gap), thick)
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
    """Drop-in replacement for the old draw_cockpit_hud.

    New keyword args:
      orientation – quaternion (required for attitude indicator & radar)
      player_pos  – [x,y,z] list
      enemies     – list of Enemy objects (for radar)
    """
    cx, cy = W // 2, H // 2

    # ── Crosshair (always) ──
    draw_crosshair(surface, cx, cy, weapons_ready)

    # ── Throttle bar (right side) ──
    draw_throttle_bar(surface, W - 40, H - 180, 140, throttle)

    # ── Speed readout ──
    print_spd(surface, W - 130, H - 120)
    draw_speed(surface, W - 120, H - 100, throttle)
    print_kph(surface, W -110, H - 80)

    if orientation is None:
        return   # legacy fallback — skip 3D instruments

    # ── Attitude indicator (bottom-left) ──
    ai_cx = 90
    ai_cy = H - 95
    ai_r  = 70
    draw_attitude_indicator(surface, ai_cx, ai_cy, ai_r, orientation)

    # ── Radar (next to altitude indicator) ──
    r_cx = W // 4 + 30
    r_cy = H - 100
    r_r  = 75
    draw_radar(surface, r_cx, r_cy, r_r, orientation,
               player_pos or [0,0,0],
               enemies   or [])