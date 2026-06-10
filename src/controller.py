import pygame
import argparse
import sys

from src.constants import DEADZONE_DEFAULT, CONTROLLER_LOG_THRESHOLD, TRIGGER_LOG_THRESHOLD


# ──────────────────────────────────────────────
#  DS4 MAPPINGS
# ──────────────────────────────────────────────
BUTTON_NAMES = [
    'X', 'Circle', 'Triangle', 'Square',
    'L1', 'R1', 'L2', 'R2',
    'Share', 'Options', 'PS', 'L3',
    'R3', 'Touchpad',
    'DPad Up', 'DPad Down', 'DPad Left', 'DPad Right'
]

# Real DS4 axis order via SDL/pygame:
#   0 = Left Stick X
#   1 = Left Stick Y
#   2 = L2 Trigger      ← NOT right stick X
#   3 = Right Stick X
#   4 = Right Stick Y
#   5 = R2 Trigger
AXIS_NAMES = [
    'Left Stick X', 'Left Stick Y',
    'L2 Trigger',
    'Right Stick X', 'Right Stick Y',
    'R2 Trigger'
]

# Axis index constants — change these if your driver maps differently
AX_LX, AX_LY = 0, 1
AX_L2        = 2
AX_RX, AX_RY = 3, 4
AX_R2        = 5

# ──────────────────────────────────────────────
#  THEME
# ──────────────────────────────────────────────
BG         = (10,  10,  18)
PANEL      = (20,  20,  32)
BORDER     = (40,  40,  60)
ACCENT     = (80, 140, 255)
ACCENT2    = (255, 80, 140)
GREEN      = (60, 220, 120)
YELLOW     = (255, 210,  60)
WHITE      = (230, 230, 240)
GRAY       = (100, 100, 130)
DARK_GRAY  = ( 30,  30,  48)

W, H = 900, 620

# ──────────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────────
def draw_rounded_rect(surf, color, rect, r=8, border=0, border_color=None):
    pygame.draw.rect(surf, color, rect, border_radius=r)
    if border and border_color:
        pygame.draw.rect(surf, border_color, rect, border, border_radius=r)

def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

# ──────────────────────────────────────────────
#  INPUT HANDLER
# ──────────────────────────────────────────────
class DS4Input:
    """
    Abstracts all gamepad/controller pygame events into clean per-frame state.
    Supports auto-detection of controllers via SDL2 GameController API,
    falling back to raw joystick profiles for unrecognized gamepads.

    Usage (minimal):
        handler = DS4Input()
        handler.init()                          # connects first joystick found

        # in your event loop:
        for event in pygame.event.get():
            handler.process_event(event)

        # in your update/draw (call in this order):
        if handler.just_pressed('X'): ...       # ← check BEFORE update()
        if handler.held('R1'):        ...
        lx, ly = handler.stick_left()
        handler.update()                        # ← call LAST per frame to clear single-frame sets

        # read state:
        lx, ly = handler.stick_left()           # –1..1, deadzone applied
        rx, ry = handler.stick_right()
        l2     = handler.trigger_left()         # 0..1
        r2     = handler.trigger_right()        # 0..1
        hat    = handler.dpad()                 # (dx, dy) raw hat tuple
    """

    DEADZONE_DEFAULT = 0.20

    # Aliases to map raw button names or alternative layouts to standard PS naming
    ALIASES = {
        'Cross': 'X',
        'A': 'X',
        'B': 'Circle',
        'Y': 'Triangle',
        'LB': 'L1',
        'RB': 'R1',
        'LT': 'L2',
        'RT': 'R2',
        'Back': 'Share',
        'Guide': 'PS',
    }

    # Standard SDL Controller to Game Button Mapping
    SDL_BUTTON_MAP = {
        pygame.CONTROLLER_BUTTON_A: 'X',
        pygame.CONTROLLER_BUTTON_B: 'Circle',
        pygame.CONTROLLER_BUTTON_Y: 'Triangle',
        pygame.CONTROLLER_BUTTON_X: 'Square',
        pygame.CONTROLLER_BUTTON_LEFTSHOULDER: 'L1',
        pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: 'R1',
        pygame.CONTROLLER_BUTTON_BACK: 'Share',
        pygame.CONTROLLER_BUTTON_START: 'Options',
        pygame.CONTROLLER_BUTTON_GUIDE: 'PS',
        pygame.CONTROLLER_BUTTON_LEFTSTICK: 'L3',
        pygame.CONTROLLER_BUTTON_RIGHTSTICK: 'R3',
        pygame.CONTROLLER_BUTTON_DPAD_UP: 'DPad Up',
        pygame.CONTROLLER_BUTTON_DPAD_DOWN: 'DPad Down',
        pygame.CONTROLLER_BUTTON_DPAD_LEFT: 'DPad Left',
        pygame.CONTROLLER_BUTTON_DPAD_RIGHT: 'DPad Right',
    }

    # Predefined raw joystick mapping profiles (Fallback Mode)
    PS_BUTTON_MAP = {
        0: 'X', 1: 'Circle', 2: 'Triangle', 3: 'Square',
        4: 'L1', 5: 'R1', 6: 'L2', 7: 'R2',
        8: 'Share', 9: 'Options', 10: 'PS', 11: 'L3', 12: 'R3',
        13: 'Touchpad'
    }
    PS_AXIS_MAP = {'LX': 0, 'LY': 1, 'RX': 3, 'RY': 4, 'L2': 2, 'R2': 5}

    XBOX_BUTTON_MAP = {
        0: 'X', 1: 'Circle', 2: 'Square', 3: 'Triangle',
        4: 'L1', 5: 'R1', 6: 'Share', 7: 'Options', 8: 'PS',
        9: 'L3', 10: 'R3'
    }
    XBOX_AXIS_MAP = {'LX': 0, 'LY': 1, 'RX': 3, 'RY': 4, 'L2': 2, 'R2': 5}

    SWITCH_BUTTON_MAP = {
        0: 'X', 1: 'Circle', 2: 'Square', 3: 'Triangle',
        4: 'L1', 5: 'R1', 6: 'L2', 7: 'R2',
        8: 'Share', 9: 'Options', 10: 'PS',
        12: 'L3', 13: 'R3'
    }
    SWITCH_AXIS_MAP = {'LX': 0, 'LY': 1, 'RX': 2, 'RY': 3, 'L2': 4, 'R2': 5}

    def __init__(self, joystick_index: int = 0, deadzone: float = DEADZONE_DEFAULT):
        self.joystick_index = joystick_index
        self.deadzone       = deadzone
        self._joy: pygame.joystick.JoystickType | None = None
        self._controller = None
        self._is_sdl_controller = False
        self._controller_module = None

        # raw axis values (–1..1)
        self._axes: dict[int, float] = {}

        # button state — keyed by BUTTON_NAMES string
        self._held:         set[str]  = set()
        self._just_pressed: set[str]  = set()
        self._just_released:set[str]  = set()

        # hat state (only used in raw fallback hat events)
        self._hat: tuple[int, int] = (0, 0)

        # fallback mapping configuration
        self._button_map = self.XBOX_BUTTON_MAP
        self._axis_map = self.XBOX_AXIS_MAP

        # optional callbacks
        self.on_press:   callable | None = None
        self.on_release: callable | None = None
        self.on_hat:     callable | None = None

        # connected info (readable after init)
        self.connected   = False
        self.name        = "No controller"
        self.num_buttons = 0
        self.num_axes    = 0
        self.num_hats    = 0

        # rumble support
        self.rumble_supported = False

    # ── initialise / reconnect ──────────────────

    def init(self) -> bool:
        """Connect to the joystick. Returns True if successful."""
        pygame.joystick.init()
        try:
            import pygame._sdl2.controller as controller
            controller.init()
            self._controller_module = controller
        except Exception:
            self._controller_module = None

        if pygame.joystick.get_count() > self.joystick_index:
            is_ctrl = False
            if self._controller_module:
                try:
                    is_ctrl = self._controller_module.is_controller(self.joystick_index)
                except Exception:
                    is_ctrl = False

            if is_ctrl:
                try:
                    self._controller = self._controller_module.Controller(self.joystick_index)
                    self._controller.init()
                    self._is_sdl_controller = True
                    self._joy = self._controller.as_joystick()
                    
                    # Pre-populate axis values from controller (range -32768..32767)
                    for axis_idx in range(6):
                        raw_val = self._controller.get_axis(axis_idx)
                        if axis_idx in (pygame.CONTROLLER_AXIS_TRIGGERLEFT, pygame.CONTROLLER_AXIS_TRIGGERRIGHT):
                            self._axes[axis_idx] = raw_val / 32767.0
                        else:
                            self._axes[axis_idx] = raw_val / 32768.0
                except Exception:
                    self._is_sdl_controller = False
                    self._controller = None
                    self._joy = pygame.joystick.Joystick(self.joystick_index)
                    self._joy.init()
                    
                    # Pre-populate raw axis values (range -1.0..1.0)
                    for axis_idx in range(self._joy.get_numaxes()):
                        self._axes[axis_idx] = self._joy.get_axis(axis_idx)
            else:
                self._is_sdl_controller = False
                self._controller = None
                self._joy = pygame.joystick.Joystick(self.joystick_index)
                self._joy.init()
                
                # Pre-populate raw axis values (range -1.0..1.0)
                for axis_idx in range(self._joy.get_numaxes()):
                    self._axes[axis_idx] = self._joy.get_axis(axis_idx)

            self.connected   = True
            if self._is_sdl_controller and self._controller:
                self.name = self._controller.name or self._joy.get_name()
            else:
                self.name = self._joy.get_name()

            self.num_buttons = self._joy.get_numbuttons()
            self.num_axes    = self._joy.get_numaxes()
            self.num_hats    = self._joy.get_numhats()

            if not self._is_sdl_controller:
                self._setup_raw_profile()

            # Check if rumble is supported
            self.rumble_supported = False
            try:
                if self._is_sdl_controller and self._controller:
                    self.rumble_supported = self._controller.rumble(0.0, 0.0, 0)
                else:
                    self.rumble_supported = self._joy.rumble(0.0, 0.0, 0)
            except Exception:
                self.rumble_supported = False

            return True

        self.connected = False
        self.name      = "No controller detected"
        self.rumble_supported = False
        self._is_sdl_controller = False
        self._controller = None
        self._joy = None
        return False

    def _setup_raw_profile(self):
        name_lower = self.name.lower()
        if any(substring in name_lower for substring in ('playstation', 'dualshock', 'dualsense', 'ps4', 'ps5', 'sony')):
            self._button_map = self.PS_BUTTON_MAP
            self._axis_map = self.PS_AXIS_MAP
        elif any(substring in name_lower for substring in ('xbox', 'microsoft', 'x-box')):
            self._button_map = self.XBOX_BUTTON_MAP
            self._axis_map = self.XBOX_AXIS_MAP
        elif any(substring in name_lower for substring in ('switch', 'nintendo')):
            self._button_map = self.SWITCH_BUTTON_MAP
            self._axis_map = self.SWITCH_AXIS_MAP
        else:
            # Generic fallback: Xbox buttons, dynamic axes discovery
            self._button_map = self.XBOX_BUTTON_MAP
            self._axis_map = self._discover_axes(self.num_axes)

    @staticmethod
    def _discover_axes(num_axes: int) -> dict[str, int]:
        if num_axes >= 6:
            return {
                'LX': 0, 'LY': 1,
                'RX': 3, 'RY': 4,
                'L2': 2, 'R2': 5
            }
        elif num_axes >= 4:
            return {
                'LX': 0, 'LY': 1,
                'RX': 2, 'RY': 3,
                'L2': -1, 'R2': -1
            }
        else:
            return {
                'LX': 0, 'LY': 1,
                'RX': -1, 'RY': -1,
                'L2': -1, 'R2': -1
            }

    # ── event ingestion ─────────────────────────

    def process_event(self, event: pygame.event.Event) -> bool:
        """
        Feed a pygame event to the handler.
        Returns True if the event was consumed (joystick-related).
        """
        # Re-initialize on hotplug events
        if event.type in (
            pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED,
            pygame.CONTROLLERDEVICEADDED, pygame.CONTROLLERDEVICEREMOVED
        ):
            self.init()
            return True

        if self._is_sdl_controller:
            if event.type == pygame.CONTROLLERBUTTONDOWN:
                name = self.SDL_BUTTON_MAP.get(event.button, f"Btn {event.button}")
                self._held.add(name)
                self._just_pressed.add(name)
                if self.on_press:
                    self.on_press(name)
                return True

            if event.type == pygame.CONTROLLERBUTTONUP:
                name = self.SDL_BUTTON_MAP.get(event.button, f"Btn {event.button}")
                self._held.discard(name)
                self._just_released.add(name)
                if self.on_release:
                    self.on_release(name)
                return True

            if event.type == pygame.CONTROLLERAXISMOTION:
                # Normalize SDL Controller axis values from -32768..32767 to -1.0..1.0
                if event.axis in (pygame.CONTROLLER_AXIS_TRIGGERLEFT, pygame.CONTROLLER_AXIS_TRIGGERRIGHT):
                    val = event.value / 32767.0
                else:
                    val = event.value / 32768.0
                self._axes[event.axis] = val
                
                # Synthesize digital button presses for triggers
                if event.axis == pygame.CONTROLLER_AXIS_TRIGGERLEFT:
                    self._handle_trigger_button('L2', val)
                elif event.axis == pygame.CONTROLLER_AXIS_TRIGGERRIGHT:
                    self._handle_trigger_button('R2', val)
                return True

        else:
            if event.type == pygame.JOYBUTTONDOWN:
                name = self._button_map.get(event.button, f"Btn {event.button}")
                self._held.add(name)
                self._just_pressed.add(name)
                if self.on_press:
                    self.on_press(name)
                return True

            if event.type == pygame.JOYBUTTONUP:
                name = self._button_map.get(event.button, f"Btn {event.button}")
                self._held.discard(name)
                self._just_released.add(name)
                if self.on_release:
                    self.on_release(name)
                return True

            if event.type == pygame.JOYAXISMOTION:
                self._axes[event.axis] = event.value
                
                # Synthesize digital button presses for triggers
                l2_axis = self._axis_map.get('L2', -1)
                r2_axis = self._axis_map.get('R2', -1)
                if event.axis == l2_axis:
                    self._handle_trigger_button('L2', event.value)
                elif event.axis == r2_axis:
                    self._handle_trigger_button('R2', event.value)
                return True

            if event.type == pygame.JOYHATMOTION:
                old_hat = self._hat
                self._hat = event.value
                
                # Synthesize button-like events for D-Pad directions
                for dx, dy, name in [
                    (0, 1, 'DPad Up'), (0, -1, 'DPad Down'),
                    (-1, 0, 'DPad Left'), (1, 0, 'DPad Right')
                ]:
                    # Check vertical
                    if dy != 0:
                        if self._hat[1] == dy and old_hat[1] != dy:
                            self._just_pressed.add(name)
                        if self._hat[1] != dy and old_hat[1] == dy:
                            self._just_released.add(name)
                        if self._hat[1] == dy: self._held.add(name)
                        else: self._held.discard(name)
                    # Check horizontal
                    if dx != 0:
                        if self._hat[0] == dx and old_hat[0] != dx:
                            self._just_pressed.add(name)
                        if self._hat[0] != dx and old_hat[0] == dx:
                            self._just_released.add(name)
                        if self._hat[0] == dx: self._held.add(name)
                        else: self._held.discard(name)

                if self.on_hat:
                    self.on_hat(event.value)
                return True

        return False

    def _handle_trigger_button(self, name: str, value: float):
        if self._is_sdl_controller:
            is_pressed = value > 0.5
        else:
            is_pressed = value > 0.0
            
        if is_pressed and name not in self._held:
            self._held.add(name)
            self._just_pressed.add(name)
            if self.on_press:
                self.on_press(name)
        elif not is_pressed and name in self._held:
            self._held.discard(name)
            self._just_released.add(name)
            if self.on_release:
                self.on_release(name)

    def update(self):
        """
        Clear single-frame sets. Call exactly ONCE per frame,
        AFTER processing all events.
        """
        self._just_pressed.clear()
        self._just_released.clear()

    # ── button queries ───────────────────────────

    def _resolve_button(self, button: str) -> str:
        return self.ALIASES.get(button, button)

    def held(self, button: str) -> bool:
        """True every frame the button is down."""
        return self._resolve_button(button) in self._held

    def just_pressed(self, button: str) -> bool:
        """True only on the frame the button went down."""
        return self._resolve_button(button) in self._just_pressed

    def just_released(self, button: str) -> bool:
        """True only on the frame the button came up."""
        return self._resolve_button(button) in self._just_released

    def any_pressed(self) -> list[str]:
        """All buttons currently held."""
        return list(self._held)

    # ── stick queries ────────────────────────────

    def stick_left(self) -> tuple[float, float]:
        """Left stick (x, y) with deadzone applied, –1..1."""
        if self._is_sdl_controller:
            lx = self._axes.get(pygame.CONTROLLER_AXIS_LEFTX, 0.0)
            ly = self._axes.get(pygame.CONTROLLER_AXIS_LEFTY, 0.0)
        else:
            lx = self._axes.get(self._axis_map.get('LX', 0), 0.0)
            ly = self._axes.get(self._axis_map.get('LY', 1), 0.0)
        return self._apply_deadzone(lx, ly)

    def stick_right(self) -> tuple[float, float]:
        """Right stick (x, y) with deadzone applied, –1..1."""
        if self._is_sdl_controller:
            rx = self._axes.get(pygame.CONTROLLER_AXIS_RIGHTX, 0.0)
            ry = self._axes.get(pygame.CONTROLLER_AXIS_RIGHTY, 0.0)
        else:
            rx = self._axes.get(self._axis_map.get('RX', 3), 0.0)
            ry = self._axes.get(self._axis_map.get('RY', 4), 0.0)
        return self._apply_deadzone(rx, ry)

    # ── trigger queries ──────────────────────────

    def trigger_left(self) -> float:
        """L2 normalised to 0..1."""
        if self._is_sdl_controller:
            return self._axes.get(pygame.CONTROLLER_AXIS_TRIGGERLEFT, 0.0)
        else:
            raw = self._axes.get(self._axis_map.get('L2', 2), -1.0)
            return self._normalise_trigger(raw)

    def trigger_right(self) -> float:
        """R2 normalised to 0..1."""
        if self._is_sdl_controller:
            return self._axes.get(pygame.CONTROLLER_AXIS_TRIGGERRIGHT, 0.0)
        else:
            raw = self._axes.get(self._axis_map.get('R2', 5), -1.0)
            return self._normalise_trigger(raw)

    # ── hat / d-pad ──────────────────────────────

    def dpad(self) -> tuple[int, int]:
        """Raw hat value: (dx, dy) where each component is –1, 0, or 1."""
        if self._is_sdl_controller:
            dx = 0
            dy = 0
            if self.held('DPad Left'):
                dx = -1
            elif self.held('DPad Right'):
                dx = 1
            if self.held('DPad Down'):
                dy = -1
            elif self.held('DPad Up'):
                dy = 1
            return (dx, dy)
        else:
            return self._hat

    def dpad_direction(self) -> str:
        """Human-readable D-pad direction, or 'neutral'."""
        return DPad.DIRS.get(self.dpad(), 'neutral')

    # ── raw axis access ──────────────────────────

    def axis(self, index: int) -> float:
        """Raw axis value with no processing."""
        return self._axes.get(index, 0.0)

    # ── rumble control ───────────────────────────

    def rumble(self, low_frequency: float, high_frequency: float, duration: int = 100) -> bool:
        """
        Trigger controller rumble.
        Returns True if successful, False if not supported.
        """
        if not self.connected:
            return False
        try:
            low = max(0.0, min(1.0, low_frequency))
            high = max(0.0, min(1.0, high_frequency))
            if self._is_sdl_controller and self._controller:
                return self._controller.rumble(low, high, duration)
            elif self._joy:
                return self._joy.rumble(low, high, duration)
            return False
        except (AttributeError, RuntimeError):
            return False

    def stop_rumble(self) -> bool:
        """Stop all rumble immediately."""
        return self.rumble(0.0, 0.0, 0)

    def pulse(self, intensity: float = 1.0, duration: int = 100) -> bool:
        """Simple pulse: both motors at same intensity."""
        return self.rumble(intensity, intensity, duration)

    def punch(self, intensity: float = 1.0) -> bool:
        """Sharp punch feeling: high-frequency spike."""
        return self.rumble(0.0, intensity, 50)

    def buzz(self, intensity: float = 0.7, duration: int = 200) -> bool:
        """Continuous buzz: low-frequency vibration."""
        return self.rumble(intensity, 0.0, duration)

    def wave(self, intensity: float = 1.0) -> bool:
        """Wave effect: both motors ramping up and down."""
        return self.rumble(intensity * 0.5, intensity, 150)

    # ── internals ───────────────────────────────

    @staticmethod
    def _btn_name(index: int) -> str:
        return BUTTON_NAMES[index] if index < len(BUTTON_NAMES) else f"Btn {index}"

    @staticmethod
    def _normalise_trigger(raw: float) -> float:
        """Maps –1..1 SDL trigger range to 0..1."""
        return (raw + 1.0) / 2.0

    def _apply_deadzone(self, x: float, y: float) -> tuple[float, float]:
        """Radial deadzone."""
        magnitude = (x * x + y * y) ** 0.5
        if magnitude < self.deadzone:
            return 0.0, 0.0
        scale = (magnitude - self.deadzone) / (1.0 - self.deadzone)
        scale = min(scale / magnitude, 1.0)   # normalise + clamp
        return x * scale, y * scale

# ──────────────────────────────────────────────
#  BUTTON GRID WIDGET
# ──────────────────────────────────────────────
class ButtonGrid:
    def __init__(self, x, y, num_buttons):
        self.x, self.y = x, y
        self.num = num_buttons
        self.states = [False] * max(num_buttons, len(BUTTON_NAMES))
        self.press_time = [0.0] * max(num_buttons, len(BUTTON_NAMES))

    def press(self, i):
        if i < len(self.states):
            self.states[i] = True
            self.press_time[i] = 1.0

    def release(self, i):
        if i < len(self.states):
            self.states[i] = False

    def update(self, dt):
        for i in range(len(self.press_time)):
            if not self.states[i] and self.press_time[i] > 0:
                self.press_time[i] = max(0.0, self.press_time[i] - dt * 3.0)

    def draw(self, surf, font_sm):
        cols = 4
        bw, bh, gap = 90, 36, 8
        for i in range(len(self.states)):
            col = i % cols
            row = i // cols
            rx = self.x + col * (bw + gap)
            ry = self.y + row * (bh + gap)
            t = self.press_time[i]
            active = self.states[i]
            bg = lerp_color(DARK_GRAY, ACCENT, t) if not active else ACCENT
            draw_rounded_rect(surf, bg, (rx, ry, bw, bh), r=6)
            draw_rounded_rect(surf, (0,0,0,0), (rx, ry, bw, bh), r=6, border=1,
                              border_color=ACCENT if (active or t > 0.05) else BORDER)
            name = BUTTON_NAMES[i] if i < len(BUTTON_NAMES) else f"Btn {i}"
            col_txt = WHITE if (active or t > 0.1) else GRAY
            lbl = font_sm.render(name, True, col_txt)
            surf.blit(lbl, (rx + bw//2 - lbl.get_width()//2,
                            ry + bh//2 - lbl.get_height()//2))



# ──────────────────────────────────────────────
#  STICK WIDGET
# ──────────────────────────────────────────────
class StickWidget:
    def __init__(self, cx, cy, radius=50, label=''):
        self.cx, self.cy = cx, cy
        self.r = radius
        self.vx, self.vy = 0.0, 0.0
        self.label = label
        self.trail = []

    def set(self, vx, vy):
        self.vx, self.vy = vx, vy
        px = self.cx + int(vx * self.r)
        py = self.cy + int(vy * self.r)
        self.trail.append((px, py))
        if len(self.trail) > 30:
            self.trail.pop(0)

    def draw(self, surf, font_sm):
        # outer ring
        pygame.draw.circle(surf, BORDER, (self.cx, self.cy), self.r, 1)
        pygame.draw.circle(surf, DARK_GRAY, (self.cx, self.cy), self.r - 1)
        # crosshair
        pygame.draw.line(surf, BORDER, (self.cx - self.r, self.cy),
                         (self.cx + self.r, self.cy), 1)
        pygame.draw.line(surf, BORDER, (self.cx, self.cy - self.r),
                         (self.cx, self.cy + self.r), 1)
        # trail
        for i, (tx, ty) in enumerate(self.trail):
            a = int(80 * i / max(len(self.trail), 1))
            col = (*ACCENT[:3],)
            s = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*ACCENT, a), (2, 2), 2)
            surf.blit(s, (tx - 2, ty - 2))
        # dot
        dot_x = self.cx + int(self.vx * self.r)
        dot_y = self.cy + int(self.vy * self.r)
        pygame.draw.circle(surf, ACCENT2, (dot_x, dot_y), 7)
        pygame.draw.circle(surf, WHITE, (dot_x, dot_y), 7, 1)
        # label
        lbl = font_sm.render(self.label, True, GRAY)
        surf.blit(lbl, (self.cx - lbl.get_width()//2, self.cy + self.r + 6))
        # value
        val = font_sm.render(f"{self.vx:+.2f}, {self.vy:+.2f}", True, WHITE)
        surf.blit(val, (self.cx - val.get_width()//2, self.cy + self.r + 22))

# ──────────────────────────────────────────────
#  TRIGGER BAR WIDGET
# ──────────────────────────────────────────────
class TriggerBar:
    def __init__(self, x, y, w, h, label='', color=ACCENT):
        self.rect = (x, y, w, h)
        self.label = label
        self.color = color
        self.value = 0.0   # –1..1 raw, displayed as 0..1

    def set(self, v):
        self.value = v

    def draw(self, surf, font_sm):
        x, y, w, h = self.rect
        draw_rounded_rect(surf, DARK_GRAY, (x, y, w, h), r=4)
        draw_rounded_rect(surf, BORDER, (x, y, w, h), r=4, border=1, border_color=BORDER)
        # normalise –1..1 → 0..1
        norm = (self.value + 1) / 2
        fill_w = int((w - 4) * norm)
        if fill_w > 0:
            draw_rounded_rect(surf, self.color, (x+2, y+2, fill_w, h-4), r=3)
        lbl = font_sm.render(self.label, True, GRAY)
        surf.blit(lbl, (x, y - 18))
        val = font_sm.render(f"{norm:.2f}", True, WHITE)
        surf.blit(val, (x + w - val.get_width(), y - 18))

# ──────────────────────────────────────────────
#  EVENT LOG
# ──────────────────────────────────────────────
class EventLog:
    def __init__(self, x, y, w, h, max_lines=14):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.max = max_lines
        self.lines = []

    def add(self, text, color=WHITE):
        self.lines.append((text, color))
        if len(self.lines) > self.max:
            self.lines.pop(0)

    def draw(self, surf, font_sm):
        draw_rounded_rect(surf, PANEL, (self.x, self.y, self.w, self.h), r=8)
        draw_rounded_rect(surf, (0,0,0,0), (self.x, self.y, self.w, self.h),
                          r=8, border=1, border_color=BORDER)
        lh = 18
        for i, (txt, col) in enumerate(self.lines):
            # fade older lines
            alpha_t = (i + 1) / max(len(self.lines), 1)
            faded = lerp_color(GRAY, col, alpha_t)
            lbl = font_sm.render(txt, True, faded)
            surf.blit(lbl, (self.x + 8, self.y + 8 + i * lh))

# ──────────────────────────────────────────────
#  D-PAD WIDGET
# ──────────────────────────────────────────────
class DPad:
    DIRS = {
        ( 0,  1): 'Up',    ( 0, -1): 'Down',
        (-1,  0): 'Left',  ( 1,  0): 'Right',
        ( 1,  1): 'Up-Right', (-1,  1): 'Up-Left',
        ( 1, -1): 'Down-Right', (-1, -1): 'Down-Left',
    }
    def __init__(self, cx, cy, size=24):
        self.cx, self.cy, self.s = cx, cy, size
        self.value = (0, 0)

    def set(self, v): self.value = v

    def draw(self, surf, font_sm):
        s = self.s
        for dx, dy, label in [
            (0, -1, '▲'), (0, 1, '▼'), (-1, 0, '◀'), (1, 0, '▶')
        ]:
            active = (self.value[0] == dx or (dx == 0 and self.value[0] == 0)) and \
                     (self.value[1] == dy or (dy == 0 and self.value[1] == 0))
            # simpler: just light up the relevant arm
            active = False
            if dx == 1  and self.value[0] > 0:  active = True
            if dx == -1 and self.value[0] < 0:  active = True
            if dy == -1 and self.value[1] > 0:  active = True
            if dy == 1  and self.value[1] < 0:  active = True

            rx = self.cx + dx * s - s//2
            ry = self.cy + dy * s - s//2  # note: pygame y-up quirk handled in hat event
            color = ACCENT if active else DARK_GRAY
            draw_rounded_rect(surf, color, (rx, ry, s, s), r=4)
            draw_rounded_rect(surf, (0,0,0,0), (rx, ry, s, s), r=4, border=1,
                              border_color=ACCENT if active else BORDER)
            t = font_sm.render(label, True, WHITE if active else GRAY)
            surf.blit(t, (rx + s//2 - t.get_width()//2, ry + s//2 - t.get_height()//2))
        # center
        draw_rounded_rect(surf, DARK_GRAY, (self.cx - s//2, self.cy - s//2, s, s), r=4)
        # label
        lbl = font_sm.render("D-Pad", True, GRAY)
        surf.blit(lbl, (self.cx - lbl.get_width()//2, self.cy + s + 4))


# ──────────────────────────────────────────────
#  MAIN (FULLY FIXED)
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='DS4 Controller Visual Debugger')
    parser.add_argument('--mode', choices=['buttons', 'triggers', 'joysticks', 'all'],
                        default='all')
    parser.add_argument('--deadzone', type=float, default=DS4Input.DEADZONE_DEFAULT,
                        help='Radial deadzone for analog sticks (0.0–0.5)')
    args = parser.parse_args()

    pygame.init()
    pygame.joystick.init()

    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("DS4 Controller Debugger")
    clock = pygame.time.Clock()

    # ── fonts ──
    try:
        font_title = pygame.font.SysFont("Courier New", 14, bold=True)
        font_sm = pygame.font.SysFont("Courier New", 12)
        font_hdr = pygame.font.SysFont("Courier New", 16, bold=True)
    except:
        font_title = pygame.font.SysFont(None, 16, bold=True)
        font_sm = pygame.font.SysFont(None, 13)
        font_hdr = pygame.font.SysFont(None, 18, bold=True)

    # ── INPUT HANDLER (single source of truth) ──
    handler = DS4Input(deadzone=args.deadzone)

    # ── widgets ──
    # Define log FIRST so callbacks can reference it
    log = EventLog(480, 120, 390, 280)

    # Attempt initial connection
    handler.init()

    # Ensure we have at least enough buttons for the standard DS4 layout
    num_buttons = max(handler.num_buttons, len(BUTTON_NAMES))

    btn_grid = ButtonGrid(30, 130, num_buttons)
    stick_L = StickWidget(110, 440, radius=55, label='Left Stick')
    stick_R = StickWidget(280, 440, radius=55, label='Right Stick')
    trig_L = TriggerBar(30, 320, 140, 20, label='L2', color=ACCENT)
    trig_R = TriggerBar(200, 320, 140, 20, label='R2', color=ACCENT2)
    dpad = DPad(cx=470, cy=430, size=26)

    # ── attach callbacks (log now exists in scope) ──
    handler.on_press = lambda name: log.add(f"▶ {name} pressed", GREEN)
    handler.on_release = lambda name: log.add(f"◀ {name} released", GRAY)
    handler.on_hat = lambda val: log.add(
        f"✦ D-Pad: {DPad.DIRS.get(val, str(val)) if val != (0, 0) else 'released'}",
        ACCENT2
    )

    # ── section labels ──
    sections = [
        (30, 105, "BUTTONS"),
        (30, 295, "TRIGGERS"),
        (30, 375, "STICKS"),
        (435, 375, "D-PAD"),
        (480, 100, "EVENT LOG"),
    ]

    # Track previous stick values to reduce log spam
    prev_lx, prev_ly = 0.0, 0.0
    prev_rx, prev_ry = 0.0, 0.0
    LOG_THRESHOLD = 0.15

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        # ── EVENT LOOP: feed all events to handler ──
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

            # Let handler consume joystick events
            handler.process_event(event)

        # ── READ STATE (BEFORE update() clears just_pressed/released!) ──
        # Buttons: update visual grid
        for i, name in enumerate(BUTTON_NAMES):
            if handler.just_pressed(name):
                btn_grid.press(i)
            elif handler.just_released(name):
                btn_grid.release(i)

        # Handle extra buttons beyond BUTTON_NAMES list
        for i in range(len(BUTTON_NAMES), handler.num_buttons):
            btn_name = f"Btn {i}"
            if handler.just_pressed(btn_name):
                btn_grid.press(i)
            elif handler.just_released(btn_name):
                btn_grid.release(i)

        # Sticks: get deadzone-processed values
        lx, ly = handler.stick_left()
        rx, ry = handler.stick_right()
        stick_L.set(lx, ly)
        stick_R.set(rx, ry)

        # Log stick movement (with deadband to reduce noise)
        if args.mode in ('all', 'joysticks'):
            if abs(lx - prev_lx) > LOG_THRESHOLD or abs(ly - prev_ly) > LOG_THRESHOLD:
                log.add(f"~ Left Stick: ({lx:+.2f}, {ly:+.2f})", ACCENT)
                prev_lx, prev_ly = lx, ly
            if abs(rx - prev_rx) > LOG_THRESHOLD or abs(ry - prev_ry) > LOG_THRESHOLD:
                log.add(f"~ Right Stick: ({rx:+.2f}, {ry:+.2f})", ACCENT)
                prev_rx, prev_ry = rx, ry

        # Triggers: get normalized 0..1 values
        l2 = handler.trigger_left()
        r2 = handler.trigger_right()
        trig_L.set(l2 * 2 - 1)  # Convert back to -1..1 for TriggerBar display
        trig_R.set(r2 * 2 - 1)

        if args.mode in ('all', 'triggers'):
            if abs(l2 - 0.5) > 0.1:  # Log when trigger moves significantly from rest
                log.add(f"~ L2: {l2:.2f}", YELLOW)
            if abs(r2 - 0.5) > 0.1:
                log.add(f"~ R2: {r2:.2f}", YELLOW)

        # D-Pad: raw hat value
        hat = handler.dpad()
        dpad.set(hat)

        # ── UPDATE: clear frame-state sets (AFTER reading state!) ──
        handler.update()
        btn_grid.update(dt)

        # ── DRAW ──
        screen.fill(BG)

        # Header bar
        pygame.draw.rect(screen, PANEL, (0, 0, W, 80))
        pygame.draw.line(screen, BORDER, (0, 80), (W, 80), 1)

        title = font_hdr.render("DS4  CONTROLLER  DEBUGGER", True, WHITE)
        screen.blit(title, (30, 18))

        mode_lbl = font_sm.render(f"MODE: {args.mode.upper()} | DEADZONE: {args.deadzone:.2f}", True, ACCENT)
        screen.blit(mode_lbl, (30, 44))

        # Connection status from handler
        status_color = GREEN if handler.connected else ACCENT2
        status_txt = f"✓ {handler.name}" if handler.connected else "⚠ No controller"
        name_lbl = font_sm.render(status_txt, True, status_color)
        screen.blit(name_lbl, (W - name_lbl.get_width() - 30, 18))

        if handler.connected:
            info = font_sm.render(
                f"axes:{handler.num_axes}  buttons:{handler.num_buttons}  hats:{handler.num_hats}",
                True, GRAY)
            screen.blit(info, (W - info.get_width() - 30, 40))
        else:
            hint = font_sm.render("→ Plug in DS4 and press any button to connect", True, GRAY)
            screen.blit(hint, (W - hint.get_width() - 30, 40))

        # Section headers
        for sx, sy, label in sections:
            lbl = font_title.render(label, True, ACCENT)
            screen.blit(lbl, (sx, sy))
            pygame.draw.line(screen, BORDER, (sx, sy + 16),
                             (sx + lbl.get_width() + 60, sy + 16), 1)

        # Widgets
        btn_grid.draw(screen, font_sm)
        stick_L.draw(screen, font_sm)
        stick_R.draw(screen, font_sm)
        trig_L.draw(screen, font_sm)
        trig_R.draw(screen, font_sm)
        dpad.draw(screen, font_sm)
        log.draw(screen, font_sm)

        # Footer
        fps_lbl = font_sm.render(f"{clock.get_fps():.0f} fps", True, BORDER)
        screen.blit(fps_lbl, (W - 54, H - 20))
        esc_lbl = font_sm.render("ESC to quit", True, BORDER)
        screen.blit(esc_lbl, (30, H - 20))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()