import threading, time, pygame
from src.game import Game
from src.enemy import Dogfighter, Sniper
from src.math_engine import get_forward_from_quat, get_basis_from_quat

g = Game()

def action():
    time.sleep(2)
    g.player.throttle = 1.0
    time.sleep(3)
    # spawn hostiles ahead of the player
    fx, fy, fz = get_forward_from_quat(g.player.orientation)
    px, py, pz = g.player.pos
    ax, ay, az = px + fx*1400, py + fy*1400, pz + fz*1400
    g.enemies.append(Dogfighter(ax - 250, ay + 100, az))
    g.enemies.append(Dogfighter(ax + 250, ay - 80, az))
    g.enemies.append(Sniper(ax, ay + 300, az + 200))
    # fire a volley from the player
    forward, right, _ = get_basis_from_quat(g.player.orientation)
    for side in (-1, 1):
        g.laser_pool.fire(
            px + right[0]*40*side + forward[0]*70,
            py + right[1]*40*side + forward[1]*70,
            pz + right[2]*40*side + forward[2]*70,
            forward[0]*16000, forward[1]*16000, forward[2]*16000)
    time.sleep(2.5)
    pygame.image.save(g.screen, "/tmp/space3d/shot2.png")
    pygame.event.post(pygame.event.Event(pygame.QUIT))

threading.Thread(target=action, daemon=True).start()
g.main()
print("saved2")
