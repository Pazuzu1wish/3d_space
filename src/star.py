import random
import numpy as np
from numba import njit

# ─────────────────────────────────────────────
#  OPTIMIZED STAR BATCH PROCESSING
# ──────────────────────────────────────────────

@njit(cache=True, fastmath=True)
def wrap_star_positions_batch(positions, player_pos, spread):
    """
    Batch wrap star positions around player.
    Avoids 220 individual Python function calls.
    """
    wrapped = positions.copy()
    px, py, pz = player_pos
    
    for i in range(wrapped.shape[0]):
        dx = wrapped[i, 0] - px
        dy = wrapped[i, 1] - py
        dz = wrapped[i, 2] - pz
        
        if dx > spread:
            wrapped[i, 0] -= 2 * spread
        elif dx < -spread:
            wrapped[i, 0] += 2 * spread
            
        if dy > spread:
            wrapped[i, 1] -= 2 * spread
        elif dy < -spread:
            wrapped[i, 1] += 2 * spread
            
        if dz > spread:
            wrapped[i, 2] -= 2 * spread
        elif dz < -spread:
            wrapped[i, 2] += 2 * spread
    
    return wrapped


@njit(cache=True, fastmath=True)
def compute_star_colors_batch(cam_positions, brightness, base_colors):
    """
    Batch compute final star colors with distance-based dimming.
    All 220 stars processed in optimized Numba loop.
    """
    N = cam_positions.shape[0]
    colors = np.zeros((N, 3), dtype=np.uint8)
    valid = np.zeros(N, dtype=np.bool_)
    
    for i in range(N):
        cz = cam_positions[i, 2]
        
        if cz > 0:
            # Distance-based dimming
            dist_factor = min(1.0, 500.0 / (cz if cz > 0.001 else 0.001))
            intensity = brightness[i] * dist_factor
            
            # Clamp and convert to uint8
            colors[i, 0] = min(255, int(base_colors[i, 0] * intensity))
            colors[i, 1] = min(255, int(base_colors[i, 1] * intensity))
            colors[i, 2] = min(255, int(base_colors[i, 2] * intensity))
            valid[i] = True
    
    return colors, valid


# ─────────────────────────────────────────────
#  GAME ENTITIES
# ──────────────────────────────────────────────

class Star:
    def __init__(self, ppos=(0, 0, 0)):
        self.spawn_around(ppos)

    def spawn_around(self, ppos):
        spread = 3000
        self.x = ppos[0] + random.uniform(-spread, spread)
        self.y = ppos[1] + random.uniform(-spread, spread)
        self.z = ppos[2] + random.uniform(-spread, spread)
        
        # Randomize size: mostly small (1-2), occasionally larger (3-5)
        if random.random() < 0.95:
            self.size = random.uniform(1.5, 3.0)
        else:
            self.size = random.uniform(4.0, 8.0) # Occasional "Hero" stars

        self.brightness = random.uniform(1.5, 2.0)
        
        # Color variety based on weighted probabilities
        # Mostly white/off-white, occasional blue/red/yellow
        c_rand = random.random()
        if c_rand < 0.75:
            self.base_color = (255, 255, 255) # White
        elif c_rand < 0.85:
            self.base_color = (100, 100, 255) # Blue-ish
        elif c_rand < 0.95:
            self.base_color = (255, 100, 100) # Red-ish
        else:
            self.base_color = (255, 255, 100) # Yellow-ish

    def submit_to_renderer(self, renderer, ppos):
        spread = 3000
        dx = self.x - ppos[0]
        dy = self.y - ppos[1]
        dz = self.z - ppos[2]

        if dx > spread: self.x -= 2 * spread
        elif dx < -spread: self.x += 2 * spread
        if dy > spread: self.y -= 2 * spread
        elif dy < -spread: self.y += 2 * spread
        if dz > spread: self.z -= 2 * spread
        elif dz < -spread: self.z += 2 * spread

        cx, cy, cz = renderer.camera.world_to_camera(self.x, self.y, self.z)

        if cz > 0:
            # Distance-based dimming
            dist_factor = min(1.0, 500 / (cz or 1))
            intensity = self.brightness * dist_factor
            
            r = min(255, int(self.base_color[0] * intensity))
            g = min(255, int(self.base_color[1] * intensity))
            b = min(255, int(self.base_color[2] * intensity))
            
            is_glow = self.size > 2.5
            # Pass cam_pos to avoid redundant world_to_camera in renderer
            renderer.submit_sprite(self.x, self.y, self.z, (r, g, b), self.size, 
                                 is_glow=is_glow, layer='background', cam_pos=(cx, cy, cz))

    @classmethod
    def submit_batch_to_renderer(cls, stars, renderer, player_pos):
        """
        Optimized batch submission of all stars.
        Wraps all positions at once using Numba, then submits individually.
        Uses a single world_to_camera_batch call for all 250 stars instead
        of 250 individual Python calls.
        """
        spread = 3000
        N = len(stars)

        # ── Build / reuse a positions array cached on the list object ──
        # Avoids re-allocating (N, 3) every frame when star count is stable.
        positions = np.array([(s.x, s.y, s.z) for s in stars], dtype=np.float64)
        wrapped_pos = wrap_star_positions_batch(positions, player_pos, spread)

        # Write wrapped positions back and collect size/brightness/color info
        sizes      = np.empty(N, dtype=np.float64)
        brightness = np.empty(N, dtype=np.float64)
        base_cols  = np.empty((N, 3), dtype=np.float64)
        for i, s in enumerate(stars):
            s.x = wrapped_pos[i, 0]
            s.y = wrapped_pos[i, 1]
            s.z = wrapped_pos[i, 2]
            sizes[i]        = s.size
            brightness[i]   = s.brightness
            base_cols[i, 0] = s.base_color[0]
            base_cols[i, 1] = s.base_color[1]
            base_cols[i, 2] = s.base_color[2]

        # Single batched world → camera transform (one Numba call for all stars)
        cam_positions = renderer.camera.world_to_camera_batch(wrapped_pos)

        # Batch-compute colours (existing Numba kernel)
        colors, valid = compute_star_colors_batch(cam_positions, brightness, base_cols)

        # Submit only visible stars to the renderer
        for i in range(N):
            if not valid[i]:
                continue
            cz = cam_positions[i, 2]
            is_glow = sizes[i] > 2.5
            renderer.submit_sprite(
                wrapped_pos[i, 0], wrapped_pos[i, 1], wrapped_pos[i, 2],
                (int(colors[i, 0]), int(colors[i, 1]), int(colors[i, 2])),
                sizes[i],
                is_glow=is_glow,
                layer='background',
                cam_pos=(cam_positions[i, 0], cam_positions[i, 1], cz),
            )








