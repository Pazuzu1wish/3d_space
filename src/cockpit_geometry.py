"""
cockpit_geometry.py
Pre-baked low-poly retro-futurist cockpit geometry.

Inspired by Descent, Terminal Velocity, Elite — late DOS-era 3D space sim aesthetic.
Renders as flat-shaded dark polygons with neon cyan/green emissive outlines.
Designed to frame the 1280x760 viewport without obscuring the combat center.

Architecture:
  _build_static(W, H) -> Surface   -- called once, bakes all dark fills + edges
  draw_cockpit_frame(surface, ticks, alert_active, hit_flash) -- blit static + animate
"""

import pygame
import math

# ── Palette ───────────────────────────────────────────────────────────────────
_DARK       = (5,   8,  18)    # deepest panel fill
_MID        = (9,  15,  28)    # mid panel
_LIGHT      = (13, 22,  40)    # inset face / lighter accent
_STRUT      = (7,  12,  24)    # canopy strut body

_BRIGHT     = (0,  210, 120)   # primary emissive edge (green)
_DIM        = (0,   75,  45)   # secondary / interior edge
_CYAN       = (0,  175, 215)   # instrument housing accent
_AMBER      = (180, 90,   0)   # warning accent
_RED_IND    = (220,  25,  10)  # indicator ON
_RED_OFF    = ( 55,   8,   5)  # indicator OFF

# ── Helpers ───────────────────────────────────────────────────────────────────
def _p(surf, col, pts, width=0):
    if len(pts) >= 3:
        pygame.draw.polygon(surf, col, pts, width)

def _l(surf, col, a, b, w=1):
    pygame.draw.line(surf, col, a, b, w)

def _r(surf, col, rect, width=0, br=0):
    pygame.draw.rect(surf, col, rect, width, border_radius=br)

def _c(surf, col, center, radius, width=0):
    pygame.draw.circle(surf, col, center, radius, width)

def _polyline(surf, col, pts, w=1):
    for i in range(len(pts) - 1):
        _l(surf, col, pts[i], pts[i+1], w)

# ── Static surface cache ───────────────────────────────────────────────────────
_STATIC: pygame.Surface | None = None
_STATIC_SIZE = (0, 0)


def _build_static(W: int, H: int) -> pygame.Surface:
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    cx = W // 2

    # ── 1. TOP FRAME ──────────────────────────────────────────────────────────
    # Dark bar along the top with a notch cut out over the heading tape area
    top_pts = [
        (0, 0), (W, 0), (W, 60),
        (1060, 60), (990, 75),
        (cx + 225, 75), (cx + 225, 66),
        (cx - 225, 66), (cx - 225, 75),
        (290, 75), (220, 60),
        (0, 60),
    ]
    _p(s, _DARK, top_pts)
    # bottom inner edge of top frame
    _l(s, _BRIGHT, (0, 59), (220, 59), 1)
    _l(s, _BRIGHT, (220, 59), (290, 74), 1)
    _l(s, _DIM,    (290, 74), (cx - 225, 74), 1)
    _l(s, _DIM,    (cx - 225, 74), (cx - 225, 65), 1)
    _l(s, _DIM,    (cx - 225, 65), (cx + 225, 65), 1)
    _l(s, _DIM,    (cx + 225, 65), (cx + 225, 74), 1)
    _l(s, _DIM,    (cx + 225, 74), (990, 74), 1)
    _l(s, _BRIGHT, (990, 74), (1060, 59), 1)
    _l(s, _BRIGHT, (1060, 59), (W, 59), 1)

    # SYSTEMS / NML / WPN strip (top-left corner panel)
    sys_strip = [(0, 0), (240, 0), (240, 60), (0, 60)]
    _p(s, (6, 14, 10), sys_strip)
    _l(s, _BRIGHT, (240, 0), (240, 60), 1)
    _l(s, _BRIGHT, (0, 60), (240, 60), 1)
    # Button outlines
    for bx in (48, 100, 155):
        _r(s, (10, 25, 16), (bx - 22, 8, 44, 24), 1, 2)
        _r(s, _DIM, (bx - 22, 8, 44, 24), 1, 2)

    # ALERT strip (top-right corner panel)
    alert_strip = [(W - 240, 0), (W, 0), (W, 60), (W - 240, 60)]
    _p(s, (16, 5, 5), alert_strip)
    _l(s, _AMBER, (W - 240, 0), (W - 240, 60), 1)
    _l(s, _AMBER, (W - 240, 60), (W, 60), 1)
    # Alert button boxes: RDR LOCK, MISSILE, WARN
    for bx in (W - 200, W - 140, W - 68):
        _r(s, (28, 8, 6), (bx - 26, 7, 52, 26), 1, 2)
        _r(s, _AMBER, (bx - 26, 7, 52, 26), 1, 2)

    # ── 2. LEFT CANOPY STRUT ──────────────────────────────────────────────────
    left_strut = [
        (0, 0), (242, 0), (242, 60),
        (196, 115), (160, 290),
        (148, 420), (118, 450),
        (0, 450),
    ]
    _p(s, _STRUT, left_strut)

    # Inward-facing bright edge (viewport boundary)
    strut_L_edge = [(242, 60), (196, 115), (160, 290), (148, 420), (118, 450)]
    _polyline(s, _BRIGHT, strut_L_edge, 2)

    # Strut surface panel lines
    for fx in (42, 118, 192):
        _l(s, _DIM, (fx, 0), (max(0, fx - 8), 60), 1)

    # Horizontal cross-rib
    rib_L = [(0, 195), (168, 170), (178, 145), (172, 195), (0, 220)]
    _p(s, _MID, rib_L)
    _l(s, _DIM, (0, 195), (168, 170), 1)
    _l(s, _DIM, (0, 220), (172, 195), 1)

    # ── 3. RIGHT CANOPY STRUT (mirror) ───────────────────────────────────────
    right_strut = [
        (W, 0), (W - 242, 0), (W - 242, 60),
        (W - 196, 115), (W - 160, 290),
        (W - 148, 420), (W - 118, 450),
        (W, 450),
    ]
    _p(s, _STRUT, right_strut)

    strut_R_edge = [(W - 242, 60), (W - 196, 115), (W - 160, 290), (W - 148, 420), (W - 118, 450)]
    _polyline(s, _BRIGHT, strut_R_edge, 2)

    for fx in (42, 118, 192):
        _l(s, _DIM, (W - fx, 0), (W - max(0, fx - 8), 60), 1)

    rib_R = [(W, 195), (W - 168, 170), (W - 178, 145), (W - 172, 195), (W, 220)]
    _p(s, _MID, rib_R)
    _l(s, _DIM, (W, 195), (W - 168, 170), 1)
    _l(s, _DIM, (W, 220), (W - 172, 195), 1)

    # ── 4. LEFT LOWER CONSOLE ─────────────────────────────────────────────────
    left_console = [
        (0, 450), (118, 450),
        (148, 490), (170, 548),
        (182, 628), (185, 695), (182, H),
        (0, H),
    ]
    _p(s, _DARK, left_console)

    lc_inner = [(118, 450), (148, 490), (170, 548), (182, 628), (185, 695)]
    _polyline(s, _BRIGHT, lc_inner, 2)

    # Top section bar
    _p(s, _MID, [(2, 452), (116, 452), (144, 488), (2, 488)])
    _l(s, _DIM, (2, 488), (144, 488), 1)

    # Dodge bar housing panel
    _p(s, _LIGHT, [(4, 492), (78, 492), (78, 564), (4, 564)])
    _r(s, _DIM, (4, 492, 74, 72), 1)

    # Radar housing (octagonal inset)
    radar_panel = [
        (4, 570), (170, 570),
        (178, 585), (178, 715),
        (170, 728), (4, 728),
    ]
    _p(s, _MID, radar_panel)
    _polyline(s, _CYAN, radar_panel + [radar_panel[0]], 1)

    # Radar disc dark recess
    _c(s, _DARK, (90, 650), 72)
    _c(s, _DIM,  (90, 650), 72, 1)

    # NSPA cardinal ring outline inside radar
    _c(s, (0, 40, 25), (90, 650), 38, 1)

    # System status panel (PWR/ENG/WEP/SHD labels column)
    _p(s, _MID, [(188, 570), (258, 570), (262, 590), (262, 730), (188, 730)])
    _l(s, _DIM, (188, 570), (258, 570), 1)
    _l(s, _DIM, (258, 570), (262, 590), 1)
    _l(s, _DIM, (262, 590), (262, 730), 1)
    _l(s, _DIM, (262, 730), (188, 730), 1)
    # Label row dividers
    for ry in (602, 634, 666, 698):
        _l(s, _DIM, (190, ry), (260, ry), 1)

    # Thrust/boost/manvr bottom strip
    _p(s, _MID, [(4, 732), (182, 732), (182, H - 2), (4, H - 2)])
    _l(s, _DIM, (4, 732), (182, 732), 1)

    # Red indicator lights left
    for iy in (498, 518, 538):
        _r(s, _RED_OFF, (52, iy - 5, 18, 10), 0, 2)
        _r(s, _DIM,    (52, iy - 5, 18, 10), 1, 2)

    # ── 5. RIGHT LOWER CONSOLE (mirror) ──────────────────────────────────────
    right_console = [
        (W, 450), (W - 118, 450),
        (W - 148, 490), (W - 170, 548),
        (W - 182, 628), (W - 185, 695), (W - 182, H),
        (W, H),
    ]
    _p(s, _DARK, right_console)

    rc_inner = [(W - 118, 450), (W - 148, 490), (W - 170, 548), (W - 182, 628), (W - 185, 695)]
    _polyline(s, _BRIGHT, rc_inner, 2)

    _p(s, _MID, [(W - 2, 452), (W - 116, 452), (W - 144, 488), (W - 2, 488)])
    _l(s, _DIM, (W - 2, 488), (W - 144, 488), 1)

    # Throttle housing panel
    _p(s, _LIGHT, [(W - 4, 492), (W - 78, 492), (W - 78, 564), (W - 4, 564)])
    _r(s, _DIM, (W - 78, 492, 74, 72), 1)

    # Speed / status display housing
    spd_panel = [
        (W - 4, 570), (W - 170, 570),
        (W - 178, 585), (W - 178, 715),
        (W - 170, 728), (W - 4, 728),
    ]
    _p(s, _MID, spd_panel)
    _polyline(s, _CYAN, spd_panel + [spd_panel[0]], 1)

    # FUEL/TEMP/OXY/ELEC labels column
    _p(s, _MID, [(W - 258, 570), (W - 188, 570), (W - 188, 730), (W - 262, 730), (W - 262, 590)])
    _l(s, _DIM, (W - 258, 570), (W - 188, 570), 1)
    _l(s, _DIM, (W - 188, 570), (W - 188, 730), 1)
    _l(s, _DIM, (W - 188, 730), (W - 262, 730), 1)
    _l(s, _DIM, (W - 262, 730), (W - 262, 590), 1)
    for ry in (602, 634, 666, 698):
        _l(s, _DIM, (W - 260, ry), (W - 190, ry), 1)

    # Bottom right controls strip
    _p(s, _MID, [(W - 182, 732), (W - 4, 732), (W - 4, H - 2), (W - 182, H - 2)])
    _l(s, _DIM, (W - 182, 732), (W - 4, 732), 1)
    # LIGHTS/HUD/SCAN/CMDS button row
    for bx in (W - 165, W - 122, W - 79, W - 36):
        _r(s, _DARK, (bx - 18, 736, 36, 18), 1, 2)
        _r(s, _DIM,  (bx - 18, 736, 36, 18), 1, 2)

    # Red indicator lights right
    for iy in (498, 518, 538):
        _r(s, _RED_OFF, (W - 70, iy - 5, 18, 10), 0, 2)
        _r(s, _DIM,    (W - 70, iy - 5, 18, 10), 1, 2)

    # ── 6. CENTER DASHBOARD ────────────────────────────────────────────────────
    # Connecting panel between left & right consoles at the bottom
    center_dash = [
        (182, H), (182, 700), (188, 680), (200, 650),
        (278, 610), (cx - 145, 590),
        (cx - 145, 578), (cx + 145, 578), (cx + 145, 590),
        (W - 278, 610), (W - 200, 650), (W - 188, 680), (W - 182, 700),
        (W - 182, H),
    ]
    _p(s, _DARK, center_dash)

    # Inner bright edge
    cd_edge = [
        (188, 680), (200, 650), (278, 610),
        (cx - 145, 590), (cx - 145, 578),
        (cx + 145, 578), (cx + 145, 590),
        (W - 278, 610), (W - 200, 650), (W - 188, 680),
    ]
    _polyline(s, _BRIGHT, cd_edge, 2)

    # Hull bar housing recess
    _p(s, _LIGHT, [(cx - 155, 580), (cx + 155, 580), (cx + 155, 594), (cx - 155, 594)])
    _l(s, _DIM, (cx - 155, 580), (cx + 155, 580), 1)
    _l(s, _DIM, (cx - 155, 594), (cx + 155, 594), 1)

    # Gravity / ship silhouette housing
    sil_pts = [
        (cx - 64, 610), (cx + 64, 610),
        (cx + 74, 636), (cx + 64, 665),
        (cx - 64, 665), (cx - 74, 636),
    ]
    _p(s, _MID, sil_pts)
    _polyline(s, _DIM, sil_pts + [sil_pts[0]], 1)

    # Gravity readout inset panel
    _p(s, _LIGHT, [(cx - 68, 668), (cx + 68, 668), (cx + 68, 686), (cx - 68, 686)])
    _l(s, _DIM, (cx - 68, 668), (cx + 68, 668), 1)
    _l(s, _DIM, (cx - 68, 686), (cx + 68, 686), 1)

    # ── 7. STRUCTURAL SEAMS & DETAIL LINES ───────────────────────────────────
    # Horizontal panel seam on left console
    _l(s, _DIM, (0, 450), (118, 450), 1)
    # Horizontal panel seam on right console
    _l(s, _DIM, (W, 450), (W - 118, 450), 1)

    # Left strut bottom horizontal seam
    _l(s, _DIM, (0, 440), (118, 440), 1)
    _l(s, _DIM, (W, 440), (W - 118, 440), 1)

    # Panel corner brackets — left console upper area
    for (x1, y1, x2, y2) in [(4, 455, 14, 455), (4, 455, 4, 465)]:
        _l(s, _BRIGHT, (x1, y1), (x2, y2), 1)
    for (x1, y1, x2, y2) in [(W - 4, 455, W - 14, 455), (W - 4, 455, W - 4, 465)]:
        _l(s, _BRIGHT, (x1, y1), (x2, y2), 1)

    return s


# ── Ship silhouette (drawn separately for clarity) ────────────────────────────
def _draw_ship_silhouette(surf: pygame.Surface, cx: int, cy: int):
    """Draw a simple top-down ship silhouette glyph."""
    col = _DIM
    # Body
    body = [(cx, cy - 18), (cx + 8, cy + 8), (cx, cy + 4), (cx - 8, cy + 8)]
    _p(surf, col, body, 1)
    # Wings
    wing_L = [(cx - 8, cy + 2), (cx - 22, cy + 12), (cx - 14, cy + 14), (cx - 6, cy + 8)]
    _p(surf, col, wing_L, 1)
    wing_R = [(cx + 8, cy + 2), (cx + 22, cy + 12), (cx + 14, cy + 14), (cx + 6, cy + 8)]
    _p(surf, col, wing_R, 1)


# ── Static surface cache ───────────────────────────────────────────────────────
_LABEL_CACHE = {}

def _cached_label(font, text, color):
    key = (text, color)
    if key not in _LABEL_CACHE:
        _LABEL_CACHE[key] = font.render(text, True, color)
    return _LABEL_CACHE[key]

# ── Public draw function ───────────────────────────────────────────────────────
def draw_cockpit_frame(
    surface: pygame.Surface,
    ticks: int,
    alert_active: bool = False,
    missile_lock: bool = False,
    hit_flash: float = 0.0,
    explosion_glow: float = 0.0,
):
    """
    Blit the static cockpit geometry and render all animated elements.

    Parameters
    ----------
    surface       : target pygame surface (game screen or hud overlay)
    ticks         : pygame.time.get_ticks() — drives animations
    alert_active  : lights the WARN indicator
    missile_lock  : lights the RDR LOCK indicator
    hit_flash     : 0.0-1.0 intensity of red damage flash
    explosion_glow: 0.0-1.0 ambient glow intensity from nearby explosions
    """
    global _STATIC, _STATIC_SIZE
    W, H = surface.get_size()
    cx = W // 2

    # (Re)bake static surface if needed
    if _STATIC is None or _STATIC_SIZE != (W, H):
        _STATIC = _build_static(W, H)
        _STATIC_SIZE = (W, H)

    # Blit the fully-baked cockpit base
    surface.blit(_STATIC, (0, 0))

    t = ticks * 0.001  # seconds

    # ── Animated: emissive edge glow pulse ────────────────────────────────────
    glow_alpha = int(40 + 30 * math.sin(t * 1.2))
    glow_col = (0, min(255, 210 + glow_alpha // 2), min(255, 120 + glow_alpha // 2))

    # Pulse on the inner strut edges (just re-draw the key lines slightly brighter)
    strut_L = [(242, 60), (196, 115), (160, 290), (148, 420), (118, 450)]
    strut_R = [(W - 242, 60), (W - 196, 115), (W - 160, 290), (W - 148, 420), (W - 118, 450)]
    _polyline(surface, glow_col, strut_L, 1)
    _polyline(surface, glow_col, strut_R, 1)

    # ── Animated: instrument panel indicator lights ───────────────────────────
    # Left console red indicators (static on for now — pulse slowly)
    ind_pulse = int(128 + 100 * math.sin(t * 2.5))
    ind_col = (min(255, 180 + ind_pulse // 5), 20, 10)
    for iy in (498, 518, 538):
        _r(surface, ind_col, (52, iy - 5, 18, 10), 0, 2)

    # Right console indicators
    for iy in (498, 518, 538):
        _r(surface, ind_col, (W - 70, iy - 5, 18, 10), 0, 2)

    # ── Animated: SYSTEMS / NML / WPN button labels ───────────────────────────
    label_col = _BRIGHT
    f10 = pygame.font.Font(None, 14)
    for txt, bx in [("SYSTEMS", 48), ("NML", 100), ("WPN", 155)]:
        lbl = _cached_label(f10, txt, label_col)
        surface.blit(lbl, (bx - lbl.get_width() // 2, 13))

    # ── Animated: ALERT button labels ─────────────────────────────────────────
    warn_col = _AMBER
    if alert_active:
        pulse_a = int(180 + 75 * abs(math.sin(t * 4.0)))
        warn_col = (min(255, pulse_a + 20), 90, 0)
    if missile_lock:
        lock_col = (min(255, int(160 + 95 * abs(math.sin(t * 5.0)))), 20, 10)
    else:
        lock_col = _AMBER

    for txt, bx, col in [("RDR\nLOCK", W - 200, lock_col),
                          ("MISSILE",  W - 140, warn_col),
                          ("WARN",     W - 68,  warn_col if alert_active else _AMBER)]:
        lines = txt.split("\n")
        for li, line in enumerate(lines):
            lbl = _cached_label(f10, line, col)
            y_off = 10 + li * 12
            surface.blit(lbl, (bx - lbl.get_width() // 2, y_off))

    # ── Animated: PWR/ENG/WEP/SHD system label column ────────────────────────
    for i, txt in enumerate(["PWR", "ENG", "WEP", "SHD"]):
        ry = 588 + i * 32
        lbl = _cached_label(f10, txt, _BRIGHT)
        surface.blit(lbl, (194, ry + 4))
        # Small status bar next to each label
        bar_x = 220
        _r(surface, _DIM, (bar_x, ry + 6, 32, 8), 0, 1)
        _r(surface, _BRIGHT, (bar_x, ry + 6, 32, 8), 1, 1)

    # ── Animated: FUEL/TEMP/OXY/ELEC column ──────────────────────────────────
    for i, txt in enumerate(["FUEL", "TEMP", "OXY", "ELEC"]):
        ry = 588 + i * 32
        lbl = _cached_label(f10, txt, _BRIGHT)
        surface.blit(lbl, (W - 256, ry + 4))
        bar_x = W - 222
        _r(surface, _DIM, (bar_x, ry + 6, 32, 8), 0, 1)
        _r(surface, _BRIGHT, (bar_x, ry + 6, 32, 8), 1, 1)

    # ── Animated: bottom-right control buttons ────────────────────────────────
    for txt, bx in [("LIGHTS", W - 165), ("HUD+", W - 122), ("SCAN", W - 79), ("CMDS", W - 36)]:
        lbl = _cached_label(f10, txt, _DIM)
        surface.blit(lbl, (bx - lbl.get_width() // 2, 739))

    # ── Animated: THRUST/BOOST/MANVR bottom-left labels ──────────────────────
    for i, txt in enumerate(["THRUST", "BOOST", "MANVR"]):
        lbl = _cached_label(f10, txt, _DIM)
        surface.blit(lbl, (8, H - 46 + i * 14))

    # ── Ship silhouette ───────────────────────────────────────────────────────
    _draw_ship_silhouette(surface, cx, 640)

    # ── Dynamic: hit flash tint on panels ────────────────────────────────────
    if hit_flash > 0.01:
        flash_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        alpha = int(hit_flash * 60)
        flash_surf.fill((200, 0, 0, alpha))
        surface.blit(flash_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Dynamic: explosion ambient glow ──────────────────────────────────────
    if explosion_glow > 0.01:
        glow_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        ag = int(explosion_glow * 45)
        glow_surf.fill((ag, ag // 3, 0, ag))
        surface.blit(glow_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    # ── RDR label under radar housing ────────────────────────────────────────
    rdr_lbl = _cached_label(f10, "RDR", _BRIGHT)
    surface.blit(rdr_lbl, (90 - rdr_lbl.get_width() // 2, H - 28))

    # ── DCH label above dodge bar ─────────────────────────────────────────────
    dch_lbl = _cached_label(f10, "DCH", _BRIGHT)
    surface.blit(dch_lbl, (8, 480))

    # ── THR label above throttle bar ──────────────────────────────────────────
    thr_lbl = _cached_label(f10, "THR", _BRIGHT)
    surface.blit(thr_lbl, (W - 70, 480))
