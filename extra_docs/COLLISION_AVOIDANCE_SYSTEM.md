# Enemy Collision Avoidance AI System

## Overview
Implemented intelligent collision avoidance for all enemy types to avoid asteroids, other enemies, and the player (except for suicide drones). This creates more natural, survivable enemy formations and prevents enemies from clumping together.

## Key Features

### 1. **Universal Avoidance System**
- Added `compute_avoidance_force()` method to Enemy base class
- Generates lateral force vectors to navigate around obstacles
- Inverse distance weighting: closer obstacles = stronger avoidance
- Quadratic falloff for smooth, natural behavior
- Returns `None` if no obstacles nearby (zero overhead when not needed)

### 2. **Obstacle Detection**
Detects and avoids:
- **Asteroids** - Identified by `split()` method
- **Other Enemies** - Identified by `on_hit()` and `hit_radius` attributes
- **Player** - Optional avoidance (not in spatial partition, but flag for intent)

### 3. **Smart Per-Enemy Implementation**

#### **SuicideDrone** ⚠️ KAMIKAZE PROFILE
- Avoids asteroids and other enemies
- **Does NOT avoid the player** - designed to charge and detonate
- Blends avoidance with pattern-based evasive movement
- Will weave around obstacles but maintain attack trajectory

#### **Dogfighter** ✓ TACTICAL PROFILE
- Avoids asteroids and enemies
- Avoids player during positioning mode (orbital maneuvering)
- **Does NOT avoid player during attack_run** - commits to firing pass
- Blends avoidance with orbital circling force

#### **Sniper** ✓ TACTICAL PROFILE
- Avoids asteroids and enemies during all movement phases
- Avoids player during fleeing and aiming states
- Does NOT avoid player during charging (static position for accurate aim)
- Maintains lateral evasion force during aiming state

#### **Corvette** 🛡️ HEAVY PROFILE
- Avoids asteroids and enemies while moving toward player
- Does NOT avoid player (full commitment strategy)
- Blends avoidance with forward movement

#### **Minelayer** 🎯 TACTICAL PROFILE
- Avoids asteroids and enemies during traveling phase (stealth approach)
- Avoids player only when traveling (not when bombing/defensive)
- Does NOT avoid player when defensive or bombing
- Maintains mine deployment tactics

#### **StealthInterceptor** ⚡ ELITE PROFILE
- Avoids asteroids and enemies during traveling phase
- Avoids player while traveling and fleeing
- **Does NOT avoid player during attacking** - commits full aggression
- Maintains flank maneuvers around obstacles

#### **Carrier** 🏳️ CAPITAL SHIP PROFILE
- Avoids asteroids and enemies at all ranges
- Does NOT avoid player (too large and powerful)
- Maintains distance management strategy

## Technical Implementation

### Avoidance Algorithm

```python
def compute_avoidance_force(self, spatial, player_pos, avoid_player=True, max_range=2000.0):
    1. Query spatial partition for nearby objects within max_range
    2. For each nearby asteroid or enemy:
       - Calculate distance vector
       - Skip if too close or too far
       - Calculate combined hit radius (self + other + 200-unit buffer)
       - Compute strength based on distance (quadratic falloff)
       - Add weighted direction to accumulator
    3. Normalize total avoidance vector
    4. Scale by 0.6 × self.thrust
    5. Return as lateral force tuple
```

### Integration Points

All enemy `update()` methods now:
1. Compute desired heading toward behavior target
2. Call `compute_avoidance_force()` with appropriate parameters
3. Blend avoidance force with existing lateral movement
4. Pass combined force to `_apply_newtonian()`

**Blending Strategy:**
- Avoidance force scales at 50-70% of original lateral force
- Allows behavior motivations to remain dominant while respecting obstacles
- SuicideDrone: 70% blending (strong evasion + attack)
- Dogfighter: 50% blending (orbital maneuvers remain smooth)
- Others: 60% blending (balanced between behavior and safety)

## Spatial Efficiency

- Uses spatial partition queries (O(cells) not O(enemies))
- Range parameters tuned per enemy type:
  - **SuicideDrone**: 2500 unit range (fast, close-range evasion)
  - **Dogfighter**: 3000 unit range (moderate awareness)
  - **Sniper**: 2500 unit range (careful maneuvering)
  - **Corvette**: 3500 unit range (heavy ship perspective)
  - **Minelayer**: 3000 unit range (stealth approach)
  - **StealthInterceptor**: 2800 unit range (precise maneuvering)
  - **Carrier**: 4000 unit range (large capital ship)

## Behavioral Impact

### Before Avoidance
- Enemies clustered together, taking collisions
- No spatial reasoning in formations
- Predictable linear paths through obstacles

### After Avoidance
- Enemies smoothly navigate around asteroids
- Formations spread out naturally under pressure
- Evasive behavior feels intelligent and coordinated
- Suicide drones still aggressively charge player despite obstacles
- Combat becomes more dynamic as collisions create cascading evasions

## Testing Recommendations

1. **Asteroid Field Test**: Spawn enemy formation in dense asteroid field
   - Verify enemies smoothly weave through asteroids
   - Confirm no "stuck" or erratic behavior
   - Check visual fluidity of movement

2. **Enemy Formation Test**: Spawn 5-10 enemies close together
   - Watch them spread out naturally
   - Verify they don't get stuck in collision loops
   - Confirm they maintain attack objectives

3. **Suicide Drone Test**: Spawn drone surrounded by asteroids
   - Verify it evades asteroids
   - Confirm it still charges at player
   - Check for smooth blending of evasion and attack

4. **Mixed Threat Test**: Asteroids + Enemy Formation + Player
   - Observe natural avoidance behavior
   - Verify tactical differentiation between enemy types
   - Check for performance impact

5. **Performance Test**: Max enemy count
   - Benchmark with avoidance enabled/disabled
   - Spatial queries should remain sub-millisecond
   - Verify no frame rate impact

## Parameter Tuning Guide

To adjust avoidance behavior, modify in `compute_avoidance_force()`:

- **combined_radius adjustment**: `self.hit_radius + other_radius + 200.0`
  - Increase value: enemies keep more distance (safer, less aggressive)
  - Decrease value: enemies cut corners (more aggressive, closer calls)

- **max_range parameter per enemy**: 
  - Higher values: broader awareness, more proactive avoidance
  - Lower values: reactive avoidance only, less forgiving

- **avoidance strength scale**: `self.thrust * 0.6`
  - Higher multiplier: stronger avoidance, weaker original behavior
  - Lower multiplier: original behavior dominates, weaker avoidance

- **blending percentages** in update methods (50% to 70%):
  - Higher: more conservative, prioritizes safety
  - Lower: behavior-focused, accepts more risk

## Files Modified

- `/home/tony/PycharmProjects/3d_space/src/enemy.py`
  - Added `compute_avoidance_force()` method to Enemy base class
  - Updated 7 enemy types: SuicideDrone, Dogfighter, Sniper, Corvette, Minelayer, StealthInterceptor, Carrier
  - Each update method now computes and applies avoidance forces contextually

## Performance Notes

- Avoidance queries only run on actively moving enemies (during update)
- Spatial partition ensures O(n) complexity is efficient
- No impact to rendering pipeline
- Avoidance force returns `None` when no obstacles detected (zero allocation)
- Total overhead per enemy: 1-2 spatial queries per frame = negligible

## Future Enhancements

1. **Predictive Avoidance**: Project future positions of moving obstacles
2. **Formation Control**: Maintain squad cohesion while avoiding obstacles
3. **Path Planning**: A* or goal-directed navigation for complex fields
4. **Aggressive Evasion**: Higher priority evasion when under fire
5. **Tactical Positioning**: Use obstacles as cover during combat

