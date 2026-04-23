import pygame

def draw_cockpit_hud(surf, W, H, throttle, weapons_ready):
    pygame.draw.rect(surf, (30, 40, 80), (0, 0, W, H), 8)
    pygame.draw.rect(surf, (80, 140, 255), (4, 4, W - 8, H - 8), 2)

    cx, cy = W // 2, H // 2
    pygame.draw.circle(surf, (80, 255, 140), (cx, cy), 3)
    pygame.draw.line(surf, (80, 255, 140), (cx - 20, cy), (cx - 8, cy), 2)
    pygame.draw.line(surf, (80, 255, 140), (cx + 8, cy), (cx + 20, cy), 2)
    pygame.draw.line(surf, (80, 255, 140), (cx, cy - 20), (cx, cy - 8), 2)
    pygame.draw.line(surf, (80, 255, 140), (cx, cy + 8), (cx, cy + 20), 2)

    bar_h = 200
    pygame.draw.rect(surf, (40, 40, 60), (W - 40, H // 2 - bar_h // 2, 20, bar_h))
    fill_h = int(bar_h * throttle)
    pygame.draw.rect(surf, (60, 220, 120), (W - 40, H // 2 + bar_h // 2 - fill_h, 20, fill_h))
    pygame.draw.rect(surf, (80, 140, 255), (W - 40, H // 2 - bar_h // 2, 20, bar_h), 1)

    status = "ARMED" if weapons_ready else "COOLING"
    color = (60, 220, 120) if weapons_ready else (255, 100, 100)
    font = pygame.font.SysFont("Courier", 14, bold=True)
    surf.blit(font.render(status, True, color), (W - 120, 20))

    speed = f"{int(throttle * 2500):04d} KM/H"
    surf.blit(pygame.font.SysFont("Courier", 24, bold=True).render(speed, True, (200, 220, 255)), (20, 20))

