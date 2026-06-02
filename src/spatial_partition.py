"""
Spatial Partitioning System (Optimized Vectorized Broadphase)
Efficient collision detection and entity culling using dense NumPy arrays and Numba.
"""

import math
from typing import List, Tuple, Optional
import numpy as np
from numba import njit

@njit(cache=True, fastmath=True)
def _query_nearby_numba(target_pos, positions, active, sq_radius):
    """
    Highly optimized brute-force distance query over flat contiguous arrays.
    With Numba and fastmath, this vectorizes beautifully and outpaces Python dict
    spatial-hashes for thousands of entities.
    """
    n = positions.shape[0]
    result = np.empty(n, dtype=np.int32)
    count = 0

    tx = target_pos[0]
    ty = target_pos[1]
    tz = target_pos[2]

    for i in range(n):
        if active[i]:
            dx = positions[i, 0] - tx
            dy = positions[i, 1] - ty
            dz = positions[i, 2] - tz
            if (dx*dx + dy*dy + dz*dz) <= sq_radius:
                result[count] = i
                count += 1

    return result[:count]


class SpatialPartition:
    """
    Main entity manager for spatial queries.
    Replaces the dict-based spatial hash grid with parallel NumPy arrays and Numba filtering.
    """

    def __init__(self, cell_size: float = 15000.0, max_entities: int = 8192):
        # cell_size is kept for API compatibility, though we don't use grid cells anymore
        self.cell_size = cell_size
        self.max_entities = max_entities

        # Pre-allocate contiguous blocks of memory for all entities
        self.positions = np.zeros((max_entities, 3), dtype=np.float64)
        self.active = np.zeros(max_entities, dtype=np.bool_)

        # Mapping between Python object IDs and array indices
        self.entity_positions: dict = {} # Retained for API compatibility
        self.entity_to_idx: dict = {}
        self.idx_to_entity: List[Optional[object]] = [None] * max_entities

        # Free list to provide O(1) slot allocation
        self.free_indices = list(range(max_entities - 1, -1, -1))

    def register_entity(self, entity: object, pos: Tuple[float, float, float]) -> None:
        """Register a new entity."""
        eid = id(entity)
        if eid in self.entity_to_idx:
            return

        if not self.free_indices:
            print("WARNING: SpatialPartition is full! Consider increasing max_entities.")
            return

        idx = self.free_indices.pop()

        self.positions[idx, 0] = pos[0]
        self.positions[idx, 1] = pos[1]
        self.positions[idx, 2] = pos[2]
        self.active[idx] = True

        self.entity_to_idx[eid] = idx
        self.idx_to_entity[idx] = entity
        self.entity_positions[eid] = pos

    def unregister_entity(self, entity: object) -> None:
        """Remove an entity from the system."""
        eid = id(entity)
        if eid in self.entity_to_idx:
            idx = self.entity_to_idx.pop(eid)
            self.active[idx] = False
            self.idx_to_entity[idx] = None
            self.free_indices.append(idx)

            if eid in self.entity_positions:
                del self.entity_positions[eid]

    def update_entity(self, entity: object, new_pos: Tuple[float, float, float]) -> None:
        """
        Update an entity's position. Contiguous memory writes are MUCH faster
        than removing and appending to python lists in dictionary grid cells.
        """
        eid = id(entity)
        if eid in self.entity_to_idx:
            idx = self.entity_to_idx[eid]
            self.positions[idx, 0] = new_pos[0]
            self.positions[idx, 1] = new_pos[1]
            self.positions[idx, 2] = new_pos[2]
            self.entity_positions[eid] = new_pos
        else:
            self.register_entity(entity, new_pos)

    def query_nearby(self, pos: Tuple[float, float, float], radius: float) -> List[object]:
        """Query entities near a position using Numba."""
        target = np.array(pos, dtype=np.float64)
        sq_radius = radius * radius
        indices = _query_nearby_numba(target, self.positions, self.active, sq_radius)
        return [self.idx_to_entity[i] for i in indices]

    def query_visible(self, camera) -> List[object]:
        """
        Query all entities that might be visible to the camera.
        Directly frustum culls the active entity positions precisely.
        """
        active_indices = np.where(self.active)[0]
        if len(active_indices) == 0:
            return []

        centers = self.positions[active_indices]

        # We use a generous bounding radius (e.g., 2500) to prevent large entities popping
        # out of view when their center is just outside the frustum bounds.
        radii = np.full(len(active_indices), 2500.0, dtype=np.float64)

        visible_mask = camera.sphere_in_frustum_batch_call(centers, radii)

        visible_entities = []
        for i, is_vis in enumerate(visible_mask):
            if is_vis:
                visible_entities.append(self.idx_to_entity[active_indices[i]])

        return visible_entities

    def clear(self) -> None:
        """Clear all entities."""
        self.active.fill(False)
        self.entity_to_idx.clear()
        self.entity_positions.clear()
        self.idx_to_entity = [None] * self.max_entities
        self.free_indices = list(range(self.max_entities - 1, -1, -1))

    def get_stats(self) -> dict:
        return {
            'entity_count': len(self.entity_to_idx),
            'active_cells': 1  # Returned as 1 for API compatibility (Unified array)
        }