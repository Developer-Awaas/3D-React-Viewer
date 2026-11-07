"""The measurement script finds wall-signature lines on a layer the parser's
own name gate excludes — reproduced on a fixture already known to have this
shape (plan_unnamed_layers_343.pdf: real walls on unnamed layer '6', see
test_cascade.py::test_geometry_retry_rescues_unnamed_layer_walls)."""
import os

import layer0_signature_report as L

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "plan_unnamed_layers_343.pdf")


def test_unnamed_layer_carries_paired_wall_signature_and_is_gated_out():
    with open(FIXTURE, "rb") as f:
        raw = f.read()
    m = L.measure_sheet(raw)
    rows = {r["layer"]: r for r in m["rows"]}

    layer6 = rows["6"]
    assert layer6["admitted_by_name"] is False   # the layer-name gate excludes it
    assert layer6["n_paired"] > 0                # it carries real wall signature
    assert layer6["n_in_struct_today"] == 0       # and none of it reaches struct


def test_a_named_wall_layer_is_admitted():
    with open(FIXTURE, "rb") as f:
        raw = f.read()
    m = L.measure_sheet(raw)
    rows = {r["layer"]: r for r in m["rows"]}

    wall = rows["pdf3_wall"]
    assert wall["admitted_by_name"] is True
    assert wall["n_paired"] > 0
    assert wall["n_in_struct_today"] >= wall["n_paired"]  # its paired lines DO reach struct
