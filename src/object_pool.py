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
    """Specialized pool for particle effects with position-based initialization."""
    
    def __init__(self, particle_class, initial_size: int = 200, max_size: int = 1000):
        self._particle_class = particle_class
        self._pool: List[dict] = []
        self._active: List[dict] = []
        self._max_size = max_size
        
        # Pre-allocate particle data dictionaries
        for _ in range(initial_size):
            self._pool.append(self._create_particle_data())
    
    def _create_particle_data(self) -> dict:
        """Create a new particle data structure."""
        return {
            'x': 0.0, 'y': 0.0, 'z': 0.0,
            'vx': 0.0, 'vy': 0.0, 'vz': 0.0,
            'life': 0.0,
            'color': (255, 100, 50),
            'active': False
        }
    
    def spawn(self, x: float, y: float, z: float, 
              velocity_range: tuple = (-300, 300),
              life: float = 1.0,
              colors: Optional[list] = None) -> Optional[dict]:
        """Spawn a particle at the given position."""
        if self._pool:
            particle = self._pool.pop()
        elif self._max_size is None or len(self._active) < self._max_size:
            particle = self._create_particle_data()
        else:
            return None
        
        # Initialize particle
        particle['x'] = x
        particle['y'] = y
        particle['z'] = z
        particle['vx'] = random.uniform(*velocity_range)
        particle['vy'] = random.uniform(*velocity_range)
        particle['vz'] = random.uniform(*velocity_range)
        particle['life'] = life
        particle['color'] = random.choice(colors) if colors else random.choice(_PARTICLE_COLORS)
        particle['active'] = True
        
        self._active.append(particle)
        return particle
    
    def update(self, dt: float) -> None:
        """Update all active particles and recycle dead ones."""
        for particle in self._active[:]:
            if not particle['active']:
                continue
                
            # Update position
            particle['x'] += particle['vx'] * dt
            particle['y'] += particle['vy'] * dt
            particle['z'] += particle['vz'] * dt
            particle['life'] -= dt
            
            # Recycle if dead
            if particle['life'] <= 0:
                particle['active'] = False
                self._active.remove(particle)
                if len(self._pool) < self._max_size:
                    self._pool.append(particle)
    
    def get_active_particles(self) -> List[dict]:
        """Get list of currently active particles."""
        return [p for p in self._active if p['active']]
    
    def get_active_count(self) -> int:
        """Get number of active particles."""
        return sum(1 for p in self._active if p['active'])
    
    def clear(self) -> None:
        """Clear all active particles."""
        for particle in self._active:
            particle['active'] = False
        self._pool.extend(self._active)
        self._active.clear()


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
        for laser in self._active[:]:
            if hasattr(laser, 'update'):
                laser.update(dt)
            
            if getattr(laser, 'life', 0) <= 0:
                self._active.remove(laser)
                if len(self._pool) < self._max_size:
                    self._pool.append(laser)
    
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
