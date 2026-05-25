import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()

from src.game import Game, GameplayState, PauseState

def main():
    print("Initializing Game...")
    g = Game()
    g.clock = pygame.time.Clock()
    
    # Verify State Manager push
    print("Transitioning to GameplayState...")
    gp = GameplayState(g)
    g.state_manager.push(gp)
    
    # Tick a few frames to generate engine trail points
    print("Simulating gameplay frame ticks...")
    for frame in range(10):
        dt = 0.016
        g.state_manager.current.update(dt, g.state_manager)
        
    print(f"Generated {len(gp.player.engine_trail)} engine trail particles successfully!")
    assert len(gp.player.engine_trail) > 0, "No engine trail particles generated!"
    
    # Push PauseState
    print("Transitioning to PauseState...")
    ps = PauseState(g)
    g.state_manager.push(ps)
    
    # Verify trail color cycling
    initial_color_idx = gp.player.trail_color_index
    print(f"Initial color: {gp.player.trail_color_name} (Index {initial_color_idx})")
    
    gp.player.change_trail_color(1)
    new_color_idx = gp.player.trail_color_index
    print(f"Cycled color: {gp.player.trail_color_name} (Index {new_color_idx})")
    assert new_color_idx != initial_color_idx, "Trail color did not cycle!"
    
    # Verify manual orbit updates
    initial_yaw = ps.orbit_yaw
    initial_pitch = ps.orbit_pitch
    print(f"Initial camera orbit - Yaw: {initial_yaw:.3f}, Pitch: {initial_pitch:.3f}")
    
    # Simulate right stick movement (manual rotation) on the gamepad handler
    g.handler._axes[3] = 0.5  # Simulate Right Stick X input
    g.handler._axes[4] = -0.5 # Simulate Right Stick Y input
    
    # Run PauseState updates
    dt = 0.016
    g.state_manager.current.update(dt, g.state_manager)
    
    new_yaw = ps.orbit_yaw
    new_pitch = ps.orbit_pitch
    print(f"Updated camera orbit - Yaw: {new_yaw:.3f}, Pitch: {new_pitch:.3f}")
    assert new_yaw != initial_yaw or new_pitch != initial_pitch, "Camera orbit coordinates did not update with analog stick input!"
    
    # Verify drawing flow under pause state
    print("Simulating PauseState render pass...")
    test_screen = pygame.Surface((g.W, g.H))
    g.state_manager.current.draw(test_screen)
    
    print("\n[SUCCESS] Headless integration tests completed successfully with no exceptions!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        exit(1)
