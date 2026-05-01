"""
Unit tests for object pooling and spatial partitioning systems.
Run with: python -m pytest src/test_optimizations.py -v
"""

import sys
import os


# Add parent directory to path so src module can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.object_pool import ObjectPool, ParticlePool, LaserPool
from src.spatial_partition import BoundingBox, OctreeNode, SpatialHash, SpatialPartition


class TestObjectPool:
    """Tests for generic object pool."""
    
    def test_initialization(self):
        """Test pool creates initial objects."""
        pool = ObjectPool(lambda: {'value': 0}, initial_size=10)
        assert pool.get_available_count() == 10
        assert pool.get_active_count() == 0
        assert pool.get_total_count() == 10
    
    def test_acquire_release(self):
        """Test acquiring and releasing objects."""
        pool = ObjectPool(lambda: {'value': 0}, initial_size=5)
        
        obj = pool.acquire()
        assert obj is not None
        assert pool.get_active_count() == 1
        assert pool.get_available_count() == 4
        
        pool.release(obj)
        assert pool.get_active_count() == 0
        assert pool.get_available_count() == 5
    
    def test_max_size(self):
        """Test pool respects max size limit."""
        pool = ObjectPool(lambda: {'value': 0}, initial_size=3, max_size=3)
        
        obj1 = pool.acquire()
        obj2 = pool.acquire()
        obj3 = pool.acquire()
        obj4 = pool.acquire()  # Should return None
        
        assert obj1 is not None
        assert obj2 is not None
        assert obj3 is not None
        assert obj4 is None
        assert pool.get_active_count() == 3
    
    def test_reset_function(self):
        """Test custom reset function is called."""
        reset_called = []
        
        def reset_func(obj):
            obj['value'] = 0
            reset_called.append(True)
        
        pool = ObjectPool(lambda: {'value': 1}, reset_func=reset_func, initial_size=1)
        obj = pool.acquire()
        obj['value'] = 99
        pool.release(obj)
        
        assert len(reset_called) == 1
        assert obj['value'] == 0


class TestParticlePool:
    """Tests for particle pool."""
    
    def test_spawn_particle(self):
        """Test spawning particles."""
        pool = ParticlePool(None, initial_size=10, max_size=50)
        
        particle = pool.spawn(100, 200, 300)
        assert particle is not None
        assert particle['x'] == 100
        assert particle['y'] == 200
        assert particle['z'] == 300
        assert particle['active'] == True
        assert pool.get_active_count() == 1
    
    def test_update_recycles_dead(self):
        """Test that dead particles are recycled."""
        pool = ParticlePool(None, initial_size=5, max_size=5)
        
        pool.spawn(0, 0, 0, life=0.01)
        assert pool.get_active_count() == 1
        
        pool.update(0.02)  # Update past particle lifetime
        assert pool.get_active_count() == 0
    
    def test_clear(self):
        """Test clearing all particles."""
        pool = ParticlePool(None, initial_size=10, max_size=50)
        
        for i in range(5):
            pool.spawn(i, i, i)
        
        assert pool.get_active_count() == 5
        pool.clear()
        assert pool.get_active_count() == 0


class TestBoundingBox:
    """Tests for bounding box utilities."""
    
    def test_contains_point(self):
        """Test point containment."""
        box = BoundingBox(-10, -10, -10, 10, 10, 10)
        
        assert box.contains_point(0, 0, 0) == True
        assert box.contains_point(10, 10, 10) == True
        assert box.contains_point(-10, -10, -10) == True
        assert box.contains_point(11, 0, 0) == False
        assert box.contains_point(-11, 0, 0) == False
    
    def test_intersects_box(self):
        """Test box intersection."""
        box1 = BoundingBox(-10, -10, -10, 10, 10, 10)
        box2 = BoundingBox(5, 5, 5, 15, 15, 15)
        box3 = BoundingBox(20, 20, 20, 30, 30, 30)
        
        assert box1.intersects_box(box2) == True
        assert box1.intersects_box(box3) == False
        assert box2.intersects_box(box1) == True
    
    def test_subdivide(self):
        """Test box subdivision into octants."""
        box = BoundingBox(-10, -10, -10, 10, 10, 10)
        children = box.subdivide()
        
        assert len(children) == 8
        # Check first child (bottom-left-back octant)
        assert children[0].min_x == -10
        assert children[0].max_x == 0
        assert children[0].min_y == -10
        assert children[0].max_y == 0
        assert children[0].min_z == -10
        assert children[0].max_z == 0


class TestOctreeNode:
    """Tests for octree spatial partition."""
    
    def test_insert_and_query(self):
        """Test inserting and querying entities."""
        bounds = BoundingBox(-100, -100, -100, 100, 100, 100)
        tree = OctreeNode(bounds, max_depth=4)
        
        entity1 = {'id': 1}
        entity2 = {'id': 2}
        entity3 = {'id': 3}
        
        tree.insert(entity1, (10, 10, 10))
        tree.insert(entity2, (20, 20, 20))
        tree.insert(entity3, (-50, -50, -50))
        
        results = tree.query_radius((0, 0, 0), radius=30)
        assert len(results) == 2
        assert entity1 in results
        assert entity2 in results
        assert entity3 not in results
    
    def test_remove(self):
        """Test removing entities."""
        bounds = BoundingBox(-100, -100, -100, 100, 100, 100)
        tree = OctreeNode(bounds, max_depth=4)
        
        entity = {'id': 1}
        tree.insert(entity, (10, 10, 10))
        
        assert tree.remove(entity) == True
        assert tree.remove(entity) == False  # Already removed
        
        results = tree.query_radius((0, 0, 0), radius=100)
        assert len(results) == 0
    
    def test_clear(self):
        """Test clearing all entities."""
        bounds = BoundingBox(-100, -100, -100, 100, 100, 100)
        tree = OctreeNode(bounds, max_depth=4)
        
        for i in range(10):
            tree.insert({'id': i}, (i*5, i*5, i*5))
        
        assert tree.get_entity_count() == 10
        tree.clear()
        assert tree.get_entity_count() == 0


class TestSpatialHash:
    """Tests for spatial hash grid."""
    
    def test_insert_and_query(self):
        """Test inserting and querying with spatial hash."""
        sh = SpatialHash(cell_size=10.0)
        
        entity1 = {'id': 1}
        entity2 = {'id': 2}
        entity3 = {'id': 3}
        
        sh.insert(entity1, (5, 5, 5))
        sh.insert(entity2, (15, 15, 15))
        sh.insert(entity3, (50, 50, 50))
        
        results = sh.query_radius((10, 10, 10), radius=15)
        assert len(results) == 2
        assert entity1 in results
        assert entity2 in results
        assert entity3 not in results
    
    def test_clear(self):
        """Test clearing spatial hash."""
        sh = SpatialHash(cell_size=10.0)
        
        for i in range(10):
            sh.insert({'id': i}, (i*5, i*5, i*5))
        
        assert sh.get_entity_count() == 10
        sh.clear()
        assert sh.get_entity_count() == 0


class TestSpatialPartition:
    """Tests for combined spatial partition system."""
    
    def test_register_unregister(self):
        """Test registering and unregistering entities."""
        sp = SpatialPartition(world_size=1000.0, cell_size=50.0)
        
        entity = {'id': 1}
        sp.register_entity(entity, (10, 20, 30), radius=5.0)
        
        assert sp.get_entity_count() == 1
        
        sp.unregister_entity(entity)
        assert sp.get_entity_count() == 0
    
    def test_query_nearby(self):
        """Test nearby queries."""
        sp = SpatialPartition(world_size=1000.0, cell_size=50.0)
        
        for i in range(5):
            sp.register_entity({'id': i}, (i*10, 0, 0), radius=2.0)
        
        results = sp.query_nearby((20, 0, 0), radius=25)
        assert len(results) >= 2  # At least nearby entities
    
    def test_stats(self):
        """Test statistics reporting."""
        sp = SpatialPartition(world_size=1000.0, cell_size=50.0)
        
        for i in range(3):
            sp.register_entity({'id': i}, (i*10, 0, 0))
        
        stats = sp.get_stats()
        assert stats['entity_count'] == 3
        assert 'hash_cells' in stats
        assert 'hash_count' in stats


class TestLaserCompatibility:
    """Test laser class compatibility with pooling."""
    
    def test_laser_init_with_params(self):
        """Test laser can be initialized with explicit parameters."""
        from src.laser import Laser
        
        laser = Laser(x=100, y=200, z=300, vx=1000, vy=0, vz=0, life=2.0)
        assert laser.x == 100
        assert laser.y == 200
        assert laser.z == 300
        assert laser.vx == 1000
        assert laser.life == 2.0
    
    def test_laser_reinit(self):
        """Test laser can be reinitialized for pooling."""
        from src.laser import Laser
        
        laser = Laser(x=0, y=0, z=0, vx=0, vy=0, vz=0)
        laser.init(500, 600, 700, 2000, 0, 0, life=3.0)
        
        assert laser.x == 500
        assert laser.y == 600
        assert laser.z == 700
        assert laser.vx == 2000
        assert laser.life == 3.0
    
    def test_laser_reset(self):
        """Test laser reset for pooling."""
        from src.laser import Laser
        
        laser = Laser(x=100, y=200, z=300, vx=1000, vy=0, vz=0)
        laser.reset()
        
        assert laser.x == 0
        assert laser.y == 0
        assert laser.z == 0
        assert laser.vx == 0
        assert laser.vy == 0
        assert laser.vz == 0
        assert laser.life == 0


def run_tests():
    """Run all tests manually (for environments without pytest)."""
    import traceback
    
    test_classes = [
        TestObjectPool,
        TestParticlePool,
        TestBoundingBox,
        TestOctreeNode,
        TestSpatialHash,
        TestSpatialPartition,
        TestLaserCompatibility,
    ]
    
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                try:
                    method = getattr(instance, method_name)
                    method()
                    print(f"✓ {test_class.__name__}.{method_name}")
                    passed += 1
                except Exception as e:
                    print(f"✗ {test_class.__name__}.{method_name}")
                    traceback.print_exc()
                    failed += 1
    
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
