import random
import math
import pygame

class NebulaCloud:
    def __init__(self, x, y, z, color=None, num_puffs=10, radius=1000):
        self.x, self.y, self.z = x, y, z

        palette = [
            (180, 50, 255),
            (50, 255, 220),
            (50, 100, 255),
            (255, 100, 50),
            (255, 50, 150),
            (100, 255, 50)
        ]
        self.color = color if color else random.choice(palette)
        self.radius = radius

        self.puffs = []
        for _ in range(num_puffs):
            ox = random.uniform(-radius, radius)
            oy = random.uniform(-radius, radius)
            oz = random.uniform(-radius, radius)
            p_size = random.uniform(radius * 0.5, radius * 1.5)
            p_alpha = random.randint(20, 50)
            self.puffs.append({
                'rel_pos': (ox, oy, oz),
                'size': p_size,
                'alpha': p_alpha
            })

        # Pre-rendered surface — built once, blitted every frame
        self._surface = None          # pygame.Surface, screen-space size
        self._world_radius = radius * 2.0  # bounding sphere for the billboard

    def build_cache(self, puff_texture_fn):
        """
        Pre-render all puffs onto a single surface in normalised space.
        Call once after construction — before the game loop starts.

        puff_texture_fn(size) -> pygame.Surface  (white SRCALPHA radial gradient)
        This lets us reuse RenderPipeline._create_puff_texture.
        """
        # Work in a normalised canvas: radius=1 unit = CANVAS_R pixels
        CANVAS_R = 256
        canvas_size = CANVAS_R * 2
        surf = pygame.Surface((canvas_size, canvas_size), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))

        # Bake the colour tint once
        r, g, b = self.color

        for p in self.puffs:
            ox, oy, _ = p['rel_pos']   # ignore Z — project to 2-D billboard
            p_size     = p['size']
            p_alpha    = p['alpha']

            # Map world-space offset/size → canvas pixels
            cx = int(CANVAS_R + (ox / self._world_radius) * CANVAS_R)
            cy = int(CANVAS_R + (oy / self._world_radius) * CANVAS_R)
            pr = max(2, int((p_size / self._world_radius) * CANVAS_R))

            # Draw gradient circle directly — no surface per puff
            for ring in range(pr, 0, -max(1, pr // 16)):
                frac  = ring / pr
                alpha = int(p_alpha * (1.0 - frac ** 1.5))
                pygame.draw.circle(
                    surf,
                    (r, g, b, alpha),
                    (cx, cy),
                    ring
                )

        self._surface = surf.convert_alpha()

    def submit_to_renderer(self, renderer):
        if self._surface is None:
            return
        renderer.submit_nebula_cloud(
            self.x, self.y, self.z,
            self._surface,
            self._world_radius
        )


class NebulaSystem:
    def __init__(self, count=5, area_radius=15000):
        self.clouds = []
        for _ in range(count):
            nx = random.uniform(-area_radius, area_radius)
            ny = random.uniform(-area_radius, area_radius)
            nz = random.uniform(2000, area_radius * 2)
            self.clouds.append(
                NebulaCloud(nx, ny, nz, radius=random.uniform(2000, 5000))
            )

    def build_caches(self, puff_texture_fn):
        """Call once after construction, before the game loop."""
        for cloud in self.clouds:
            cloud.build_cache(puff_texture_fn)

    def submit_to_renderer(self, renderer):
        for cloud in self.clouds:
            cloud.submit_to_renderer(renderer)

class NebulaSystem:
    def __init__(self, count=5, area_radius=15000):
        self.clouds = []
        for _ in range(count):
            # Spawn clouds in a large area around the scene
            nx = random.uniform(-area_radius, area_radius)
            ny = random.uniform(-area_radius, area_radius)
            nz = random.uniform(2000, area_radius * 2) # Mostly in front
            
            self.clouds.append(NebulaCloud(nx, ny, nz, radius=random.uniform(2000, 5000)))

    def build_caches(self, puff_texture_fn):
        """Call once after construction, before the game loop."""
        for cloud in self.clouds:
            cloud.build_cache(puff_texture_fn) 

    def submit_to_renderer(self, renderer):
        for cloud in self.clouds:
            cloud.submit_to_renderer(renderer)
