
"""Reuse an existing calibration for one bench session.
Does not measure buffers or establish calibration accuracy.
Does not overwrite the saved calibration.
"""

import json
import os

PENDING_FILE = "calibration_pending.json"

# Remove any old, unused session permission.
try:
    os.remove(PENDING_FILE)
except OSError as exc:
    if exc.args[0] != 2:
        raise

# Load and check the existing calibration.
with open("calibration_record.json") as f:
    record = json.load(f)

if not isinstance(record, dict):
    raise ValueError("Invalid calibration record")

raw4 = float(record["raw_ph4"])
raw7 = float(record["raw_ph7"])
cal_id = record["calibration_id"]
limit = record["session_limit_ms"]

if not (100 < raw4 < raw7 < 65435 and raw7 - raw4 > 500):
    raise ValueError("Invalid calibration coefficients")

if not isinstance(cal_id, str) or not cal_id:
    raise ValueError("Missing calibration ID")

if type(limit) is not int or not (0 < limit <= 600000):
    raise ValueError("Unsupported session duration")

print("REUSE SAVED CALIBRATION — BENCH ONLY")
print("Calibration ID:", cal_id)
print("Original operator:", record.get("operator", "unknown"))
print("Raw pH 4:", raw4)
print("Raw pH 7:", raw7)
print("Session duration:", limit // 60000, "minutes")
print("Actual calibration age and accuracy are NOT verified.")
print("No new buffer measurements will be taken.")

operator = input("Your initials: ").strip()
if not operator:
    raise ValueError("Operator initials required")

confirmation = input(
    "If wiring is unchanged and you will check a known buffer, "
    "type REUSE; otherwise press Enter to cancel: "
).strip()

if confirmation != "REUSE":
    raise ValueError("Cancelled; no session authorized")

# Preserve an audit record of the reuse action.
# The Pico clock is not treated as a reliable calendar clock.
reuse_event = {
    "event_type": "BENCH_CALIBRATION_REUSE",
    "calibration_id": cal_id,
    "operator": operator,
    "session_limit_ms": limit,
    "new_buffer_capture": False,
    "calibration_age_verified": False,
    "calendar_time": None,
}

with open("calibration_reuse_log.jsonl", "a") as f:
    f.write(json.dumps(reuse_event) + "\n")

# Existing main.py consumes this permission on its next startup.
with open(PENDING_FILE, "w") as f:
    json.dump({
        "calibration_id": cal_id,
        "authorization_basis": "OPERATOR_REQUESTED_BENCH_REUSE",
        "reuse_operator": operator,
        "calibration_age_verified": False,
    }, f)

print("REUSE EVENT:", json.dumps(reuse_event))
print("One bench session authorized using the saved calibration.")
print("Close Thonny, unplug/replug once, then launch the monitor.")
