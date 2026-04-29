"""
Spatial Partitioning System
Efficient collision detection and entity culling using octree spatial partitioning.
"""

import math
from typing import List, Optional, Tuple, Callable
from dataclasses import dataclass


@dataclass
class BoundingBox:
    """Axis-aligned bounding box for spatial queries."""
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float
    
    def contains_point(self, x: float, y: float, z: float) -> bool:
        """Check if a point is inside this bounding box."""
        return (self.min_x <= x <= self.max_x and
                self.min_y <= y <= self.max_y and
                self.min_z <= z <= self.max_z)
    
    def intersects_box(self, other: 'BoundingBox') -> bool:
        """Check if this box intersects another box."""
        return not (self.max_x < other.min_x or self.min_x > other.max_x or
                    self.max_y < other.min_y or self.min_y > other.max_y or
                    self.max_z < other.min_z or self.min_z > other.max_z)
    
    def get_center(self) -> Tuple[float, float, float]:
        """Get the center point of the box."""
        return ((self.min_x + self.max_x) / 2,
                (self.min_y + self.max_y) / 2,
                (self.min_z + self.max_z) / 2)
    
    def get_size(self) -> Tuple[float, float, float]:
        """Get the dimensions of the box."""
        return (self.max_x - self.min_x,
                self.max_y - self.min_y,
                self.max_z - self.min_z)
    
    def subdivide(self) -> List['BoundingBox']:
        """Subdivide this box into 8 octants."""
        cx, cy, cz = self.get_center()
        
        return [
            # Bottom layer (z-)
            BoundingBox(self.min_x, self.min_y, self.min_z, cx, cy, cz),
            BoundingBox(cx, self.min_y, self.min_z, self.max_x, cy, cz),
            BoundingBox(self.min_x, cy, self.min_z, cx, self.max_y, cz),
            BoundingBox(cx, cy, self.min_z, self.max_x, self.max_y, cz),
            # Top layer (z+)
            BoundingBox(self.min_x, self.min_y, cz, cx, cy, self.max_z),
            BoundingBox(cx, self.min_y, cz, self.max_x, cy, self.max_z),
            BoundingBox(self.min_x, cy, cz, cx, self.max_y, self.max_z),
            BoundingBox(cx, cy, cz, self.max_x, self.max_y, self.max_z),
        ]


class OctreeNode:
    """Node in the octree spatial partition."""
    
    def __init__(self, bounds: BoundingBox, depth: int = 0, max_depth: int = 6):
        self.bounds = bounds
        self.depth = depth
        self.max_depth = max_depth
        self.entities: List[object] = []
        self.children: Optional[List['OctreeNode']] = None
        self.is_divided = False
    
    def insert(self, entity: object, pos: Tuple[float, float, float], 
               radius: float = 0.0) -> bool:
        """
        Insert an entity into the octree.
        
        Args:
            entity: The entity to insert
            pos: Position tuple (x, y, z)
            radius: Collision radius of the entity
        
        Returns:
            True if insertion was successful
        """
        x, y, z = pos
        
        # Check if position is within this node's bounds
        if not self.bounds.contains_point(x, y, z):
            return False
        
        # If we have children, try to insert into them
        if self.is_divided:
            for child in self.children:
                if child.insert(entity, pos, radius):
                    return True
            # If none of the children accepted it, store here
            self.entities.append(entity)
            return True
        
        # If at max depth, store entity here
        if self.depth >= self.max_depth:
            self.entities.append(entity)
            return True
        
        # Check if entity fits entirely within this node
        # (considering its radius)
        margin = radius
        if (x - margin < self.bounds.min_x or x + margin > self.bounds.max_x or
            y - margin < self.bounds.min_y or y + margin > self.bounds.max_y or
            z - margin < self.bounds.min_z or z + margin > self.bounds.max_z):
            self.entities.append(entity)
            return True
        
        # Subdivide and insert
        self._subdivide()
        for child in self.children:
            if child.insert(entity, pos, radius):
                return True
        
        # Fallback: store in this node
        self.entities.append(entity)
        return True
    
    def _subdivide(self) -> None:
        """Divide this node into 8 children."""
        if self.is_divided:
            return
        
        self.children = []
        for bounds in self.bounds.subdivide():
            self.children.append(OctreeNode(bounds, self.depth + 1, self.max_depth))
        self.is_divided = True
    
    def query_radius(self, center: Tuple[float, float, float], 
                     radius: float) -> List[object]:
        """
        Query all entities within a sphere.
        
        Args:
            center: Center point (x, y, z)
            radius: Search radius
        
        Returns:
            List of entities within the sphere
        """
        results = []
        self._query_radius_recursive(center, radius, results, set())
        return results
    
    def _query_radius_recursive(self, center: Tuple[float, float, float],
                                 radius: float, results: List[object],
                                 seen: set) -> None:
        """Recursive helper for radius query."""
        x, y, z = center
        radius_sq = radius * radius
        
        # Check if search sphere intersects this node's bounds
        if not self._sphere_intersects_bounds(center, radius):
            return
        
        # Add entities from this node
        for entity in self.entities:
            entity_id = id(entity)
            if entity_id not in seen:
                seen.add(entity_id)
                results.append(entity)
        
        # Recurse into children
        if self.is_divided:
            for child in self.children:
                child._query_radius_recursive(center, radius, results, seen)
    
    def _sphere_intersects_bounds(self, center: Tuple[float, float, float],
                                   radius: float) -> bool:
        """Check if a sphere intersects this node's bounds."""
        x, y, z = center
        
        # Find closest point on box to sphere center
        closest_x = max(self.bounds.min_x, min(x, self.bounds.max_x))
        closest_y = max(self.bounds.min_y, min(y, self.bounds.max_y))
        closest_z = max(self.bounds.min_z, min(z, self.bounds.max_z))
        
        # Calculate distance from closest point to sphere center
        dx = x - closest_x
        dy = y - closest_y
        dz = z - closest_z
        
        return (dx*dx + dy*dy + dz*dz) <= (radius * radius)
    
    def query_box(self, box: BoundingBox) -> List[object]:
        """Query all entities within a bounding box."""
        results = []
        self._query_box_recursive(box, results, set())
        return results
    
    def _query_box_recursive(self, box: BoundingBox, results: List[object],
                             seen: set) -> None:
        """Recursive helper for box query."""
        if not self.bounds.intersects_box(box):
            return
        
        for entity in self.entities:
            entity_id = id(entity)
            if entity_id not in seen:
                seen.add(entity_id)
                results.append(entity)
        
        if self.is_divided:
            for child in self.children:
                child._query_box_recursive(box, results, seen)
    
    def remove(self, entity: object) -> bool:
        """Remove an entity from the octree."""
        if entity in self.entities:
            self.entities.remove(entity)
            return True
        
        if self.is_divided:
            for child in self.children:
                if child.remove(entity):
                    return True
        
        return False
    
    def clear(self) -> None:
        """Clear all entities from this node and children."""
        self.entities.clear()
        if self.is_divided:
            for child in self.children:
                child.clear()
    
    def get_entity_count(self) -> int:
        """Get total number of entities in this node and children."""
        count = len(self.entities)
        if self.is_divided:
            for child in self.children:
                count += child.get_entity_count()
        return count


class SpatialHash:
    """
    Alternative spatial partitioning using a hash grid.
    Better for uniformly distributed entities.
    """
    
    def __init__(self, cell_size: float = 100.0):
        """
        Initialize spatial hash.
        
        Args:
            cell_size: Size of each grid cell
        """
        self.cell_size = cell_size
        self.grid: dict = {}
    
    def _hash_position(self, x: float, y: float, z: float) -> Tuple[int, int, int]:
        """Convert world position to grid cell coordinates."""
        return (
            int(math.floor(x / self.cell_size)),
            int(math.floor(y / self.cell_size)),
            int(math.floor(z / self.cell_size))
        )
    
    def insert(self, entity: object, pos: Tuple[float, float, float]) -> None:
        """Insert an entity into the spatial hash."""
        cell = self._hash_position(*pos)
        if cell not in self.grid:
            self.grid[cell] = []
        self.grid[cell].append(entity)
    
    def remove(self, entity: object, pos: Tuple[float, float, float]) -> None:
        """Remove an entity from the spatial hash."""
        cell = self._hash_position(*pos)
        if cell in self.grid and entity in self.grid[cell]:
            self.grid[cell].remove(entity)
    
    def query_radius(self, center: Tuple[float, float, float],
                     radius: float) -> List[object]:
        """Query all entities within a sphere."""
        results = []
        seen = set()
        
        # Calculate range of cells to check
        cx, cy, cz = self._hash_position(*center)
        cells_radius = int(math.ceil(radius / self.cell_size))
        
        for dx in range(-cells_radius, cells_radius + 1):
            for dy in range(-cells_radius, cells_radius + 1):
                for dz in range(-cells_radius, cells_radius + 1):
                    cell = (cx + dx, cy + dy, cz + dz)
                    if cell in self.grid:
                        for entity in self.grid[cell]:
                            entity_id = id(entity)
                            if entity_id not in seen:
                                seen.add(entity_id)
                                results.append(entity)
        
        return results
    
    def clear(self) -> None:
        """Clear all entities from the hash."""
        self.grid.clear()
    
    def get_entity_count(self) -> int:
        """Get total number of entities in the hash."""
        return sum(len(entities) for entities in self.grid.values())


class SpatialPartition:
    """
    Main spatial partitioning manager for the game.
    Automatically chooses between octree and spatial hash based on needs.
    """
    
    def __init__(self, world_size: float = 20000.0, cell_size: float = 500.0):
        """
        Initialize spatial partitioning system.
        
        Args:
            world_size: Size of the game world (for octree bounds)
            cell_size: Cell size for spatial hash queries
        """
        half_size = world_size / 2
        self.bounds = BoundingBox(
            -half_size, -half_size, -half_size,
            half_size, half_size, half_size
        )
        self.octree = OctreeNode(self.bounds, max_depth=6)
        self.spatial_hash = SpatialHash(cell_size)
        
        # Track entity positions for removal
        self.entity_positions: dict = {}
    
    def register_entity(self, entity: object, pos: Tuple[float, float, float],
                        radius: float = 0.0) -> None:
        """Register an entity in the spatial partition."""
        self.octree.insert(entity, pos, radius)
        self.spatial_hash.insert(entity, pos)
        self.entity_positions[id(entity)] = pos
    
    def unregister_entity(self, entity: object) -> None:
        """Remove an entity from the spatial partition."""
        entity_id = id(entity)
        if entity_id in self.entity_positions:
            pos = self.entity_positions[entity_id]
            self.spatial_hash.remove(entity, pos)
            del self.entity_positions[entity_id]
        self.octree.remove(entity)
    
    def update_entity(self, entity: object, old_pos: Tuple[float, float, float],
                      new_pos: Tuple[float, float, float]) -> None:
        """Update an entity's position in the spatial partition."""
        self.unregister_entity(entity)
        self.register_entity(entity, new_pos)
    
    def query_nearby(self, pos: Tuple[float, float, float],
                     radius: float) -> List[object]:
        """Query entities near a position using spatial hash (faster)."""
        return self.spatial_hash.query_radius(pos, radius)
    
    def query_collision(self, pos: Tuple[float, float, float],
                        radius: float) -> List[object]:
        """Query entities for collision detection using octree (more accurate)."""
        return self.octree.query_radius(pos, radius)
    
    def clear(self) -> None:
        """Clear all entities from the spatial partition."""
        self.octree.clear()
        self.spatial_hash.clear()
        self.entity_positions.clear()
    
    def get_entity_count(self) -> int:
        """Get total number of registered entities."""
        return len(self.entity_positions)
    
    def get_stats(self) -> dict:
        """Get statistics about the spatial partition."""
        return {
            'entity_count': len(self.entity_positions),
            'octree_count': self.octree.get_entity_count(),
            'hash_cells': len(self.spatial_hash.grid),
            'hash_count': self.spatial_hash.get_entity_count()
        }
