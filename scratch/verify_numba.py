import sys
import os
import numpy as np

# Add src to path
sys.path.append(os.path.abspath('.'))

from src.math_engine import world_to_camera_batch, project_to_screen_batch
from src.camera import Camera

def test_batch_projection():
    print("Testing batch projection...")
    cam = Camera(1280, 720)
    cam.update((0, 0, 0), (1, 0, 0, 0)) # Identity orientation
    
    verts = np.array([
        [0, 0, 10],
        [1, 1, 20],
        [-1, -1, 5]
    ], dtype=np.float64)
    
    # 1. World to Camera
    cam_verts = cam.world_to_camera_batch(verts)
    print("Cam Verts:\n", cam_verts)
    # Since identity, should be same as verts
    assert np.allclose(cam_verts, verts)
    
    # 2. Project
    projected = cam.project_batch(cam_verts)
    print("Projected:\n", projected)
    
    # 3. Individual project for comparison
    for i in range(len(verts)):
        p = cam.project(*cam_verts[i])
        print(f"Indiv {i}: {p}")
        if p:
            assert np.allclose(projected[i, 0], p[0])
            assert np.allclose(projected[i, 1], p[1])
            assert np.allclose(projected[i, 2], p[2])
            
    print("Verification successful!")

if __name__ == "__main__":
    try:
        test_batch_projection()
    except Exception as e:
        print(f"Error during verification: {e}")
        sys.exit(1)
