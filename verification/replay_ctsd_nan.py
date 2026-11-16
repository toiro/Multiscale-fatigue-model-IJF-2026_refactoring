from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.optimize import brentq

from multiscale_fatigue_model_ijf_2026.calculation import crack_life


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay captured CTSD inputs without loading the stress fields.")
    parser.add_argument("trace", type=Path)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--analysis-file", type=Path, required=True)
    args = parser.parse_args()
    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    value = trace["ctsd"]
    a, c, n = value["a"], value["c"], value["n"]
    ratios = [np.asarray(v) if isinstance(v, list) else v for v in value["ratios"]]
    boundaries = value["boundaries"]
    delta_tau = np.asarray(value["delta_tau"])
    k = value["interaction_constant"]
    root = crack_life._solve_multilayer_slip_band_length(a, n, ratios, boundaries)
    used = boundaries[:n + 1]
    reached = sum(boundary <= c for boundary in used)
    assert reached < len(used), "This trace does not contain an unreached boundary in the integral."
    assert used == sorted(used)
    reached_n = reached - 1
    reached_root = crack_life._solve_multilayer_slip_band_length(a, reached_n, ratios, boundaries)
    with np.errstate(all="ignore"):
        result = crack_life._calculate_ctsd_value(a, c, n, ratios, delta_tau, boundaries, k)
        # A counterfactual local evaluation, not a change to the model algorithm.
        reached_only = crack_life._calculate_ctsd_value(a, c, reached_n, ratios, delta_tau, boundaries, k)
    assert np.isnan(result)
    assert np.isfinite(reached_only)
    assert root == c, "Captured solver output was not reproduced exactly."

    # Execute only the four nested numerical functions, never the legacy program.
    legacy_source = args.repo_root / "multiscale-fatigue-model/Multiscale_fatigue_model.py"
    tree = ast.parse(legacy_source.read_text(encoding="utf-8-sig"))
    names = {"safe_arccos", "CCn", "gg", "CTSD"}
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(functions) == len(names)
    scope = {"np": np, "brentq": brentq, "DataImport": SimpleNamespace(AA=k)}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(legacy_source), "exec"), scope)
    with np.errstate(all="ignore"):
        legacy_root = scope["CCn"](a, n, ratios, boundaries)
        legacy_ctsd = scope["CTSD"](a, c, n, ratios, delta_tau, boundaries)
    assert legacy_root == root
    assert np.isnan(legacy_ctsd)

    queries = [boundary / (c + 1e-10) for boundary in used]
    angles = [float(np.arccos(np.clip(q, -1, 1))) for q in queries]
    residual = np.pi / 2 - ratios[0] * np.arccos(np.clip(a / (c + 1e-10), -1, 1)) - sum(
        (ratios[i + 1] - ratios[i]) * angles[i] for i in range(n + 1)
    )
    summary = {
        "seed": trace["seed"], "evaluation_index": trace["evaluation"]["index"],
        "a": a, "c": c, "integral_boundary_count": n + 1,
        "reached_boundary_count": reached, "used_boundaries": used,
        "sqrt_radicands": [c**2 - boundary**2 for boundary in used],
        "root_arccos_queries": queries, "root_clipped_arccos_values": angles,
        "root_residual": float(np.asarray(residual).item()),
        "root_using_reached_boundary_equation": reached_root,
        "root_calls_at_this_crack_depth": [
            {"n": call.get("n"), "root": call["root"]}
            for call in trace["root_calls"] if call["a"] == a
        ],
        "layer_root_decisions": [
            {"m": i, "tested_ratio": float(np.asarray(ratios[i]).item()),
             "new_ratio": float(np.asarray(ratios[i + 1]).item()),
             "keeps_through_thickness_slip_band": bool(np.asarray(ratios[i]).item() < 1)}
            for i in range(n + 1)
        ],
        "root_reproduced_exactly": root == c,
        "legacy_root_reproduced_exactly": legacy_root == root,
        "ctsd_is_nan": bool(np.isnan(result)), "legacy_ctsd_is_nan": bool(np.isnan(legacy_ctsd)),
        "ctsd_using_reached_boundaries_only": reached_only,
        "note": "The reached-boundaries-only value is a diagnostic counterfactual; no model correction was applied.",
    }
    path = args.analysis_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Local replay passed: {path}")


if __name__ == "__main__":
    main()
