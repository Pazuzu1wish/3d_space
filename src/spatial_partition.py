"""
Spatial Partitioning System
Efficient collision detection and entity culling using spatial hash grid.
"""

import math
from typing import List, Optional, Tuple, Set

class SpatialHash:
    """
    Efficient spatial partitioning using a hash grid.
    Optimized for fast insertion, removal, and incremental updates.
    """
    
    def __init__(self, cell_size: float = 500.0):
        self.cell_size = cell_size
        self.inv_cell_size = 1.0 / cell_size
        self.grid: dict = {}
    
    def _hash_position(self, x: float, y: float, z: float) -> Tuple[int, int, int]:
        """Convert world position to grid cell coordinates using fast truncation."""
        return (
            int(x * self.inv_cell_size),
            int(y * self.inv_cell_size),
            int(z * self.inv_cell_size)
        )
    
    def insert(self, entity: object, pos: Tuple[float, float, float]) -> None:
        """Insert an entity into the spatial hash."""
        cell = self._hash_position(*pos)
        if cell not in self.grid:
            self.grid[cell] = []
        self.grid[cell].append(entity)
    
    def remove(self, entity: object, pos: Tuple[float, float, float]) -> bool:
        """Remove an entity from the spatial hash."""
        cell = self._hash_position(*pos)
        if cell in self.grid:
            try:
                self.grid[cell].remove(entity)
                if not self.grid[cell]:
                    del self.grid[cell]
                return True
            except ValueError:
                return False
        return False

    def move(self, entity: object, old_pos: Tuple[float, float, float], 
             new_pos: Tuple[float, float, float]) -> None:
        """Incrementally move an entity between cells."""
        old_cell = self._hash_position(*old_pos)
        new_cell = self._hash_position(*new_pos)
        
        if old_cell != new_cell:
            self.remove(entity, old_pos)
            self.insert(entity, new_pos)
    
    def query_radius(self, center: Tuple[float, float, float],
                      radius: float) -> List[object]:
        """Query all entities within a sphere."""
        results = []
        
        # Calculate range of cells to check
        cx, cy, cz = self._hash_position(*center)
        cells_radius = int(math.ceil(radius * self.inv_cell_size))
        
        for dx in range(-cells_radius, cells_radius + 1):
            gx = cx + dx
            for dy in range(-cells_radius, cells_radius + 1):
                gy = cy + dy
                for dz in range(-cells_radius, cells_radius + 1):
                    cell = (gx, gy, cz + dz)
                    if cell in self.grid:
                        # Append all entities in this cell
                        results.extend(self.grid[cell])
        
        return results
    
    def clear(self) -> None:
        """Clear all entities from the hash."""
        self.grid.clear()


class SpatialPartition:
    """
    Main spatial partitioning manager for the game.
    Manages entity lifecycle and provides fast spatial queries.
    """
    
    def __init__(self, cell_size: float = 500.0):
        self.spatial_hash = SpatialHash(cell_size)
        self.cell_size = cell_size
        # Track entity positions for removal/moving
        self.entity_positions: dict = {} # id(entity) -> pos
    
    def register_entity(self, entity: object, pos: Tuple[float, float, float]) -> None:
        """Register a new entity."""
        eid = id(entity)
        self.spatial_hash.insert(entity, pos)
        self.entity_positions[eid] = pos
    
    def unregister_entity(self, entity: object) -> None:
        """Remove an entity from the system."""
        eid = id(entity)
        if eid in self.entity_positions:
            pos = self.entity_positions[eid]
            self.spatial_hash.remove(entity, pos)
            del self.entity_positions[eid]

    def update_entity(self, entity: object, new_pos: Tuple[float, float, float]) -> None:
        """
        Update an entity's position incrementally.
        Call this every frame for moving objects.
        """
        eid = id(entity)
        if eid in self.entity_positions:
            old_pos = self.entity_positions[eid]
            self.spatial_hash.move(entity, old_pos, new_pos)
            self.entity_positions[eid] = new_pos
        else:
            self.register_entity(entity, new_pos)
    
    def query_nearby(self, pos: Tuple[float, float, float], radius: float) -> List[object]:
        """Query entities near a position."""
        return self.spatial_hash.query_radius(pos, radius)

    def query_visible(self, camera) -> List[object]:
        """
        Query all entities that might be visible to the camera.
        Uses cell-level frustum culling.
        """
        visible_entities = []
        cell_size = self.cell_size
        half_cell = cell_size * 0.5
        # Sphere radius that encompasses a cell (diagonal / 2)
        cell_radius = math.sqrt(3 * (half_cell**2))
        
        for cell_coords, entities in self.spatial_hash.grid.items():
            # Calculate world center of this cell
            cx = cell_coords[0] * cell_size + half_cell
            cy = cell_coords[1] * cell_size + half_cell
            cz = cell_coords[2] * cell_size + half_cell
            
            # Check if this cell's bounding sphere is in frustum
            if camera.sphere_in_frustum(cx, cy, cz, cell_radius):
                visible_entities.extend(entities)
        
        return visible_entities

    def clear(self) -> None:
        """Clear all entities."""
        self.spatial_hash.clear()
        self.entity_positions.clear()
    
    def get_stats(self) -> dict:
        return {
            'entity_count': len(self.entity_positions),
            'active_cells': len(self.spatial_hash.grid)
        }

