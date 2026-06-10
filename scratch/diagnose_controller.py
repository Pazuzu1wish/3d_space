import pygame
import time
import sys

pygame.init()
pygame.joystick.init()

from src.controller import DS4Input

print("=== Controller Diagnosis ===")
print(f"Total joysticks found: {pygame.joystick.get_count()}")

for i in range(pygame.joystick.get_count()):
    joy = pygame.joystick.Joystick(i)
    joy.init()
    print(f"Joystick {i}: name='{joy.get_name()}', axes={joy.get_numaxes()}, buttons={joy.get_numbuttons()}, hats={joy.get_numhats()}")
    joy.quit()

handler = DS4Input(joystick_index=0)
success = handler.init()
print(f"\nHandler init success: {success}")
if success:
    print(f"Detected Controller Name: {handler.name}")
    print(f"Is SDL Controller: {handler._is_sdl_controller}")
    print(f"Number of Axes: {handler.num_axes}")
    print(f"Number of Buttons: {handler.num_buttons}")
    print(f"Number of Hats: {handler.num_hats}")
    print(f"Rumble Supported: {handler.rumble_supported}")
    if not handler._is_sdl_controller:
        print(f"Raw Axis Map: {handler._axis_map}")
        print(f"Raw Button Map: {handler._button_map}")

    print("\nPolling inputs for 3 seconds (please move stick/triggers)...")
    start = time.time()
    last_print = 0.0
    while time.time() - start < 3.0:
        pygame.event.pump()
        for event in pygame.event.get():
            handler.process_event(event)
        
        now = time.time()
        if now - last_print > 0.2:
            lx, ly = handler.stick_left()
            rx, ry = handler.stick_right()
            l2 = handler.trigger_left()
            r2 = handler.trigger_right()
            print(f"Time: {now - start:.1f}s | StickL: ({lx:+.2f}, {ly:+.2f}) | StickR: ({rx:+.2f}, {ry:+.2f}) | L2: {l2:.2f} | R2: {r2:.2f} | Raw Axes: {dict(handler._axes)}")
            last_print = now
            time.sleep(0.05)
else:
    print("No controller could be initialized.")

pygame.quit()
