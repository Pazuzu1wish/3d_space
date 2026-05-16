"""
enhanced_cockpit_geometry.py

Retro-futurist low-poly cockpit frame implementation.

Features:
- Recessed panel geometry for depth.
- Layered armor plating aesthetics.
- Inset bevels and emissive groove channels for a high-tech look.
- Industrial surface segmentation.
- Geometry-first visual language (no baked text labels).

Aesthetics:
- Inspired by Descent, Terminal Velocity, and Freespace.
- Flat-shaded software-rendered polygon look.
- Designed for integration with external live HUD/instrument rendering.

This module is responsible ONLY for drawing the structural cockpit geometry and its 
static/dynamic visual elements (indicators, pulses, flashes).
"""

import pygame
import math

# ──────────────────────────────────────────────────────────────────────────────
# Palette
# ──────────────────────────────────────────────────────────────────────────────
_DARK       = (4, 7, 15)
_MID        = (9, 16, 28)
_LIGHT      = (18, 28, 46)
_EDGE       = (0, 180, 120)
_EDGE_DIM   = (0, 75, 50)
_CYAN       = (0, 170, 210)
_CYAN_DIM   = (0, 60, 90)
_AMBER      = (180, 90, 0)

_RED_ON     = (220, 40, 20)
_RED_OFF    = (55, 10, 8)

_SHADOW     = (0, 0, 0, 70)

# ──────────────────────────────────────────────────────────────────────────────
# Drawing Helpers (Short aliases for brevity in geometry definitions)
# ──────────────────────────────────────────────────────────────────────────────
def _p(surf, col, pts, width=0):
    """Draws a filled or outlined polygon.
    
    Args:
        surf (pygame.Surface): Target surface to draw on.
        col (tuple): RGB or RGBA color tuple.
        pts (list): List of (x, y) coordinate tuples.
        width (int): Border width. If 0, fills the polygon.
    """
    if len(pts) >= 3:
        pygame.draw.polygon(surf, col, pts, width)

def _l(surf, col, a, b, w=1):
    """Draws a single line.
    
    Args:
        surf (pygame.Surface): Target surface.
        col (tuple): RGB color.
        a (tuple): Start (x, y) coordinates.
        b (tuple): End (x, y) coordinates.
        w (int): Line width.
    """
    pygame.draw.line(surf, col, a, b, w)

def _poly(surf, col, pts, w=1):
    """Draws an open sequence of connected lines (a polyline).
    
    Args:
        surf (pygame.Surface): Target surface.
        col (tuple): RGB color.
        pts (list): List of (x, y) coordinates.
        w (int): Line width.
    """
    for i in range(len(pts) - 1):
        _l(surf, col, pts[i], pts[i + 1], w)

def _r(surf, col, rect, width=0, br=0):
    """Draws a rectangle, optionally with rounded corners.
    
    Args:
        surf (pygame.Surface): Target surface.
        col (tuple): RGB color.
        rect (tuple): (x, y, width, height) rectangle definition.
        width (int): Border width. If 0, fills the rectangle.
        br (int): Border radius for rounded corners.
    """
    pygame.draw.rect(surf, col, rect, width, border_radius=br)

def _c(surf, col, center, radius, width=0):
    """Draws a circle.
    
    Args:
        surf (pygame.Surface): Target surface.
        col (tuple): RGB color.
        center (tuple): (x, y) center coordinates.
        radius (int): Circle radius.
        width (int): Border width. If 0, fills the circle.
    """
    pygame.draw.circle(surf, col, center, radius, width)

# ──────────────────────────────────────────────────────────────────────────────
# Geometry Generators
# ──────────────────────────────────────────────────────────────────────────────
def _inset_panel(surf, outer_pts, inset=6,
                 outer_col=_MID,
                 inner_col=_DARK,
                 edge_col=_EDGE_DIM):
    """Creates a recessed panel effect by drawing a smaller polygon inside another.
    
    Calculates the centroid of the outer points and moves each point toward it
    by the 'inset' amount.
    
    Args:
        surf (pygame.Surface): Target surface.
        outer_pts (list): Vertices of the outer frame.
        inset (int): How many pixels to shrink the inner panel by.
        outer_col (tuple): Color of the outer frame.
        inner_col (tuple): Color of the inner (recessed) area.
        edge_col (tuple): Color of the outline for the inner panel.
        
    Returns:
        list: The calculated points for the inner panel.
    """
    # Draw the base outer frame
    _p(surf, outer_col, outer_pts)

    # Calculate centroid for inward scaling
    cx = sum(x for x, y in outer_pts) / len(outer_pts)
    cy = sum(y for x, y in outer_pts) / len(outer_pts)

    inner = []

    # Scale points toward centroid
    for x, y in outer_pts:
        dx = cx - x
        dy = cy - y
        mag = max(1, math.hypot(dx, dy))

        inner.append((
            x + dx / mag * inset,
            y + dy / mag * inset
        ))

    # Draw the inner recessed area
    _p(surf, inner_col, inner)
    # Draw the bevel/edge highlight
    _poly(surf, edge_col, inner + [inner[0]], 1)

    return inner


def _vent(surf, x, y, w, h, count=5):
    """Draws an industrial vent with horizontal slats.
    
    Args:
        surf (pygame.Surface): Target surface.
        x, y (int): Top-left position.
        w, h (int): Width and height of the vent housing.
        count (int): Number of horizontal slats/slots.
    """
    # Vent background housing
    _r(surf, _MID, (x, y, w, h))

    pad = 4
    slot_h = 2
    spacing = (h - pad * 2) / count

    # Draw individual recessed slots
    for i in range(count):
        sy = y + pad + i * spacing
        _r(surf, _DARK, (x + 5, sy, w - 10, slot_h))


def _hex_plate(surf, cx, cy, r):
    """Draws a hexagonal armor plate with an inset recessed area.
    
    Args:
        surf (pygame.Surface): Target surface.
        cx, cy (int): Center coordinates.
        r (int): Radius of the hexagon.
        
    Returns:
        list: The inner points of the hexagon.
    """
    pts = []

    # Generate 6 points for a regular hexagon
    for i in range(6):
        a = math.radians(i * 60)
        pts.append((
            cx + math.cos(a) * r,
            cy + math.sin(a) * r
        ))

    # Apply the inset panel treatment for depth
    inner = _inset_panel(surf, pts, 5, _MID, _DARK, _EDGE_DIM)
    return inner


# ──────────────────────────────────────────────────────────────────────────────
# Static Geometry Caching
# ──────────────────────────────────────────────────────────────────────────────
# We cache the heavy static geometry to a Surface to avoid re-calculating 
# thousands of points every frame.
_STATIC = None
_STATIC_SIZE = (0, 0)

def _build_static(W, H):
    """Bakes the non-animated cockpit geometry into a static Surface.
    
    This includes the main frame, struts, console housings, and dash panels.
    It respects 'safe zones' where HUD text (like heading or hull bars) is drawn.
    
    Args:
        W, H (int): Dimensions of the screen/target surface.
        
    Returns:
        pygame.Surface: A transparent surface containing the rendered static geometry.
    """

    s = pygame.Surface((W, H), pygame.SRCALPHA)
    cx = W // 2

    # HUD safe zones — geometry lines must not cross into these
    # heading tape lives at top ~0..28px, hull bar at bottom ~H-28..H
    TOP_SAFE    = 28   # below this line: heading tape band — no geometry lines
    BOTTOM_SAFE = H - 28  # above this line: hull bar band — no geometry lines

    # =========================================================================
    # TOP FRAME
    # =========================================================================

    # Main Top Frame Boundary
    # Defines the overall silhouette of the top cockpit bar
    top = [
        (0, 0),
        (W, 0),
        (W, 72),      # Right edge drop

        (1050, 72),   # Right notch start
        (970, 96),    # Right notch corner

        (cx + 240, 96), # Center-right indent
        (cx + 240, 70), # Center-right rise

        (cx - 240, 70), # Center-left rise
        (cx - 240, 96), # Center-left indent

        (310, 96),    # Left notch corner
        (230, 72),    # Left notch start

        (0, 72)       # Left edge drop
    ]

    _p(s, _DARK, top)

    # Top Panel Layering (Recessed aesthetic)
    # This creates the "plate on plate" look with a bright edge
    top_inner_points = [
        (12, TOP_SAFE + 4),
        (W - 12, TOP_SAFE + 4),
        (W - 12, 62),

        (1040, 62),
        (955, 86),

        (cx + 220, 86),
        (cx + 220, 62),

        (cx - 220, 62),
        (cx - 220, 86),

        (325, 86),
        (240, 62),

        (12, 62)
    ]
    
    top_inner = _inset_panel(
        s,
        top_inner_points,
        inset=5,
        outer_col=_MID,
        inner_col=_DARK,
        edge_col=_EDGE_DIM
    )

    # bright highlight on the full outer top inset
    _poly(s, _EDGE, top_inner + [top_inner[0]], 1)

    # secondary recessed sub-panels in the top bar — left and right of center gap
    # left sub-panel
    _inset_panel(s, [
        (20, TOP_SAFE + 8),
        (cx - 245, TOP_SAFE + 8),
        (cx - 245, 60),
        (20, 60),
    ], 4, _LIGHT, _MID, _CYAN_DIM)

    # right sub-panel
    _inset_panel(s, [
        (cx + 245, TOP_SAFE + 8),
        (W - 20, TOP_SAFE + 8),
        (W - 20, 60),
        (cx + 245, 60),
    ], 4, _LIGHT, _MID, _CYAN_DIM)

    # =========================================================================
    # LEFT STRUT (Vertical support on the left side)
    # =========================================================================

    left_strut = [
        (0, 0),
        (250, 0),
        (250, 72),      # Connects to top frame

        (205, 132),     # First diagonal break
        (170, 300),     # Long sweep
        (155, 430),     # Bottom taper
        (120, 470),     # Corner join

        (0, 470)        # Edge join
    ]

    _p(s, _MID, left_strut)

    # outer armor shell — recessed with CYAN highlight to match consoles
    outer_plate = [
        (8, TOP_SAFE + 4),
        (232, TOP_SAFE + 4),
        (232, 68),

        (188, 122),
        (158, 290),
        (143, 418),
        (108, 450),

        (8, 450)
    ]

    _inset_panel(s, outer_plate, 7, _MID, _DARK, _CYAN_DIM)
    _poly(s, _EDGE_DIM, outer_plate + [outer_plate[0]], 1)

    # inner recessed armor panel — tighter inset, brighter edge
    inner_plate = [
        (22, TOP_SAFE + 12),
        (218, TOP_SAFE + 12),
        (218, 62),

        (175, 116),
        (145, 284),
        (132, 410),
        (97, 440),

        (22, 440)
    ]

    _inset_panel(s, inner_plate, 5, _LIGHT, _MID, _EDGE_DIM)

    # Asymmetrical hex plate on the left strut (moved down to clear HUD bars)
    _hex_plate(s, 70, 390, 32)

    groove = [
        (250, 72),
        (205, 132),
        (170, 300),
        (155, 430),
        (120, 470)
    ]

    _poly(s, _DARK, groove, 2)

    # =========================================================================
    # RIGHT STRUT
    # =========================================================================

    right_strut = [
        (W, 0),
        (W - 250, 0),
        (W - 250, 72),

        (W - 205, 132),
        (W - 170, 300),
        (W - 155, 430),
        (W - 120, 470),

        (W, 470)
    ]

    _p(s, _MID, right_strut)

    # outer armor shell — mirrored
    outer_plate_r = [
        (W - 8, TOP_SAFE + 4),
        (W - 232, TOP_SAFE + 4),
        (W - 232, 68),

        (W - 188, 122),
        (W - 158, 290),
        (W - 143, 418),
        (W - 108, 450),

        (W - 8, 450)
    ]

    _inset_panel(s, outer_plate_r, 7, _LIGHT, _MID, _EDGE_DIM)
    _poly(s, _EDGE_DIM, outer_plate_r + [outer_plate_r[0]], 1)

    # asymmetrical detail (moved down to clear HUD bars)
    _hex_plate(s, W - 70, 390, 32)

    groove_r = [
        (W - 250, 72),
        (W - 205, 132),
        (W - 170, 300),
        (W - 155, 430),
        (W - 120, 470)
    ]

    _poly(s, _EDGE, groove_r, 2)

    # =========================================================================
    # LOWER LEFT CONSOLE
    # =========================================================================

    left_console = [
        (0, 470),
        (120, 470),

        (150, 510),
        (175, 580),

        (190, 690),
        (190, H),

        (0, H)
    ]

    _p(s, _DARK, left_console)

    # upper armor inset
    _inset_panel(s, [
        (8, 485),
        (102, 485),
        (128, 520),
        (128, 640),
        (8, 640)
    ], 5)

    # radar housing
    radar_outer = [
        (0, 570),
        (170, 570),

        (182, 590),
        (182, 720),

        (165, 755),
        (5, 755)
    ]

    radar_inner = _inset_panel(
        s,
        radar_outer,
        4,
        _LIGHT,
        _MID,
        _CYAN
    )

    # Deep Radar Recess (Circle stack for depth)
    # Centered at (90, H - 95) to match the 3D radar in cockpit.py
    _c(s, _DARK, (90, H - 95), 80)
    _c(s, _MID, (90, H - 95), 75)

    # Radar Grid / Groove Rings
    # Static rings to give the radar floor some depth
    # Matches the 37.5 radius mid-ring in cockpit.py
    for r in [37]:
        _c(s, _EDGE_DIM, (90, H - 95), r, 1)

    # Radial "Clock" lines for radar orientation
    for a in range(0, 360, 45):
        rad = math.radians(a)

        x1 = 90 + math.cos(rad) * 15
        y1 = (H - 95) + math.sin(rad) * 15

        x2 = 90 + math.cos(rad) * 70
        y2 = (H - 95) + math.sin(rad) * 70

        _l(s, _EDGE_DIM, (x1, y1), (x2, y2), 1)

    # indicator pockets
    for i in range(3):
        y = 500 + i * 24

        _inset_panel(
            s,
            [
                (42, y),
                (78, y),
                (78, y + 16),
                (42, y + 16)
            ],
            3,
            _MID,
            _DARK,
            _EDGE_DIM
        )

    # =========================================================================
    # LOWER RIGHT CONSOLE
    # =========================================================================

    right_console = [
        (W, 470),
        (W - 120, 470),

        (W - 150, 510),
        (W - 175, 580),

        (W - 190, 690),
        (W - 190, H),

        (W, H)
    ]

    _p(s, _DARK, right_console)

    _inset_panel(s, [
        (W - 8, 485),
        (W - 102, 485),
        (W - 128, 520),
        (W - 128, 640),
        (W - 8, 640)
    ], 5)

    # asymmetric venting (Moved down and left to clear space for speed readout)
    _vent(s, W - 155, 665, 50, 40)

    # throttle trench (Shrunk vertically to clear space for GUN TEMP / MSL box)
    trench = [
        (W - 165, 640),
        (W - 25, 640),

        (W - 35, 720),
        (W - 155, 720)
    ]

    _inset_panel(s, trench, 8, _LIGHT, _MID, _CYAN)

    # =========================================================================
    # CENTER DASH
    # =========================================================================

    # Center dash plate construction
    center = [
        (190, H),
        (190, 710),

        (210, 660),
        (290, 610),

        (cx - 180, 585),
        (cx + 180, 585),

        (W - 290, 610),
        (W - 210, 660),

        (W - 190, 710),
        (W - 190, H)
    ]

    _p(s, _MID, center)

    # Main structural plate on the center dash
    main_plate = [
        (260, H - 8),
        (260, 690),

        (320, 635),

        (cx - 150, 610),
        (cx + 150, 610),

        (W - 320, 635),

        (W - 260, 690),
        (W - 260, H - 8)
    ]

    _inset_panel(s, main_plate, 10)

    # The core central monitor/instrument recess
    core = [
        (cx - 90, 620),
        (cx + 90, 620),

        (cx + 120, 655),
        (cx + 100, 700),

        (cx - 100, 700),
        (cx - 120, 655)
    ]

    _inset_panel(s, core, 8, _LIGHT, _DARK, _EDGE)

    # Vertical detail seams in the center dash
    for off in [-140, 140]:
        y1 = 620
        y2 = min(H, BOTTOM_SAFE - 2)
        _l(
            s,
            _EDGE_DIM,
            (cx + off, y1),
            (cx + int(off * 1.2), y2),
            1
        )

    # Thick support ribs at the base
    for off in [-240, -180, 180, 240]:
        y1 = 650
        y2 = min(H, BOTTOM_SAFE - 2)
        _l(
            s,
            _DARK,
            (cx + off, y1),
            (cx + int(off * 1.1), y2),
            3
        )

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
    """Main entry point to draw the cockpit and HUD overlays.
    
    Handles static geometry caching, dynamic glows, indicator lights,
    and screen-wide flash effects.
    
    Args:
        surface (pygame.Surface): The main display surface.
        ticks (int): Current millisecond count for animations.
        alert_active (bool): Whether a general 'warning' state is active (e.g. low fuel).
        missile_lock (bool): Whether an enemy has a lock on the player.
        hit_flash (float): 0.0 to 1.0 value representing recent damage impact intensity.
        explosion_glow (float): 0.0 to 1.0 value for external explosion light bleed.
    """

    global _STATIC, _STATIC_SIZE

    # Check for resolution changes or first-time initialization
    W, H = surface.get_size()

    if _STATIC is None or _STATIC_SIZE != (W, H):
        _STATIC = _build_static(W, H)
        _STATIC_SIZE = (W, H)

    # Draw the cached static background first
    surface.blit(_STATIC, (0, 0))

    # Time-based animation factor (seconds)
    t = ticks * 0.001

    # --- DYNAMIC GLOWS AND PULSES ---

    # Main Emissive Groove Pulse (Cyan/Green)
    # Sinusoidal breathing effect for the outer frame grooves
    pulse = int(140 + 60 * math.sin(t * 1.7))
    glow = (0, pulse, 120)

    # Coordinates for the emissive grooves on the struts
    left_glow = [
        (250, 72),
        (205, 132),
        (170, 300),
        (155, 430),
        (120, 470)
    ]

    right_glow = [
        (W - 250, 72),
        (W - 205, 132),
        (W - 170, 300),
        (W - 155, 430),
        (W - 120, 470)
    ]

    _poly(surface, glow, left_glow, 1)
    _poly(surface, glow, right_glow, 1)

    # Top Bar Edge Pulse (Cyberpunk blue/cyan)
    top_pulse = int(60 + 30 * math.sin(t * 1.2))
    _poly(surface, (0, top_pulse, top_pulse + 30), [
        (22, 32),
        (W - 22, 32),
        (W - 22, 60),
        (22, 60),
        (22, 32),
    ], 1)

    # animated strut inner edge glow
    strut_glow = (0, int(55 + 25 * math.sin(t * 1.4)), int(70 + 30 * math.sin(t * 1.4)))

    left_inner_glow = [
        (22, 32),
        (218, 32),
        (175, 116),
        (145, 284),
        (132, 410),
        (97, 440),
        (22, 440),
        (22, 32),
    ]
    right_inner_glow = [
        (W - 22, 32),
        (W - 218, 32),
        (W - 175, 116),
        (W - 145, 284),
        (W - 132, 410),
        (W - 97, 440),
        (W - 22, 440),
        (W - 22, 32),
    ]

    _poly(surface, strut_glow, left_inner_glow, 1)
    _poly(surface, strut_glow, right_inner_glow, 1)

    # Radar Sweep Rings (Expanding/contracting circle highlight)
    radar_pulse = int(70 + 50 * math.sin(t * 3.0))

    for r in [37]:
        _c(
            surface,
            (0, radar_pulse, 90),
            (90, H - 95),
            r,
            1
        )

    # Left Console Indicator Lights (Status Indicators)
    # They stay steady green when shields are healthy, and turn pulsing red
    # progressively as the shield is depleted (one per 33% loss).
    for i in range(3):
        y = 500 + i * 24
        
        # Determine if this specific bar should be Red (warning) or Green (okay)
        # Thresholds: Top bar (0) turns red at <66%, Mid (1) at <33%, Bottom (2) at 0%
        if shield_charge <= (1.0 - (i + 1) * 0.333):
            # Pulsing Red Warning
            bar_color = (
                min(255, 180 + int(70 * abs(math.sin(t * 5)))),
                20,
                10
            )
        else:
            # Steady Green Status (with a subtle life pulse)
            g_pulse = int(140 + 40 * math.sin(t * 2.0))
            bar_color = (20, g_pulse, 60)

        # Small indicator rectangles next to the radar
        _r(surface, bar_color, (50, y + 3, 20, 8), br=2)

    # hit flash
    if hit_flash > 0.01:
        fs = pygame.Surface((W, H), pygame.SRCALPHA)
        fs.fill((255, 0, 0, int(hit_flash * 80)))
        surface.blit(fs, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    # explosion glow
    if explosion_glow > 0.01:
        gs = pygame.Surface((W, H), pygame.SRCALPHA)

        a = int(explosion_glow * 60)

        gs.fill((a, a // 3, 0, a))

        surface.blit(gs, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)