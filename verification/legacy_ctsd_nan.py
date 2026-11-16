"""Observe the unmodified legacy program, then replay its captured numerical inputs."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import platform
import random
import runpy
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import scipy
from scipy.optimize import brentq


class NonfiniteCTSDFound(Exception):
    """Stop only after saving the first non-finite CTSD."""


def serial(value):
    if isinstance(value, np.ndarray):
        return serial(value.tolist())
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [serial(v) for v in value]
    return value


def write_json(path, value):
    path.write_text(json.dumps(serial(value), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def replay(source, capture, destination):
    def restore_ratios(values):
        return [np.asarray(value, dtype=float) if isinstance(value, list) else float(value) for value in values]

    scope = {"np": np, "brentq": brentq,
             "DataImport": SimpleNamespace(AA=float(capture["ctsd"]["interaction_constant"]))}
    names = {"safe_arccos", "CCn", "CC1", "gg", "CTSD"}
    functions = [node for node in ast.walk(ast.parse(source.read_text(encoding="utf-8-sig")))
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    if len(functions) != len(names):
        raise ValueError("Expected exactly one definition of each legacy numerical function")
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), scope)
    v = capture["ctsd"]
    a, c, n = float(v["a"]), float(v["c"]), v["n"]
    ratios = restore_ratios(v["ratios"])
    boundaries = np.asarray(v["boundaries"], dtype=float)
    with np.errstate(all="ignore"):
        result = scope["CTSD"](a, c, n, ratios, np.asarray(v["delta_tau"], dtype=float), boundaries)
        roots = []
        for call in capture["root_calls"]:
            residual = None
            if call["kind"] == "CCn":
                root_ratios = restore_ratios(call["ratios"])
                root_boundaries = np.asarray(call["boundaries"], dtype=float)
                root = scope["CCn"](call["a"], call["n"], root_ratios, root_boundaries)
                residual = np.pi / 2 - root_ratios[0] * scope["safe_arccos"](call["a"] / (root + 1e-10)) - sum(
                    (root_ratios[i + 1] - root_ratios[i]) * scope["safe_arccos"](root_boundaries[i] / (root + 1e-10))
                    for i in range(call["n"] + 1))
            else:
                root = scope["CC1"](call["a"], restore_ratios(call["ratios"]), call["boundary"])
            roots.append({"kind": call["kind"], "saved": call["root"], "replayed": root,
                          "exact": bool(root == float(call["root"])), "equation_residual": residual})
        geometry = []
        for boundary in boundaries[:n + 1]:
            effective = (1 - 1e-3) * boundary if a == boundary else boundary
            ca2, cx2 = c**2 - effective**2, c**2 - a**2
            ca, cx = np.sqrt(ca2), np.sqrt(cx2)
            geometry.append({"boundary": boundary, "effective_boundary": effective,
                             "c2_minus_effective_boundary2": ca2, "c2_minus_crack_depth2": cx2,
                             "log_argument1": abs((ca + cx) / (ca - cx)),
                             "log_argument2": abs((a * ca + effective * cx) / (a * ca - effective * cx)),
                             "root_angle": np.arccos(np.clip(boundary / (c + 1e-10), -1, 1)),
                             "gg": scope["gg"](a, c, boundary)})
    analysis = {"replayed_ctsd": result, "ctsd_is_nan": bool(np.isnan(result)),
                "ctsd_is_inf": bool(np.isinf(result)), "roots": roots, "geometry": geometry,
                "finite_ctsd_inputs": all(np.all(np.isfinite(value)) for value in
                                          [a, c, *ratios, *boundaries, np.asarray(v["delta_tau"], dtype=float),
                                           float(v["interaction_constant"])]),
                "used_boundary_count": len(boundaries[:n + 1]),
                "reached_boundary_count": int(np.count_nonzero(boundaries[:n + 1] <= c)),
                "unreached_boundary_in_integral": bool(np.any(boundaries[:n + 1] > c))}
    write_json(destination, analysis)
    if str(result) != str(float(v["result"])) or not all(root["exact"] for root in roots):
        raise AssertionError("Legacy replay did not reproduce the saved values")
    return analysis


def run(args):
    source = (args.repo_root / "multiscale-fatigue-model/Multiscale_fatigue_model.py").resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = [source, *sorted(source.parent.glob("N50R_*.csv")),
              source.parent / "N50R_CS_T50.inp", source.parent / "CombinedData_Ellipse_WF_CF.json",
              source.parent / "N50R_CS_FieldValues.pkl", source.parent / "N50R_CS_gData.pkl"]
    manifest = [{"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)} for path in inputs]
    write_json(output / "manifest.json", manifest)
    overrides = {"MFM_RANDOM_SEED": str(args.seed), "MFM_SIGMA_NOM": "135",
                 "MFM_ITERATIONS": ",".join(str(i) for i in range(args.iterations)),
                 "MFM_N_SYMM": str(args.symmetries), "MFM_OUTPUT_DIR": str(output / "csv"),
                 "MFM_MAX_ACTIVE_ELEMENTS": str(args.max_elements) if args.max_elements else None}
    previous_env = {key: os.environ.get(key) for key in overrides}
    summary = {"started_utc": datetime.now(timezone.utc).isoformat(), "seed": args.seed,
               "sigma_nom": 135, "iterations": args.iterations, "symmetries": args.symmetries,
               "max_elements": args.max_elements, "observe": not args.no_observe,
               "continue_after_capture": args.continue_after_capture,
               "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
               "index_convention": "all recorded indices are zero-based",
               "ctsd_calls": 0, "evalctsd_calls": 0, "candidate_calls": 0,
               "status": "running"}
    write_json(output / "summary.json", summary)
    roots, geometry, decisions = [], [], []
    capture = None
    # Only these existing lines need line events; numerical operations are untouched.
    decision_lines = {i for i, line in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), 1)
                      if line.strip() == "if σ_fr[m] < 1:"}

    def observe(frame, event, result):
        nonlocal capture
        name, state = frame.f_code.co_name, frame.f_locals
        if event == "line" and frame.f_lineno in decision_lines:
            m = state["m"]
            decisions.append(serial({"m": m, "tested_ratio": state["σ_fr"][m],
                                     "new_ratio": state["σ_fr"][m + 1]}))
        if event != "return" or result is None:
            return observe
        if name in {"CC1", "CCn"}:
            call = {"kind": name, "a": state["a"], "ratios": state["σ_fr"], "root": result}
            call.update({"n": state["n"], "boundaries": state["rnList"]} if name == "CCn"
                        else {"boundary": state["rnlist"]})
            roots.append(serial(call))
        elif name == "gg":
            geometry.append(serial({key: state[key] for key in ("x", "c", "ad", "a", "ca", "cx")}))
        elif name == "CTSD":
            summary["ctsd_calls"] += 1
            if capture is None and not np.all(np.isfinite(result)):
                context = {}
                caller = frame.f_back
                while caller:
                    if caller.f_code.co_filename == str(source):
                        keys = {"main": ("load_quene", "iteration", "i", "n"),
                                "ElementLife": ("n", "ia0", "ia", "Grain_i", "y", "z"),
                                "CrackLifeCalc": ("i", "aii", "r0", "r1", "rt1"),
                                "evalCTSD": ("jj", "m", "cc", "Δσ", "rnList", "σ_fr")}.get(caller.f_code.co_name, ())
                        context[caller.f_code.co_name] = {k: caller.f_locals[k] for k in keys if k in caller.f_locals}
                    caller = caller.f_back
                capture = serial({"context": context, "root_calls": roots, "layer_decisions": decisions,
                                  "geometry": geometry, "ctsd": {"a": state["a"], "c": state["c"],
                                  "n": state["n"], "ratios": state["σ_fr"], "delta_tau": state["Δτ_j"],
                                  "boundaries": state["rnList_L"], "result": result,
                                  "interaction_constant": frame.f_globals["DataImport"].AA}})
                write_json(output / "capture.json", capture)
                if not args.continue_after_capture:
                    raise NonfiniteCTSDFound
        return observe

    def trace(frame, event, arg):
        if event != "call" or frame.f_code.co_filename != str(source):
            return None
        name = frame.f_code.co_name
        if name == "main":
            params = frame.f_globals["BasicParams"]
            summary["effective_parameters"] = serial({key: getattr(params, key) for key in
                ("name", "σ_nom", "iteration_num", "n_symm", "stress_lim", "AeNum", "thickness",
                 "width", "R_ratio", "c_paris", "n_paris", "Δδ_th")})
            write_json(output / "summary.json", summary)
        if name == "CrackLifeCalc":
            summary["candidate_calls"] += 1
        if name == "evalCTSD":
            summary["evalctsd_calls"] += 1
            roots.clear()
            geometry.clear()
            decisions.clear()
        if name in {"CTSD", "evalCTSD", "CCn", "CC1", "gg"}:
            frame.f_trace_lines = name == "evalCTSD"
            return observe
        return None

    previous_trace, previous_cwd = sys.gettrace(), Path.cwd()
    started = time.monotonic()
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if not args.no_observe:
            sys.settrace(trace)
        runpy.run_path(str(source), run_name="__main__")
        summary["status"] = "completed"
    except NonfiniteCTSDFound:
        summary["status"] = "nonfinite_ctsd_captured"
    except BaseException as error:
        summary.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "error",
                       error=f"{type(error).__name__}: {error}")
        raise
    finally:
        sys.settrace(previous_trace)
        os.chdir(previous_cwd)
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        summary["elapsed_seconds"] = time.monotonic() - started
        summary["ended_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(output / "random_state.json", {"python": random.getstate(), "numpy": np.random.get_state()})
        summary["input_hashes_unchanged"] = all(digest(Path(item["path"])) == item["sha256"] for item in manifest)
        write_json(output / "summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    if capture:
        analysis = replay(source, capture, output / "analysis.json")
        print(f"Legacy replay: NaN={analysis['ctsd_is_nan']}, inf={analysis['ctsd_is_inf']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--symmetries", type=int, default=1)
    parser.add_argument("--max-elements", type=int, default=1, help="0 uses the legacy default range")
    parser.add_argument("--no-observe", action="store_true")
    parser.add_argument("--continue-after-capture", action="store_true",
                        help="Keep the original execution running after saving the first event for CSV comparison")
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--analysis-file", type=Path)
    args = parser.parse_args()
    if args.replay:
        capture = json.loads(args.replay.read_text(encoding="utf-8"))
        destination = args.analysis_file or args.replay.with_suffix(".replay.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        replay(args.repo_root / "multiscale-fatigue-model/Multiscale_fatigue_model.py", capture,
               destination)
    else:
        if args.output_dir is None or args.iterations < 1 or args.symmetries < 1 or args.max_elements < 0:
            parser.error("Provide --output-dir and positive iteration/symmetry counts; max-elements must be >= 0")
        run(args)


if __name__ == "__main__":
    main()
