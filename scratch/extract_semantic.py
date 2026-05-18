import json
from pathlib import Path

nodes = [
    # Document nodes
    {
        "id": "requirements_txt",
        "label": "requirements.txt",
        "file_type": "document",
        "source_file": "requirements.txt",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None
    },
    {
        "id": "workflows_graphify",
        "label": "graphify.md",
        "file_type": "document",
        "source_file": ".agents/workflows/graphify.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None
    },
    {
        "id": "rules_graphify",
        "label": "graphify.md",
        "file_type": "document",
        "source_file": ".agents/rules/graphify.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None
    },
    {
        "id": "extra_docs_quick_reference",
        "label": "QUICK_REFERENCE.md",
        "file_type": "document",
        "source_file": "extra_docs/QUICK_REFERENCE.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None
    },
    {
        "id": "extra_docs_optimization_summary",
        "label": "OPTIMIZATION_SUMMARY.md",
        "file_type": "document",
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None
    },
    {
        "id": "extra_docs_star_optimization_summary",
        "label": "STAR_OPTIMIZATION_SUMMARY.md",
        "file_type": "document",
        "source_file": "extra_docs/STAR_OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None
    },
    {
        "id": "extra_docs_collision_fix_summary",
        "label": "COLLISION_FIX_SUMMARY.md",
        "file_type": "document",
        "source_file": "extra_docs/COLLISION_FIX_SUMMARY.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None
    },
    {
        "id": "extra_docs_integration_example",
        "label": "INTEGRATION_EXAMPLE.md",
        "file_type": "document",
        "source_file": "extra_docs/INTEGRATION_EXAMPLE.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None
    },
    # Rationale/Concept nodes
    {
        "id": "concept_numba_jit",
        "label": "Numba JIT Position Wrapping",
        "file_type": "rationale",
        "source_file": "extra_docs/STAR_OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None,
        "rationale": "Uses compiled Numba functions to wrap all 220 star positions around the player, bypassing Python interpreter overhead and native loops."
    },
    {
        "id": "concept_batch_star_submission",
        "label": "Batch Star Submission",
        "file_type": "rationale",
        "source_file": "extra_docs/STAR_OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None,
        "rationale": "Replaces individual submission loops with a single batch call from game.py, freeing ~0.096ms per frame (~7% performance improvement)."
    },
    {
        "id": "concept_object_pooling",
        "label": "Object Pooling",
        "file_type": "rationale",
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None,
        "rationale": "Pre-allocates game entities (Particles and Lasers) to eliminate garbage collection spikes and runtime allocation overhead, boosting FPS by 10-30%."
    },
    {
        "id": "concept_spatial_partitioning",
        "label": "Spatial Partitioning",
        "file_type": "rationale",
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None,
        "rationale": "Uses hierarchical octrees and spatial hashing to reduce collision detection complexity from O(n²) to O(n log n) or O(n), saving 50-80% CPU."
    },
    {
        "id": "concept_massive_enemy_collision",
        "label": "Carrier Collision Box Fix",
        "file_type": "rationale",
        "source_file": "extra_docs/COLLISION_FIX_SUMMARY.md",
        "source_location": None,
        "source_url": None,
        "captured_at": None,
        "author": None,
        "contributor": None,
        "rationale": "Implements rotated 3D bounding box checks in local space to perfectly handle the massive 800-unit wedge Carrier, resolving spatial partition lookup boundaries."
    }
]

edges = [
    # Citations/References (EXTRACTED)
    {
        "source": "extra_docs_quick_reference",
        "target": "src_star_submit_batch_to_renderer",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/QUICK_REFERENCE.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_quick_reference",
        "target": "src_star_wrap_star_positions_batch",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/QUICK_REFERENCE.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_star_optimization_summary",
        "target": "src_star_wrap_star_positions_batch",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/STAR_OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_star_optimization_summary",
        "target": "src_star_submit_batch_to_renderer",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/STAR_OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_optimization_summary",
        "target": "src_object_pool_objectpool",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_optimization_summary",
        "target": "src_object_pool_particlepool",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_optimization_summary",
        "target": "src_object_pool_laserpool",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_optimization_summary",
        "target": "src_spatial_partition_spatialpartition",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_optimization_summary",
        "target": "src_spatial_partition_spatialhash",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_collision_fix_summary",
        "target": "src_enemy_carrier",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/COLLISION_FIX_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_collision_fix_summary",
        "target": "src_enemy_carrier_is_hit",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/COLLISION_FIX_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_integration_example",
        "target": "src_object_pool_particlepool",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/INTEGRATION_EXAMPLE.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_integration_example",
        "target": "src_object_pool_laserpool",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/INTEGRATION_EXAMPLE.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_integration_example",
        "target": "src_spatial_partition_spatialpartition",
        "relation": "cites",
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": "extra_docs/INTEGRATION_EXAMPLE.md",
        "source_location": None,
        "weight": 1.0
    },
    # Rationale Edges (INFERRED)
    {
        "source": "concept_numba_jit",
        "target": "src_star_wrap_star_positions_batch",
        "relation": "rationale_for",
        "confidence": "INFERRED",
        "confidence_score": 0.95,
        "source_file": "extra_docs/STAR_OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "concept_batch_star_submission",
        "target": "src_star_submit_batch_to_renderer",
        "relation": "rationale_for",
        "confidence": "INFERRED",
        "confidence_score": 0.95,
        "source_file": "extra_docs/STAR_OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "concept_object_pooling",
        "target": "src_object_pool_objectpool",
        "relation": "rationale_for",
        "confidence": "INFERRED",
        "confidence_score": 0.95,
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "concept_spatial_partitioning",
        "target": "src_spatial_partition_spatialpartition",
        "relation": "rationale_for",
        "confidence": "INFERRED",
        "confidence_score": 0.95,
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "concept_massive_enemy_collision",
        "target": "src_enemy_carrier_is_hit",
        "relation": "rationale_for",
        "confidence": "INFERRED",
        "confidence_score": 0.95,
        "source_file": "extra_docs/COLLISION_FIX_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    # Semantic Relationships (INFERRED)
    {
        "source": "extra_docs_star_optimization_summary",
        "target": "extra_docs_quick_reference",
        "relation": "conceptually_related_to",
        "confidence": "INFERRED",
        "confidence_score": 0.85,
        "source_file": "extra_docs/STAR_OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "extra_docs_optimization_summary",
        "target": "extra_docs_integration_example",
        "relation": "conceptually_related_to",
        "confidence": "INFERRED",
        "confidence_score": 0.85,
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "concept_numba_jit",
        "target": "concept_batch_star_submission",
        "relation": "conceptually_related_to",
        "confidence": "INFERRED",
        "confidence_score": 0.85,
        "source_file": "extra_docs/STAR_OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    },
    {
        "source": "concept_object_pooling",
        "target": "concept_spatial_partitioning",
        "relation": "conceptually_related_to",
        "confidence": "INFERRED",
        "confidence_score": 0.85,
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md",
        "source_location": None,
        "weight": 1.0
    }
]

hyperedges = [
    {
        "id": "optimization_systems",
        "label": "Game Engine Optimization Framework",
        "nodes": [
            "src_object_pool_objectpool",
            "src_spatial_partition_spatialpartition",
            "src_star_wrap_star_positions_batch"
        ],
        "relation": "implement",
        "confidence": "INFERRED",
        "confidence_score": 0.85,
        "source_file": "extra_docs/OPTIMIZATION_SUMMARY.md"
    }
]

semantic_result = {
    "nodes": nodes,
    "edges": edges,
    "hyperedges": hyperedges,
    "input_tokens": 12000,
    "output_tokens": 1500
}

out_path = Path("graphify-out/.graphify_semantic.json")
out_path.write_text(json.dumps(semantic_result, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Successfully generated semantic extraction with {len(nodes)} nodes and {len(edges)} edges!")
