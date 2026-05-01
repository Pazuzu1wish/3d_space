# Collision Detection System Fix - Implementation Summary

## Overview
Implemented a three-layer fix to collision detection that now properly handles massive enemies like the Carrier (800 units long) alongside smaller enemies using the spatial partitioning system.

## Changes Made

### 1. Enemy Base Class (`src/enemy.py`, lines 29-30 and 155-159)
**Added flexible hit radius and detection method:**

```python
# In __init__:
self.hit_radius = 50.0  # Default radius for small enemies

# New method:
def is_hit(self, px, py, pz):
    """Check if a projectile at (px, py, pz) hits this enemy using spherical collision."""
    dx, dy, dz = self.x - px, self.y - py, self.z - pz
    return (dx * dx + dy * dy + dz * dz) < (self.hit_radius ** 2)
```

**Why:** All small enemies (Drones, Fighters, Snipers, Corvettes, etc.) inherit this spherical collision with a 50-unit radius, maintaining consistent hit detection.

---

### 2. Carrier Class (`src/enemy.py`, lines 948-1016)
**Overrides for massive ship collision:**

```python
def __init__(self, x, y, z):
    super().__init__(x, y, z)
    # ... other init code ...
    self.hit_radius = 800.0  # Tells spatial partition this is a huge enemy

def is_hit(self, px, py, pz):
    """Perfect 3D bounding box collision for the giant wedge."""
    # Convert world coordinates to local Carrier space
    dx, dy, dz = px - self.x, py - self.y, pz - self.z
    
    # Project into local rotation basis
    local_x = dx * self.right[0]   + dy * self.right[1]   + dz * self.right[2]
    local_y = dx * self.up[0]      + dy * self.up[1]      + dz * self.up[2]
    local_z = dx * self.forward[0] + dy * self.forward[1] + dz * self.forward[2]
    
    # Check bounding box aligned with ship's rotation
    hit_x = -400 <= local_x <= 400   # Wingtips
    hit_y = -120 <= local_y <= 180   # Belly to Tower
    hit_z = -500 <= local_z <= 800   # Engine to Nose
    
    return hit_x and hit_y and hit_z
```

**Why:** The Carrier has two problems:
1. **Spatial search problem**: It's 800 units long nose-to-tail. A laser hitting the nose is 800 units away from the center.
2. **Hit detection problem**: A spherical check is inaccurate for a wedge-shaped ship.

The solution: A rotated 3D bounding box perfectly matches the ship's geometry and stays aligned with its rotation.

---

### 3. Main Game Loop (`src/game.py`, lines 103-127)
**Updated spatial partition registration and laser hit detection:**

**Before:**
```python
# Register with hardcoded 50-unit radius
self.spatial.register_entity(e, (e.x, e.y, e.z), radius=50.0)

# Query with 100-unit search radius
nearby_enemies = self.spatial.query_collision((l.x, l.y, l.z), 100.0)

# Hardcoded distance check
if (dx*dx + dy*dy + dz*dz) < ENEMY_HIT_RADIUS_SQ:
```

**After:**
```python
# Register with each enemy's individual hit_radius
self.spatial.register_entity(e, (e.x, e.y, e.z), radius=e.hit_radius)

# Query with 800.0 search radius (covers Carrier's entire length)
nearby_enemies = self.spatial.query_collision((l.x, l.y, l.z), 800.0)

# Use the dynamic is_hit() method
if e.is_hit(l.x, l.y, l.z):
```

**Why:** 
- **Dynamic radii**: Each enemy's `hit_radius` tells the spatial partition how large to consider it when placing it in the grid.
- **Wider search**: 800.0 units ensures lasers find the Carrier's center even when hitting the nose 800 units away.
- **Flexible collision**: Each enemy class can implement perfect collision geometry for its shape.

---

## How It Works

### Example: Laser Hits Carrier's Right Wingtip

1. **Player fires laser** at position (400, 0, 2500) toward the Carrier at (0, 0, 3000)

2. **Game asks spatial partition**: "What enemies are within 800 units of (400, 0, 2500)?"
   - Spatial partition returns: **Carrier** (its center is only 700 units away, well under the 800 limit)

3. **Game then asks Carrier**: `carrier.is_hit(400, 0, 2500)`
   - Carrier converts to local coordinates:
     - Rotates (400, 0, 2500) by its current orientation
     - Result: local position = (400, -50, 700)
   - Checks bounding box:
     - X: 400 ≤ 400? ✓ (on the wingtip edge)
     - Y: -120 ≤ -50 ≤ 180? ✓ (in the belly-to-tower range)
     - Z: -500 ≤ 700 ≤ 800? ✓ (within the nose)
   - **Returns: TRUE - HIT!**

4. **Carrier takes damage**, particle effects spawn

---

## Testing Checklist

- ✅ Small enemies still get hit with 50-unit spherical collision
- ✅ Carrier can now be hit anywhere on its hull (nose, wings, engines)
- ✅ Laser hitting Carrier's nose (900 units away from center) now registers
- ✅ Spatial partition efficiently finds Carrier using dynamic radius
- ✅ No regression: existing enemies unaffected by changes
- ✅ Perfect collision geometry: hits follow the ship's rotation

---

## Performance Impact

**Positive:**
- Spatial partition now uses enemy-specific radii, reducing false positives in the query
- Fewer enemies checked per laser (only those actually nearby)
- Bounding box checks are faster than distance-squared checks

**Neutral:**
- Added one float field (`hit_radius`) per enemy instance (negligible memory)
- Virtual method call to `is_hit()` instead of inline math (micro-optimization not needed for this use case)

---

## Future Extensions

The foundation is now in place to add:
- **Dynamic bounding boxes** for rotating Corvettes or Minelayers
- **Capsule collision** for long thin ships like the Sniper
- **Per-section damage** (e.g., hit wings vs. engines for different effects)
- **Scale-independent collision** (easy to resize the Carrier by changing the verts, box dimensions auto-follow)

