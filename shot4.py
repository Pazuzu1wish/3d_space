import threading, time, pygame
from src.game import Game
from src.enemy import Dogfighter, Sniper
from src.math_engine import get_forward_from_quat, get_basis_from_quat

g = Game()

def action():
    time.sleep(2)
    g.player.throttle = 0.0
    fx, fy, fz = get_forward_from_quat(g.player.orientation)
    px, py, pz = g.player.pos
    # dogfighters at good visual range, sniper further back
    g.enemies.append(Dogfighter(px + fx*1100 - 220, py + fy*1100 + 80, pz + fz*1100))
    g.enemies.append(Dogfighter(px + fx*1200 + 240, py + fy*1200 - 60, pz + fz*1200))
    g.enemies.append(Sniper(px + fx*1600, py + fy*1600 + 150, pz + fz*1600))
    forward, right, _ = get_basis_from_quat(g.player.orientation)
    for volley in range(4):
        for side in (-1, 1):
            g.laser_pool.fire(
                px + right[0]*40*side + forward[0]*70,
                py + right[1]*40*side + forward[1]*70,
                pz + right[2]*40*side + forward[2]*70,
                forward[0]*16000, forward[1]*16000, forward[2]*16000)
        time.sleep(0.3)
    # clean frame: no damage overlay, no incoming fire
    g.player.hit_flash = 0
    g.enemy_projectiles.clear()
    time.sleep(0.1)
    pygame.image.save(g.screen, "/tmp/space3d/shot4.png")
    pygame.event.post(pygame.event.Event(pygame.QUIT))

threading.Thread(target=action, daemon=True).start()
g.main()
print("saved4")
