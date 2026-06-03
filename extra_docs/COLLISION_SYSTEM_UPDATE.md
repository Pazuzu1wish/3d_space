# Collision System Update - Enemy & Projectile Interactions

## Summary
Added collision detection between enemies and between enemies and their projectiles (friendly fire). This creates more dynamic combat where enemies can damage each other through collision or projectile fire.

## Changes Made

### 1. **src/projectile.py**

#### Added `owner` field to EnemyProjectile
- Added optional `owner` parameter to `__init__` to track which enemy fired each projectile
- Defaults to `None` for backward compatibility

```python
def __init__(self, x, y, z, vx, vy, vz, life, damage, color, size_mult, homing=False, owner=None):
    # ... existing code ...
    self.owner = owner  # Reference to the enemy that fired this projectile
```

#### Added `check_enemy_collision()` method
- Checks if projectile collides with other enemies (excluding the owner)
- Uses spatial query to find nearby objects within 500 units
- Applies spherical collision detection using hit_radius
- Automatically converts projectile damage to integer for on_hit()
- Prevents friendly fire (projectiles don't hit their owner)
- Excludes asteroids from this check (they have 'split' method)

```python
def check_enemy_collision(self, spatial, particles):
    """Check if this projectile hits an enemy (excluding the owner). Returns True if collision occurred."""
    nearby = spatial.query_nearby((self.x, self.y, self.z), 500.0)
    
    for obj in nearby:
        # Skip if this is the owner of the projectile (no friendly fire on self)
        if obj is self.owner:
            continue
        # Check if it's an enemy (has hit_radius and on_hit methods)
        if hasattr(obj, 'hit_radius') and hasattr(obj, 'on_hit'):
            # Don't collide with asteroids (they have 'split' method)
            if hasattr(obj, 'split'):
                continue
            # Use spherical collision check
            dx = self.x - obj.x
            dy = self.y - obj.y
            dz = self.z - obj.z
            dist_sq = dx * dx + dy * dy + dz * dz
            if dist_sq < (obj.hit_radius ** 2):
                obj.on_hit(int(self.damage))
                self.life = 0
                for _ in range(PARTICLES_ON_HIT):
                    particles.spawn(self.x, self.y, self.z)
                return True
    return False
```

### 2. **src/enemy.py**

Updated all enemy classes that fire projectiles to set the `owner` field:

- **Dogfighter._fire_projectile()** - Sets owner for MachineGunBolt and HomingBolt
- **Corvette.update()** - Sets owner for CorvetteTurret
- **Minelayer.update()** - Sets owner for Mine and MachineGunBolt
- **StealthInterceptor.update()** - Sets owner for StealthShotgun
- **Carrier.update()** - Sets owner for SniperBeam, HomingBolt, and MachineGunBolt

#### Example implementation pattern:
```python
# Before
global_projectiles.append(MachineGunBolt(self.x, self.y, self.z, vx, vy, vz))

# After
bolt = MachineGunBolt(self.x, self.y, self.z, vx, vy, vz)
bolt.owner = self
global_projectiles.append(bolt)
```

### 3. **src/game.py**

Updated `update_entities()` method in `GameplayState` class:

#### Added Enemy-to-Enemy collision detection
- Iterates through all enemies and checks for collisions with nearby enemies
- Uses spatial queries for efficiency
- Applies 1 damage to both colliding enemies
- Generates particles at collision point
- Prevents self-collision through identity check

```python
# Enemy vs Enemy collisions
for i, e1 in enumerate(enemies):
    nearby = self.spatial.query_nearby((e1.x, e1.y, e1.z), e1.hit_radius + 500.0)
    for e2 in nearby:
        # Skip if it's the same enemy or not an enemy
        if e2 is e1 or not isinstance(e2, type(e1).__bases__[0] if e1.__class__.__bases__ else object):
            continue
        # Check if it has hit_radius and on_hit (enemy attributes)
        if not hasattr(e2, 'hit_radius') or not hasattr(e2, 'on_hit'):
            continue
        # Skip asteroids (they have 'split' method)
        if hasattr(e2, 'split'):
            continue
        # Check if it's actually in the enemies list
        if e2 not in enemies:
            continue
        
        dist_sq = (e1.x - e2.x) ** 2 + (e1.y - e2.y) ** 2 + (e1.z - e2.z) ** 2
        if dist_sq < (e1.hit_radius + e2.hit_radius) ** 2:
            e1.on_hit(1)
            e2.on_hit(1)
            for _ in range(PARTICLES_ON_HIT):
                self.particle_pool.spawn(e1.x, e1.y, e1.z)
            break
```

#### Added Enemy Projectile-to-Enemy collision check
- Inserted before player and asteroid collision checks in the projectile update loop
- Allows projectiles to hit other enemies (friendly fire)
- Prevents projectiles from hitting their owner
- Removes projectile on collision

```python
# In projectile update loop
if bolt.check_enemy_collision(self.spatial, self.particle_pool):
    if bolt in enemy_projectiles:
        enemy_projectiles.remove(bolt)
    continue
```

## Collision Order

Projectiles now check collisions in this order:
1. **Asteroids** - check_asteroid_collision()
2. **Enemies** - check_enemy_collision() (NEW)
3. **Player** - check_player_collision()
4. **Lifetime expiry** - life <= 0

The first collision found removes the projectile from the game.

## Gameplay Effects

### Enemy-to-Enemy:
- Enemies which spawn close together can collide and take damage
- Creates tactical spacing requirements for incoming enemy waves
- Larger enemies (Carrier, Corvette) have larger hit_radius, making them more likely to collide

### Projectile-to-Enemy:
- Machine gun bolts fire from Dogfighters and Minelayers can hit other nearby enemies
- Homing bolts from Dogfighters and Carrier can hit other enemies
- Corvette turret projectiles can hit other enemies
- Mines from Minelayers can be hit by enemy projectiles
- StealthInterceptor shotguns can hit other enemies
- Carrier sniper beams, bolts, and MG fire can hit other enemies

### Strategic Implications:
- Enemies with overlapping fire cones will damage each other
- Dogfighters in formation may interfere with each other
- Minelayer mines create hazards for other enemies
- Player can position self to let enemies damage each other

## Technical Notes

- All collision checks use spherical collision detection (distance <= hit_radius)
- Spatial partitioning system ensures O(1) performance for nearby object queries
- Owner-check prevents projectiles from immediately colliding with the firing enemy
- Enemy type checking filters out non-enemy objects (asteroids, player)
- Damage is cast to int before passing to on_hit() to maintain compatibility
- Particle effects spawn at collision points for visual feedback

## Testing Recommendations

1. **Enemy Formation Collisions**: Spawn multiple enemies close together and watch them collide
2. **Friendly Fire**: Watch Dogfighters shoot and have projectiles hit nearby enemies
3. **Minelayer Hazards**: Observe mines being destroyed by enemy fire
4. **Visual Effects**: Confirm particle effects appear at collision points
5. **Survival Impact**: Test if grouping enemies together causes them to eliminate each other faster

## Files Modified

1. `/home/tony/PycharmProjects/3d_space/src/projectile.py` - Added owner field and check_enemy_collision()
2. `/home/tony/PycharmProjects/3d_space/src/enemy.py` - All projectile firing methods updated
3. `/home/tony/PycharmProjects/3d_space/src/game.py` - Added enemy collision detection logic

