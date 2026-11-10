
# Reuse saved calibration for one bench session.
# Does not collect new calibration measurements.
import json
import os

with open("calibration_record.json", "r") as f:
    cal = json.load(f)

raw4 = float(cal["raw_ph4"])
raw7 = float(cal["raw_ph7"])
limit = int(cal["session_limit_ms"])
cal_id = cal["calibration_id"]

if not (100 < raw4 < raw7 < 65435 and raw7 - raw4 > 500):
    raise ValueError("Saved calibration coefficients are invalid.")

if not (0 < limit <= 600000):
    raise ValueError("Saved session duration is invalid.")

# Remove any previous unused authorization.
try:
    os.remove("calibration_pending.json")
except OSError as exc:
    if exc.args[0] != 2:
        raise

print("Saved calibration:", cal_id)
print("Reusing coefficients; calibration accuracy/age not rechecked.")

operator = input("Operator initials: ").strip()
if not operator:
    raise ValueError("Operator initials required.")

if input("Type REUSE to start another bench session: ").strip() != "REUSE":
    raise ValueError("Cancelled.")

event = {
    "event_type": "CALIBRATION_REUSED",
    "calibration_id": cal_id,
    "operator": operator,
    "new_buffer_capture": False,
    "calibration_age_verified": False,
    "bench_only": True
}

with open("calibration_reuse_log.jsonl", "a") as f:
    f.write(json.dumps(event) + "\n")

with open("calibration_pending.json", "w") as f:
    json.dump({"calibration_id": cal_id}, f)

print("READY. Run main.py once, then use the laptop monitor.")
