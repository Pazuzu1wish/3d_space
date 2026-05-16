# Rendering Optimization: Ships & Asteroids with NumPy + Njit

## Overview
Optimized the rendering pipeline for ships and asteroids by moving face color calculations into the NumPy/Njit layer, eliminating repeated Python-level color computation.

## Key Changes

### 1. **Enhanced Numba Function Signature**
**Before:**
```python
def process_faces_batch_numba(cam_verts, projected, face_indices):
    # ... returns (valid_mask, shades, avg_zs)
    # Shade was a single int per face
```

**After:**
```python
def process_faces_batch_numba(cam_verts, projected, face_indices, face_colors):
    # ... returns (valid_mask, shaded_colors, avg_zs)
    # shaded_colors is (N_faces, 3) RGB tuples, pre-computed
```

**Benefit:** Color multiplication happens once inside the fast JIT-compiled loop, not repeatedly in Python.

### 2. **Color Shading Computed in Njit**
The numba function now:
- Takes `face_colors` (N x 3 array of base colors)
- Computes the shade value for each face (lighting)
- Applies the shade multiplicatively to the RGB channels
- Returns fully shaded RGB tuples

This eliminates the Python loop overhead:
```python
# OLD (Python loop after numba)
for i in range(len(face_indices)):
    shade = shades[i]
    r = int(face_colors[i, 0] * (shade / 255.0))  # Python computation
    g = int(face_colors[i, 1] * (shade / 255.0))
    b = int(face_colors[i, 2] * (shade / 255.0))
    # ... append to layer

# NEW (All in numba, return ready-to-use colors)
for i in range(len(face_indices)):
    if valid_mask[i]:
        color = tuple(shaded_colors[i])  # Already shaded
        # ... append to layer
```

### 3. **Pre-cached Face Arrays**
The `submit_mesh` function already caches face indices and colors:
- Face indices are cached once per unique mesh
- Face colors are now also pre-converted to numpy int32 arrays
- This avoids repeated list-to-array conversions on every frame

## Performance Improvements

1. **Reduced Python Loop Iterations**: Color multiplication now happens in fast JIT code
2. **Better Cache Locality**: All face data (indices + colors) processed together in numba
3. **Eliminated Intermediate Steps**: No shade-to-color multiplication in Python
4. **Consistent with Existing Pattern**: Uses same numba optimization approach as vertex transforms

## Impact on Ships & Asteroids

Both entity types already use `submit_mesh()`:
- **Asteroids** (20 faces per asteroid, ~100+ asteroids)
- **Enemy Ships** (varying face counts per ship type)

The optimization is most beneficial when rendering many faces across multiple entities.

## Testing

- Game starts without errors ✓
- Rendering pipeline functions correctly ✓
- Mesh caching still works as expected ✓
- No visual regressions observed ✓

## Future Optimizations

Consider:
1. Further batching multiple meshes into single numba call
2. Pre-computing world transforms for static meshes
3. Using depth prepass for early triangle rejection
4. Implementing GPU rendering path (e.g., Pygame+ or custom opengl)

