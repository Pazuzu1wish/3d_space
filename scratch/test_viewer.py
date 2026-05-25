import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()

import importlib
viewer_module = importlib.import_module("tools.3d_viewer_debug_claude")
DebugViewer = viewer_module.DebugViewer

def main():
    print("Initializing DebugViewer...")
    viewer = DebugViewer()
    
    # Verify we can load all 9 models!
    for idx, (name, _) in enumerate(viewer.models):
        print(f"Testing load of model: {name}...")
        viewer.load_model(idx)
        assert len(viewer.verts) > 0, f"Model {name} had no vertices!"
        assert len(viewer.faces) > 0, f"Model {name} had no faces!"
        
    print("\n[SUCCESS] Headless model loader validation passed perfectly for all meshes!")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        exit(1)
