import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

from src.game import Game
import pygame

try:
    g = Game()
    g.clock = pygame.time.Clock()
    for _ in range(10):
        dt = 0.016
        g.player.update(dt, g.handler, pygame.key.get_pressed(), g.laser_pool, g.particle_pool, g.enemy_projectiles, g.player_missiles, g.sound)
        g.update_entities(dt, g.player, g.enemies, g.enemy_projectiles)
        g.director.update(dt, g.player.pos, g.player.orientation, g.enemies)
        
        # Test particle spawn and update
        g.particle_pool.spawn(0,0,0)
        
        g.draw_game(g.screen, g.W, g.H, g.player, g.stars, g.enemies, g.enemy_projectiles, dt)
    print("Test passed successfully!")
except Exception as e:
    import traceback
    traceback.print_exc()

pygame.quit()
