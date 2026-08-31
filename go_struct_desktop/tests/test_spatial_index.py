from __future__ import annotations

from go_struct_desktop.spatial_index import CanvasSpatialIndex, nearest_point


def _crossing_model() -> dict[str, object]:
    return {
        "nodes": [
            {"id": 1, "x": 0.0, "y": 0.0},
            {"id": 2, "x": 4.0, "y": 4.0},
            {"id": 3, "x": 0.0, "y": 4.0},
            {"id": 4, "x": 4.0, "y": 0.0},
        ],
        "elements": [
            {"id": 1, "n1": 1, "n2": 2},
            {"id": 2, "n1": 3, "n2": 4},
        ],
        "nloads": [{"node": 1, "fx": 10.0}],
        "eloads": [{"elem": 2, "type": "Point Force", "x_m": 2.0}],
    }


def test_spatial_index_caches_member_midpoints_and_intersections() -> None:
    index = CanvasSpatialIndex(_crossing_model())

    nearest = nearest_point((2.0, 2.0), index.snap_points_near((2.0, 2.0), 0.2))

    assert index.bounds == (0.0, 0.0, 4.0, 4.0)
    assert nearest is not None
    assert nearest[0] == 0.0
    assert nearest[1] == (2.0, 2.0)
    assert {int(segment.member["id"]) for segment in index.members_near((2.0, 2.0), 0.2)} == {1, 2}


def test_spatial_index_limits_node_and_load_candidates_to_nearby_cells() -> None:
    index = CanvasSpatialIndex(_crossing_model())

    assert [int(node["id"]) for node in index.nodes_near((0.0, 0.0), 0.2)] == [1]
    assert {(kind, item_index) for kind, item_index, _ in index.loads_near((0.0, 0.0), 0.2)} == {("nodal", 0)}
    # The member action is two metres along the diagonal from node 3, not at its midpoint.
    assert {(kind, item_index) for kind, item_index, _ in index.loads_near((1.414, 2.586), 0.2)} == {("member", 0)}
