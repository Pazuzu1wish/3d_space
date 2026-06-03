# Spawn Immunity System

## Overview
Newly spawned enemies have a grace period where they are immune to collision damage. This prevents the Carrier and Corvette from disintegrating their spawned units on the frame they appear.

## Problem Solved
**Before:** When Carrier/Corvette spawned Drones and Dogfighters, the new enemies could instantly collide with the parent ship and take damage (often dying immediately).

**After:** New enemies have 0.75 seconds of spawn immunity during which they cannot:
- Take damage from collisions with other enemies
- Take damage from collisions with asteroids

## Implementation Details

### 1. **Spawn Immunity Timer Field**
Added to `Enemy` base class:
```python
self.spawn_immunity_timer = 0.0  # Time remaining in immunity period
```

### 2. **Spawn Point Configuration**

**Corvette** (spawns at offset):
- Position: 40 units below parent (`self.y - 40`)
- Immunity: **0.75 seconds**
- Effect: Drone clears carrier before first collision check

**Carrier** (spawns at offset):
- Drone Position: 150 units down (`-self.up * 150`)
- Dogfighter Position: 150 units to the side (`+self.right * 150`)
- Immunity: **0.75 seconds** for both
- Effect: Both unit types clear the massive capital ship

### 3. **Immunity Update Logic** (`game.py`)
```python
# Decrement timer each frame
if e.spawn_immunity_timer > 0:
    e.spawn_immunity_timer -= dt
```

### 4. **Collision Checks with Immunity**

#### Enemy vs Enemy Collisions
```python
# Skip collision if either enemy is immune
if e1.spawn_immunity_timer > 0 or e2.spawn_immunity_timer > 0:
    continue
```

#### Enemy vs Asteroid Collisions
```python
# Skip collision check for immune enemies
if e.spawn_immunity_timer > 0:
    continue
```

*Note: Projectile collisions are NOT affected by immunity - only direct entity collisions*

## Immunity Grace Period

**Duration:** 0.75 seconds (750ms)

This is long enough to:
- ✓ Clear the spawn point
- ✓ Gain separation from parent ship
- ✓ Execute initial movement patterns
- ✓ Avoid immediate environmental collisions

But short enough to:
- ✓ Maintain collision gameplay after spawn window
- ✓ Not create sustained "invulnerability zones"
- ✓ Feel responsive to player interactions

## Affected Spawning Systems

### Corvette Spawning
- Spawns: SuicideDrone
- Immunity: 0.75 seconds
- Interval: Every 8 seconds
- Max spawned per interval: 1

### Carrier Spawning
- Spawns: 70% SuicideDrone, 30% Dogfighter
- Immunity: 0.75 seconds for both types
- Interval: Every 6 seconds
- Max spawned per interval: 1

## Spawn Sequences

### Corvette Spawn Flow (t=8s after spawn timer reset)
```
t=0:     Spawn timer starts (8.0s)
t=8:     New drone spawned at (x, y-40, z) with 0.75s immunity
t=8-8.75: Drone clears parent while immune
t=8.75:  Immunity expires, normal collision rules apply
t=16:    Next spawn (8s interval)
```

### Carrier Spawn Flow (t=6s after spawn timer reset)
```
t=0:     Spawn timer starts (6.0s)
t=6:     New unit spawned (70% drone/30% fighter) with 0.75s immunity
t=6-6.75: Unit clears parent while immune
t=6.75:  Immunity expires, normal collision rules apply
t=12:    Next spawn (6s interval)
```

## Visual Feedback

During spawn immunity:
- No collision particles generated
- Enemy moves freely without constraint
- Parent ship remains unaffected
- Smooth spawn animation (no stuttering)

After immunity expires:
- Normal collision detection active
- Full damage/physics applies
- Environmental awareness required

## Technical Notes

### Performance
- Immunity timer decrement: O(n) through enemies list per frame
- Collision skip check: One comparison per collision pair
- Zero overhead for non-spawned enemies
- No impact to rendering or AI systems

### Consistency
- All newly spawned enemies get same immunity duration
- Prevents "random survivors" syndrome
- Predictable & fair spawn mechanics

### Edge Cases Handled
- ✓ Multiple enemies spawning in same frame (each gets own immunity)
- ✓ Immunity expiring during same-frame collision check (respects current timer value)
- ✓ Parent ship movement (immunity is position-independent)
- ✓ Rapid successive spawns (each spawn gets fresh timer)

## Tuning Parameters

To adjust immunity duration, modify in `src/enemy.py`:

**Corvette spawn:**
```python
drone.spawn_immunity_timer = 0.75  # Change to longer/shorter
```

**Carrier spawn:**
```python
new_e.spawn_immunity_timer = 0.75  # Change to longer/shorter
```

### Recommendation
- **0.5 seconds**: Very quick, challenging for spawned units
- **0.75 seconds**: Current balanced setting
- **1.0 seconds**: Generous grace period, safer for spawned units
- **1.5 seconds**: Very lenient, almost unlimited spawn protection

## Future Enhancements

1. **Per-Enemy-Type Immunity**: Different durations for Drones vs Dogfighters
2. **Smart Immunity**: Scale based on parent ship size
3. **Staggered Spawning**: Spawn multiple units with time offset
4. **Spawn Velocity**: Inherit parent velocity for smoother separation
5. **Visual Indicator**: Glow/shimmer effect showing immunity active

## Files Modified

- `src/enemy.py`
  - Added `spawn_immunity_timer` field to Enemy base class
  - Updated Corvette spawn code to set immunity timer
  - Updated Carrier spawn code to set immunity timer

- `src/game.py`
  - Added immunity timer decrement in enemy update loop
  - Updated enemy-to-enemy collision check to respect immunity
  - Updated enemy-to-asteroid collision check to respect immunity

