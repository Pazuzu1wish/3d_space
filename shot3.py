import threading, time, pygame
from src.game import Game
from src.enemy import Dogfighter, Sniper, Corvette
from src.math_engine import get_forward_from_quat, get_basis_from_quat

g = Game()

def action():
    time.sleep(2)
    g.player.throttle = 0.0
    fx, fy, fz = get_forward_from_quat(g.player.orientation)
    px, py, pz = g.player.pos
    # hostiles close and visible
    g.enemies.append(Dogfighter(px + fx*650 - 180, py + fy*650 + 60, pz + fz*650))
    g.enemies.append(Dogfighter(px + fx*700 + 200, py + fy*700 - 40, pz + fz*700))
    g.enemies.append(Corvette(px + fx*900, py + fy*900 + 120, pz + fz*900))
    # staggered volleys so bolts are mid-flight at capture
    forward, right, _ = get_basis_from_quat(g.player.orientation)
    for volley in range(3):
        for side in (-1, 1):
            g.laser_pool.fire(
                px + right[0]*40*side + forward[0]*70,
                py + right[1]*40*side + forward[1]*70,
                pz + right[2]*40*side + forward[2]*70,
                forward[0]*16000, forward[1]*16000, forward[2]*16000)
        time.sleep(0.35)
    time.sleep(0.15)
    pygame.image.save(g.screen, "/tmp/space3d/shot3.png")
    pygame.event.post(pygame.event.Event(pygame.QUIT))

threading.Thread(target=action, daemon=True).start()
g.main()
print("saved3")
