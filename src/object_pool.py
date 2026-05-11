"""
Object Pooling System
Efficiently manages reusable game objects to avoid frequent allocation/deallocation.
"""

from typing import List, Callable, Optional, TypeVar, Generic
import random

T = TypeVar('T')

# Particle colors palette (matches original Particle class)
_PARTICLE_COLORS = [(255, 100, 50), (255, 200, 50), (100, 100, 100)]


class ObjectPool(Generic[T]):
    """Generic object pool for managing reusable entities."""
    
    def __init__(self, 
                 factory: Callable[[], T],
                 reset_func: Optional[Callable[[T], None]] = None,
                 initial_size: int = 50,
                 max_size: Optional[int] = None):
        """
        Initialize the object pool.
        
        Args:
            factory: Function that creates new instances of type T
            reset_func: Optional function to reset an object before reuse
            initial_size: Number of objects to pre-allocate
            max_size: Maximum pool size (None for unlimited)
        """
        self._factory = factory
        self._reset_func = reset_func or self._default_reset
        self._max_size = max_size
        self._available: List[T] = []
        self._in_use: List[T] = []
        
        # Pre-allocate initial objects
        for _ in range(initial_size):
            self._available.append(self._factory())
    
    def _default_reset(self, obj: T) -> None:
        """Default reset does nothing - override for specific types."""
        pass
    
    def acquire(self, *args, **kwargs) -> Optional[T]:
        """
        Acquire an object from the pool.
        
        Returns None if pool is exhausted and at max_size.
        Note: Caller is responsible for initializing the object with provided args.
        """
        if self._available:
            obj = self._available.pop()
        elif self._max_size is None or len(self._in_use) < self._max_size:
            obj = self._factory()
        else:
            return None
        
        self._in_use.append(obj)
        return obj
    
    def release(self, obj: T) -> None:
        """Return an object to the pool for reuse."""
        if obj in self._in_use:
            self._in_use.remove(obj)
            self._reset_func(obj)
            
            if self._max_size is None or len(self._available) < self._max_size:
                self._available.append(obj)
    
    def release_all(self) -> None:
        """Return all in-use objects to the pool."""
        for obj in self._in_use[:]:
            self.release(obj)
    
    def get_active_count(self) -> int:
        """Get number of objects currently in use."""
        return len(self._in_use)
    
    def get_available_count(self) -> int:
        """Get number of objects available in pool."""
        return len(self._available)
    
    def get_total_count(self) -> int:
        """Get total number of objects managed by pool."""
        return len(self._in_use) + len(self._available)
    
    def shrink(self, target_size: int) -> None:
        """Remove excess objects from the pool to reduce memory."""
        while len(self._available) > target_size:
            self._available.pop()


class ParticlePool:
    """Specialized high-performance pool for particle effects using parallel lists."""
    
    def __init__(self, particle_class=None, initial_size: int = 500, max_size: int = 2000):
        self.max_size = max_size
        
        # Parallel lists for particle data (much faster than list of dicts)
        self.px = [0.0] * max_size
        self.py = [0.0] * max_size
        self.pz = [0.0] * max_size
        self.vx = [0.0] * max_size
        self.vy = [0.0] * max_size
        self.vz = [0.0] * max_size
        self.life = [0.0] * max_size
        self.max_life = [1.0] * max_size
        self.color = [(255, 255, 255)] * max_size
        self.active = [False] * max_size
        
        # Free indices stack for O(1) allocation
        self.free_indices = list(range(max_size - 1, -1, -1))
        self.active_indices = set()
    
    def spawn(self, x: float, y: float, z: float, 
              velocity_range: tuple = (-300, 300),
              life: float = 1.0,
              colors: Optional[list] = None) -> None:
        """Spawn a particle at the given position."""
        if not self.free_indices:
            return
            
        idx = self.free_indices.pop()
        self.active_indices.add(idx)
        
        self.px[idx] = x
        self.py[idx] = y
        self.pz[idx] = z
        self.vx[idx] = random.uniform(*velocity_range)
        self.vy[idx] = random.uniform(*velocity_range)
        self.vz[idx] = random.uniform(*velocity_range)
        self.life[idx] = life
        self.max_life[idx] = life
        self.color[idx] = random.choice(colors) if colors else random.choice(_PARTICLE_COLORS)
        self.active[idx] = True
    
    def update(self, dt: float) -> None:
        """Update all active particles and recycle dead ones."""
        to_remove = []
        for idx in self.active_indices:
            self.px[idx] += self.vx[idx] * dt
            self.py[idx] += self.vy[idx] * dt
            self.pz[idx] += self.vz[idx] * dt
            self.life[idx] -= dt
            
            if self.life[idx] <= 0:
                self.active[idx] = False
                to_remove.append(idx)
        
        for idx in to_remove:
            self.active_indices.remove(idx)
            self.free_indices.append(idx)
    
    def submit_to_renderer(self, renderer, camera):
        """Batch submit active particles to the renderer with frustum culling."""
        for idx in self.active_indices:
            x, y, z = self.px[idx], self.py[idx], self.pz[idx]
            # Fast distance-based culling before heavy sphere-in-frustum
            # (Assuming camera.pos is available via player in game.py, 
            # but renderer has access to camera)
            if camera.sphere_in_frustum(x, y, z, 50):
                ratio = self.life[idx] / self.max_life[idx]
                renderer.submit_sprite(x, y, z, self.color[idx], 15 * ratio, layer='alpha')

    def get_active_particles(self) -> List[dict]:
        """Legacy shim for compatibility with existing game.py loops."""
        results = []
        for idx in self.active_indices:
            results.append({
                'x': self.px[idx], 'y': self.py[idx], 'z': self.pz[idx],
                'life': self.life[idx] / self.max_life[idx],
                'color': self.color[idx],
                'active': True
            })
        return results

    def get_active_count(self) -> int:
        return len(self.active_indices)
    
    def clear(self) -> None:
        """Clear all active particles."""
        for idx in self.active_indices:
            self.active[idx] = False
            self.free_indices.append(idx)
        self.active_indices.clear()



class LaserPool:
    """Specialized pool for laser projectiles."""
    
    def __init__(self, laser_class, initial_size: int = 30, max_size: int = 100):
        self._laser_class = laser_class
        self._pool: List[object] = []
        self._active: List[object] = []
        self._max_size = max_size
        
        for _ in range(initial_size):
            self._pool.append(laser_class())
    
    def fire(self, x: float, y: float, z: float, 
             vx: float, vy: float, vz: float,
             life: float = 2.0) -> Optional[object]:
        """Fire a laser from the given position with the given velocity."""
        if self._pool:
            laser = self._pool.pop()
        elif self._max_size is None or len(self._active) < self._max_size:
            laser = self._laser_class()
        else:
            return None
        
        # Initialize laser (assumes laser has init method)
        if hasattr(laser, 'init'):
            laser.init(x, y, z, vx, vy, vz, life)
        else:
            # Fallback: set attributes directly
            laser.x, laser.y, laser.z = x, y, z
            laser.vx, laser.vy, laser.vz = vx, vy, vz
            laser.life = life
        
        self._active.append(laser)
        return laser
    
    def update(self, dt: float) -> None:
        """Update all active lasers and recycle expired ones."""
        still_active = []
        for laser in self._active:
            if hasattr(laser, 'update'):
                laser.update(dt)
            
            if getattr(laser, 'life', 0) <= 0:
                if len(self._pool) < self._max_size:
                    self._pool.append(laser)
            else:
                still_active.append(laser)
        self._active = still_active
    
    def get_active(self) -> List[object]:
        """Get list of active lasers."""
        return self._active
    
    def get_active_count(self) -> int:
        """Get number of active lasers."""
        return len(self._active)
    
    def clear(self) -> None:
        """Clear all active lasers."""
        self._pool.extend(self._active)
        self._active.clear()
