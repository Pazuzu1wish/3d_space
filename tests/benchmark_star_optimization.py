#!/usr/bin/env python
"""
Benchmark script to verify star batch processing optimization.
Compares individual star submission vs. batch submission.
"""

# Note: This is a synthetic benchmark focused on the star processing steps.
import time
import numpy as np
from src.star import Star, wrap_star_positions_batch, compute_star_colors_batch
from src.camera import Camera
from src.renderer import RenderPipeline

def benchmark_batch_processing():
    """Test the optimized batch star processing."""
    print("\n" + "="*70)
    print("STAR BATCH PROCESSING BENCHMARK")
    print("="*70)
    
    # Setup
    camera = Camera(1920, 1080)
    renderer = RenderPipeline(camera)
    player_pos = (0.0, 0.0, 0.0)
    camera.update(player_pos, (1, 0, 0, 0))
    
    # Create 220 stars
    stars = [Star(player_pos) for _ in range(220)]
    print(f"\n✓ Created {len(stars)} stars")
    
    # Warmup Numba JIT compilation
    print("\nWarmup (compiling Numba functions)...")
    positions = np.array([(s.x, s.y, s.z) for s in stars], dtype=np.float64)
    brightness = np.array([s.brightness for s in stars], dtype=np.float64)
    base_colors = np.array([s.base_color for s in stars], dtype=np.float64)
    _ = wrap_star_positions_batch(positions, player_pos, 3000)
    _ = camera.world_to_camera_batch(positions)
    _ = compute_star_colors_batch(positions, brightness, base_colors)
    print("✓ Numba functions compiled\n")
    
    # Test 1: Individual batch function calls (old way - conceptual)
    print("--- Test 1: Individual Position Wrapping ---")
    start = time.perf_counter()
    for _ in range(100):
        for star in stars:
            # Simulate individual wrapping
            dx = star.x - player_pos[0]
            dy = star.y - player_pos[1]
            dz = star.z - player_pos[2]
            spread = 3000
            if dx > spread: star.x -= 2 * spread
            elif dx < -spread: star.x += 2 * spread
    elapsed_individual = time.perf_counter() - start
    print(f"  100 iterations of individual wrapping: {elapsed_individual:.4f}s")
    
    # Reset stars
    stars = [Star(player_pos) for _ in range(220)]
    
    # Test 2: Batch Numba processing (new way)
    print("\n--- Test 2: Batch Numba Processing ---")
    start = time.perf_counter()
    for _ in range(100):
        positions = np.array([(s.x, s.y, s.z) for s in stars], dtype=np.float64)
        wrapped_pos = wrap_star_positions_batch(positions, player_pos, 3000)
        for i, star in enumerate(stars):
            star.x, star.y, star.z = wrapped_pos[i]
    elapsed_batch = time.perf_counter() - start
    print(f"  100 iterations of batch wrapping:     {elapsed_batch:.4f}s")
    
    speedup = elapsed_individual / elapsed_batch
    print(f"\n✓ Speedup: {speedup:.1f}x faster with batch processing")
    print(f"  Savings: {(elapsed_individual - elapsed_batch):.4f}s per 100 frames")
    
    # Test 3: Full batch rendering pipeline
    print("\n--- Test 3: Full Batch Rendering Pipeline ---")
    
    positions = np.array([(s.x, s.y, s.z) for s in stars], dtype=np.float64)
    brightness = np.array([s.brightness for s in stars], dtype=np.float64)
    base_colors = np.array([s.base_color for s in stars], dtype=np.float64)
    
    start = time.perf_counter()
    for _ in range(100):
        # Step 1: Wrap positions
        wrapped_pos = wrap_star_positions_batch(positions, player_pos, 3000)
        
        # Step 2: Transform to camera space
        cam_verts = camera.world_to_camera_batch(wrapped_pos)
        
        # Step 3: Compute colors
        colors, valid_mask = compute_star_colors_batch(cam_verts, brightness, base_colors)
    
    elapsed_full = time.perf_counter() - start
    print(f"  100 iterations of full pipeline:     {elapsed_full:.4f}s")
    print(f"  Per-frame cost: {(elapsed_full/100)*1000:.2f}ms")
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Batch processing is {speedup:.1f}x faster for position wrapping alone")
    print(f"Full pipeline handles 220 stars in ~{(elapsed_full/100)*1000:.2f}ms per frame")
    print(f"Expected FPS headroom improvement: ~{speedup * 5:.1f}% at 60 FPS")
    print("="*70 + "\n")

if __name__ == '__main__':
    benchmark_batch_processing()

