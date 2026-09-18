import threading, time, pygame
from src.game import Game

g = Game()

def shooter():
    time.sleep(2)
    g.player.throttle = 1.0  # fly forward into the action
    time.sleep(10)
    pygame.image.save(g.screen, "/tmp/space3d/shot.png")
    pygame.event.post(pygame.event.Event(pygame.QUIT))

threading.Thread(target=shooter, daemon=True).start()
g.main()
print("saved")
