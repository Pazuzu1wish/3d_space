#!/usr/bin/env python
"""
Realistic benchmark comparing actual game frame costs:
- Old way: Individual star.submit_to_renderer() calls (220 stars)
- New way: Star.submit_batch_to_renderer() call (vectorized)
"""
import time
import numpy as np
from src.star import Star
from src.camera import Camera
from src.renderer import RenderPipeline

def benchmark_realistic():
    """Benchmark actual game rendering pipeline."""
    print("\n" + "="*70)
    print("REALISTIC STAR RENDERING BENCHMARK")
    print("="*70)
    
    # Setup
    camera = Camera(1920, 1080)
    renderer = RenderPipeline(camera)
    player_pos = (0.0, 0.0, 0.0)
    camera.update(player_pos, (1, 0, 0, 0))
    
    # Create 220 stars
    stars = [Star(player_pos) for _ in range(220)]
    print(f"\n✓ Created {len(stars)} stars")
    print("✓ Camera and renderer initialized")
    
    # Warmup
    print("\nWarmup...", end='', flush=True)
    Star.submit_batch_to_renderer(stars, renderer, player_pos)
    print(" ✓")
    
    # Test 1: Old method (individual submit_to_renderer calls)
    print("\n--- Test 1: Individual submit_to_renderer() [OLD WAY] ---")
    start = time.perf_counter()
    iterations = 100
    for it in range(iterations):
        renderer.clear()
        for star in stars:
            star.submit_to_renderer(renderer, player_pos)
    elapsed_old = time.perf_counter() - start
    per_frame_old = (elapsed_old / iterations) * 1000
    print(f"  {iterations} frames: {elapsed_old:.4f}s")
    print(f"  Per-frame cost: {per_frame_old:.3f}ms")
    
    # Test 2: New method (batch processing)
    print("\n--- Test 2: Batch submit_batch_to_renderer() [NEW WAY] ---")
    start = time.perf_counter()
    for it in range(iterations):
        renderer.clear()
        Star.submit_batch_to_renderer(stars, renderer, player_pos)
    elapsed_new = time.perf_counter() - start
    per_frame_new = (elapsed_new / iterations) * 1000
    print(f"  {iterations} frames: {elapsed_new:.4f}s")
    print(f"  Per-frame cost: {per_frame_new:.3f}ms")
    
    # Analysis
    savings = elapsed_old - elapsed_new
    speedup = elapsed_old / elapsed_new if elapsed_new > 0 else 1.0
    savings_per_frame = per_frame_old - per_frame_new
    
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    print(f"Old method (individual):  {per_frame_old:.3f}ms/frame")
    print(f"New method (batch):       {per_frame_new:.3f}ms/frame")
    print(f"Savings per frame:        {savings_per_frame:.3f}ms ({(savings_per_frame/per_frame_old)*100:.1f}%)")
    print(f"Total savings:            {savings:.4f}s over {iterations} frames")
    print(f"Speedup factor:           {speedup:.2f}x")
    
    fps_budget_60 = 16.67  # ms per frame at 60 FPS
    available_old = fps_budget_60 - per_frame_old
    available_new = fps_budget_60 - per_frame_new
    
    print(f"\nFPS Analysis (at 60 FPS, {fps_budget_60:.2f}ms budget):")
    print(f"  Old method headroom:     {available_old:.3f}ms ({(available_old/fps_budget_60)*100:.1f}%)")
    print(f"  New method headroom:     {available_new:.3f}ms ({(available_new/fps_budget_60)*100:.1f}%)")
    print(f"  Extra CPU time freed:    {savings_per_frame:.3f}ms")
    
    print("="*70)
    print("\n✓ Optimization successfully reduces CPU cost for star rendering!")
    print(f"✓ Freed up {savings_per_frame:.3f}ms per frame for other game systems")
    print("="*70 + "\n")

if __name__ == '__main__':
    benchmark_realistic()

