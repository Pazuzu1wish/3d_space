"""
enhanced_cockpit_geometry.py

Retro-futurist low-poly cockpit frame implementation.

Features:
- True 3D Parallax Recessed panels.
- Directional lighting bevels.
- Slanted A-Pillar struts and canopy geometry for a deep 3D perspective effect.
- Curved glass canopy reflections.
"""

import pygame
import math
import numpy as np


def interpolate_color(val, c0, c1, c2):
    val = max(0.0, min(1.0, float(val)))
    xp = [0.0, 0.5, 1.0]
    r = int(np.interp(val, xp, [c0[0], c1[0], c2[0]]))
    g = int(np.interp(val, xp, [c0[1], c1[1], c2[1]]))
    b = int(np.interp(val, xp, [c0[2], c1[2], c2[2]]))
    if len(c0) > 3:
        a = int(np.interp(val, xp, [c0[3], c1[3], c2[3]]))
        return (r, g, b, a)
    return (r, g, b)


# ──────────────────────────────────────────────────────────────────────────────
# Palette
# ──────────────────────────────────────────────────────────────────────────────
_DARK = (4, 7, 15)
_MID = (9, 16, 28)
_LIGHT = (18, 28, 46)
_EDGE = (0, 180, 120)
_EDGE_DIM = (0, 75, 50)
_CYAN = (0, 170, 210)
_CYAN_DIM = (0, 60, 90)
_AMBER = (180, 90, 0)


# ──────────────────────────────────────────────────────────────────────────────
# Drawing Helpers
# ──────────────────────────────────────────────────────────────────────────────
def _p(surf, col, pts, width=0):
    if len(pts) >= 3:
        pygame.draw.polygon(surf, col, pts, width)


def _l(surf, col, a, b, w=1):
    pygame.draw.line(surf, col, a, b, w)


def _poly(surf, col, pts, w=1):
    for i in range(len(pts) - 1):
        _l(surf, col, pts[i], pts[i + 1], w)


def _r(surf, col, rect, width=0, br=0):
    pygame.draw.rect(surf, col, rect, width, border_radius=br)


def _c(surf, col, center, radius, width=0):
    pygame.draw.circle(surf, col, center, radius, width)


# ──────────────────────────────────────────────────────────────────────────────
# 3D Perspective Geometry Generators
# ──────────────────────────────────────────────────────────────────────────────
def _inset_panel(surf, outer_pts, inset=6,
                 outer_col=_MID,
                 inner_col=_DARK,
                 edge_col=_EDGE_DIM,
                 vp=None, depth_shift=0.035):
    """
    Creates a 3D recessed panel effect.
    Calculates parallax depth based on distance from the Vanishing Point (VP),
    and draws the inner 3D walls with faux-directional lighting.
    """
    _p(surf, outer_col, outer_pts)

    if vp is None:
        vp = (surf.get_width() // 2, surf.get_height() // 2)

    cx = sum(x for x, y in outer_pts) / len(outer_pts)
    cy = sum(y for x, y in outer_pts) / len(outer_pts)

    inner = []
    for x, y in outer_pts:
        # 1. Standard inset toward the center of the polygon
        dx, dy = cx - x, cy - y
        mag = max(1, math.hypot(dx, dy))
        ix = x + dx / mag * inset
        iy = y + dy / mag * inset

        # 2. 3D Parallax shift (push away from the center of the screen to fake depth)
        px, py = ix - vp[0], iy - vp[1]
        ix += px * depth_shift
        iy += py * depth_shift

        inner.append((ix, iy))

    # 3. Draw 3D connecting walls with directional lighting
    for i in range(len(outer_pts)):
        n_i = (i + 1) % len(outer_pts)
        p1, p2 = outer_pts[i], outer_pts[n_i]
        p3, p4 = inner[n_i], inner[i]

        # Calculate wall normal
        ex, ey = p2[0] - p1[0], p2[1] - p1[1]
        nx, ny = -ey, ex
        mag = math.hypot(nx, ny) or 1
        nx, ny = nx / mag, ny / mag

        # Directional Lighting (Top-lit)
        if ny < -0.3:  # Faces UP (catches light)
            w_col = _LIGHT
        elif ny > 0.3:  # Faces DOWN (in shadow)
            w_col = (max(0, _DARK[0] - 4), max(0, _DARK[1] - 4), max(0, _DARK[2] - 4))
        else:  # Faces SIDE (mid tone)
            w_col = (max(0, outer_col[0] - 2), max(0, outer_col[1] - 2), max(0, outer_col[2] - 2))

        _p(surf, w_col, [p1, p2, p3, p4])
        _l(surf, (0, 0, 0), p1, p4, 1)  # Corner seam

    # Floor of the recess
    _p(surf, inner_col, inner)
    _poly(surf, edge_col, inner + [inner[0]], 1)

    return inner


def _vent(surf, x, y, w, h, count=5):
    _r(surf, _MID, (x, y, w, h))
    pad = 4
    slot_h = 2
    spacing = (h - pad * 2) / count
    for i in range(count):
        sy = y + pad + i * spacing
        _r(surf, _DARK, (x + 5, sy, w - 10, slot_h))


def _hex_plate(surf, cx, cy, r, vp=None):
    pts = []
    for i in range(6):
        a = math.radians(i * 60)
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return _inset_panel(surf, pts, 5, _MID, _DARK, _EDGE_DIM, vp=vp)


# ──────────────────────────────────────────────────────────────────────────────
# Static Geometry Caching
# ──────────────────────────────────────────────────────────────────────────────
_STATIC = None
_STATIC_SIZE = (0, 0)


def _build_static(W, H):
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2
    vp = (cx, int(H * 0.45))  # Horizon slightly above center for perspective

    # =========================================================================
    # TOP FRAME (Sweeping Canopy Arch)
    # =========================================================================
    top = [
        (0, 0),
        (W, 0),
        (W, 140),  # Drops low at edges
        (W - 160, 100),  # Slants up toward center
        (cx + 260, 60),
        (cx + 100, 40),
        (cx - 100, 40),
        (cx - 260, 60),
        (160, 100),  # Slants up toward center
        (0, 140)
    ]
    _p(s, _DARK, top)

    top_inner = _inset_panel(s, [
        (12, 130),
        (150, 95),
        (cx - 250, 55),
        (cx - 95, 35),
        (cx + 95, 35),
        (cx + 250, 55),
        (W - 150, 95),
        (W - 12, 130)
    ], inset=6, outer_col=_MID, inner_col=_DARK, vp=vp)

    _poly(s, _EDGE, top_inner + [top_inner[0]], 1)

    # =========================================================================
    # LEFT STRUT (Slanted A-Pillar)
    # =========================================================================
    left_strut = [
        (0, 0),
        (180, 90),  # Meets arched canopy
        (140, 250),  # Slants aggressively to center
        (120, 400),
        (100, 500),
        (0, 500)
    ]
    _p(s, _MID, left_strut)

    outer_plate = [
        (10, 80),
        (170, 95),
        (130, 250),
        (110, 400),
        (90, 480),
        (10, 480)
    ]
    _inset_panel(s, outer_plate, 7, _MID, _DARK, _CYAN_DIM, vp=vp)
    _poly(s, _EDGE_DIM, outer_plate + [outer_plate[0]], 1)

    _hex_plate(s, 50, 390, 28, vp=vp)

    # =========================================================================
    # RIGHT STRUT (Slanted A-Pillar)
    # =========================================================================
    right_strut = [
        (W, 0),
        (W - 180, 90),
        (W - 140, 250),
        (W - 120, 400),
        (W - 100, 500),
        (W, 500)
    ]
    _p(s, _MID, right_strut)

    outer_plate_r = [
        (W - 10, 80),
        (W - 170, 95),
        (W - 130, 250),
        (W - 110, 400),
        (W - 90, 480),
        (W - 10, 480)
    ]
    _inset_panel(s, outer_plate_r, 7, _LIGHT, _MID, _EDGE_DIM, vp=vp)

    # Recessed box to house the HUD bars seamlessly
    _inset_panel(s, [(W - 25, 140), (W - 15, 350), (W - 125, 350), (W - 120, 140)], 4, vp=vp)

    _hex_plate(s, W - 50, 400, 28, vp=vp)

    # =========================================================================
    # LOWER LEFT CONSOLE (Flared outward to player)
    # =========================================================================
    left_console = [
        (0, 480),
        (100, 480),
        (150, 520),
        (220, H),  # Widens heavily at the bottom
        (0, H)
    ]
    _p(s, _DARK, left_console)

    # Deep 3D Radar Recess
    rx, ry = 90, H - 95
    # Faux 3D Cylinder by stacking circles offset towards vanishing point
    for r_step in range(80, 75, -1):
        pr_x = rx + (rx - vp[0]) * 0.005 * (80 - r_step)
        pr_y = ry + (ry - vp[1]) * 0.005 * (80 - r_step)
        _c(s, _DARK if r_step > 76 else _MID, (int(pr_x), int(pr_y)), r_step)

    for r in [37]:
        _c(s, _EDGE_DIM, (90, H - 95), r, 1)

    for a in range(0, 360, 45):
        rad = math.radians(a)
        _l(s, _EDGE_DIM, (90 + math.cos(rad) * 15, H - 95 + math.sin(rad) * 15),
           (90 + math.cos(rad) * 70, H - 95 + math.sin(rad) * 70), 1)

    for i in range(3):
        y = 500 + i * 24
        _inset_panel(s, [(42, y), (78, y), (78, y + 16), (42, y + 16)], 3, vp=vp)

    # =========================================================================
    # LOWER RIGHT CONSOLE
    # =========================================================================
    right_console = [
        (W, 480),
        (W - 100, 480),
        (W - 150, 520),
        (W - 220, H),
        (W, H)
    ]
    _p(s, _DARK, right_console)

    _vent(s, W - 155, 665, 50, 40)

    # Perspective sloped trench
    trench = [
        (W - 160, 640),
        (W - 40, 640),
        (W - 20, 720),
        (W - 190, 720)
    ]
    _inset_panel(s, trench, 8, _LIGHT, _MID, _CYAN, vp=vp)

    # =========================================================================
    # CENTER DASH (Tapering deep into screen)
    # =========================================================================
    center = [
        (160, H),
        (180, 680),
        (250, 620),
        (cx - 180, 590),
        (cx + 180, 590),
        (W - 250, 620),
        (W - 180, 680),
        (W - 160, H)
    ]
    _p(s, _MID, center)

    main_plate = [
        (230, H - 8),
        (240, 685),
        (280, 630),
        (cx - 150, 605),
        (cx + 150, 605),
        (W - 280, 630),
        (W - 240, 685),
        (W - 230, H - 8)
    ]
    _inset_panel(s, main_plate, 10, vp=vp)

    core = [
        (cx - 90, 620),
        (cx + 90, 620),
        (cx + 120, 655),
        (cx + 100, 700),
        (cx - 100, 700),
        (cx - 120, 655)
    ]
    _inset_panel(s, core, 8, _LIGHT, _DARK, _EDGE, vp=vp)

    # =========================================================================
    # GLASS CANOPY REFLECTIONS (The "Bubble" look)
    # =========================================================================
    glass_base = (200, 240, 255)

    # Main sweeping glass arch over the player's head
    _p(s, (*glass_base, 8), [
        (cx - 300, 60),
        (cx + 300, 60),
        (cx + 600, H * 0.7),
        (cx + 450, H * 0.7),
        (cx + 150, 120),
        (cx - 150, 120),
        (cx - 450, H * 0.7),
        (cx - 600, H * 0.7)
    ])

    # Diagonal side glares wrapping the struts
    _p(s, (*glass_base, 4), [
        (170, 95),
        (cx - 150, 120),
        (cx - 250, H * 0.4),
        (130, 250)
    ])

    _p(s, (*glass_base, 4), [
        (W - 170, 95),
        (cx + 150, 120),
        (cx + 250, H * 0.4),
        (W - 130, 250)
    ])

    return s


# ──────────────────────────────────────────────────────────────────────────────
# Main Public Interface
# ──────────────────────────────────────────────────────────────────────────────
def draw_cockpit_frame(
        surface,
        ticks,
        alert_active=False,
        missile_lock=False,
        hit_flash=0.0,
        explosion_glow=0.0,
        shield_charge=1.0
):
    global _STATIC, _STATIC_SIZE

    W, H = surface.get_size()
    cx = W // 2

    if _STATIC is None or _STATIC_SIZE != (W, H):
        _STATIC = _build_static(W, H)
        _STATIC_SIZE = (W, H)

    surface.blit(_STATIC, (0, 0))
    t = ticks * 0.001

    # --- DYNAMIC GLOWS AND PULSES ---

    pulse = int(140 + 60 * math.sin(t * 1.7))
    glow = (0, pulse, 120)

    # Glowing grooves matched to the new slanted perspective geometry
    left_glow = [(175, 95), (140, 250), (120, 400), (100, 480)]
    right_glow = [(W - 175, 95), (W - 140, 250), (W - 120, 400), (W - 100, 480)]

    _poly(surface, glow, left_glow, 2)
    _poly(surface, glow, right_glow, 2)

    # Top canopy pulse
    top_pulse = int(60 + 30 * math.sin(t * 1.2))
    _poly(surface, (0, top_pulse, top_pulse + 30), [
        (150, 95),
        (cx - 250, 55),
        (cx - 95, 35),
        (cx + 95, 35),
        (cx + 250, 55),
        (W - 150, 95)
    ], 2)

    # Radar sweep rings
    radar_pulse = int(70 + 50 * math.sin(t * 3.0))
    _c(surface, (0, radar_pulse, 90), (90, H - 95), 37, 1)

    # Left Console Indicator Lights
    for i in range(3):
        y = 500 + i * 24

        if shield_charge <= 0.0:
            pulse = int((math.sin(ticks * 0.015) + 1) * 127)
            bar_color = (255, pulse, pulse)
        else:
            col_green = (20, int(140 + 40 * math.sin(t * 2.0)), 60)
            col_amber = (int(180 + 40 * math.sin(t * 2.0)), int(90 + 20 * math.sin(t * 2.0)), 10)
            col_red = (min(255, 180 + int(70 * abs(math.sin(t * 5)))), 20, 10)

            red_threshold = 1.0 - (i + 1) * 0.333
            val = (shield_charge - red_threshold) / 0.333
            bar_color = interpolate_color(val, col_red, col_amber, col_green)

        _r(surface, bar_color, (50, y + 3, 20, 8), br=2)

    # Hit and explosion flashes
    if hit_flash > 0.01:
        fs = pygame.Surface((W, H), pygame.SRCALPHA)
        fs.fill((255, 0, 0, int(hit_flash * 80)))
        surface.blit(fs, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    if explosion_glow > 0.01:
        gs = pygame.Surface((W, H), pygame.SRCALPHA)
        a = int(explosion_glow * 60)
        gs.fill((a, a // 3, 0, a))
        surface.blit(gs, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)