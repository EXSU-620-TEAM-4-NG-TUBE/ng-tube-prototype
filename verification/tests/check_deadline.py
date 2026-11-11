"""Check timing and refusal at the current firmware decision deadline."""

import ast
import json
import textwrap
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

source = (Path(__file__).resolve().parents[2] / "firmware" / "main.py").read_text(encoding="utf-8")
tree = ast.parse(source)
helper_names = {"decide", "drift_summary", "signal_out_of_range", "stuck_summary"}
setting_names = {"SETTLING_DEADLINE_MS", "DRIFT_LIMIT_PH", "ADC_MIN", "ADC_MAX", "STUCK_LIMIT_PH", "STUCK_DURATION_MS"}
settings = [
    node for node in tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id in setting_names for target in node.targets)
]
helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in helper_names]
env = {}
exec(compile(ast.Module(body=settings + helpers, type_ignores=[]), "firmware checks", "exec"), env)
start = source.index("        ready = sample_elapsed")
end = source.index("        if calibration_valid and sample_id is None:", start)
decision = compile(textwrap.dedent(source[start:end]), "deadline", "exec")
deadline = env["SETTLING_DEADLINE_MS"]


def check(age, settled=True, valid=True, raw=34000):
    capture = {
        second: dict(ph=7, raw=raw, actual_ms=second * 1000, on_time=True)
        for second in range(1, 21)
    }
    state = dict(
        env, json=json, capture=capture, sample_elapsed=age, elapsed=age,
        sample_id="bench", filtered_ph=7, settled=settled, calibration_valid=valid,
        fault=raw > env["ADC_MAX"], evaluating=age >= deadline, deadline_checked=False,
        sample_stopped=False, drift_info=None, spread=0.1, stuck_baseline=None,
        known_buffer_changed=False,
    )
    with redirect_stdout(StringIO()):
        exec(decision, state)
    return state


assert check(deadline - 1)["verdict"] is None
assert check(deadline)["verdict"] == "DO_NOT_FEED"
for result, reason in [
    (check(deadline, settled=False), "UNABLE_TO_SETTLE"),
    (check(deadline, valid=False), "CALIBRATION_INVALID"),
    (check(deadline, raw=env["ADC_MAX"] + 1), "SIGNAL_OUT_OF_RANGE"),
]:
    assert result["reason"] == reason
    assert result["sample_stopped"] and result["verdict"] is None
print("PASS: deadline publication, unsettled refusal, calibration and signal faults.")
