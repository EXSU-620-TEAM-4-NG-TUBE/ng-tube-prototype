from machine import ADC, Pin
from time import ticks_ms, ticks_diff, sleep_ms
import neopixel
import json
import os
import sys
import select

adc = ADC(26)
ring = neopixel.NeoPixel(Pin(15), 16)

# Derived from your original calibration datasets.
RAW_PH4 = 34099.2941
RAW_PH7 = 39095.7692
CAL_ID = "two_point_4_7_v1"

# PROVISIONAL engineering settings, not verified performance.
DRIFT_LIMIT_PH = 0.40
STUCK_LIMIT_PH = 0.10
STUCK_DURATION_MS = 15000
ADC_MIN = 500
ADC_MAX = 45000
WINDOW_N = 10
MAX_SPREAD_PH = 0.35
MIN_WAIT_MS = 0  # Track stability from the beginning.
SETTLING_DEADLINE_MS = 21000
SAMPLE_TOLERANCE_MS = 250
STABLE_DWELL_MS = 10000

DIM = (3, 3, 3)
CYAN = (0, 8, 8)
OFF = (0, 0, 0)

def signal_out_of_range(raw):
    return raw < ADC_MIN or raw > ADC_MAX

def stuck_summary(capture, baseline, known_change):
    result = {"assessed": False, "failed": False, "baseline_ph": baseline,
              "known_buffer_changed": known_change, "limit_ph": STUCK_LIMIT_PH,
              "required_duration_ms": STUCK_DURATION_MS,
              "filter": "3-reading moving average"}
    if not known_change:
        result["reason"] = "NOT_ASSESSED_ROUTINE_SAMPLE"
        return result
    if baseline is None:
        result["reason"] = "NO_PREVIOUS_SAMPLE_BASELINE"
        return result
    # Full three-reading filters exist from second 3 onwards.
    if not all(s in capture and capture[s]["on_time"] for s in range(1,21)):
        result["reason"] = "INCOMPLETE_CAPTURE"
        return result
    values = [capture[s]["filtered_ph"] for s in range(3,21)]
    duration = capture[20]["actual_ms"] - capture[3]["actual_ms"]
    excursion = max(abs(value-baseline) for value in values)
    result.update({"assessed": True, "observed_duration_ms": duration,
        "max_excursion_ph": excursion,
        "failed": duration >= STUCK_DURATION_MS and round(excursion,9) <= STUCK_LIMIT_PH,
        "reason": "STUCK" if duration >= STUCK_DURATION_MS and round(excursion,9) <= STUCK_LIMIT_PH else "MEANINGFUL_MOVEMENT"})
    return result

def drift_summary(first, last, count):
    # Non-overlapping groups, actual sample readings, no filtering of jumps.
    if count < 6 or len(first) != 3 or len(last) != 3:
        return None
    if not all(0 <= value <= 14 for value in first + last):
        return None
    initial = sum(first) / 3.0
    recent = sum(last) / 3.0
    delta = round(recent - initial, 9)
    return {"first_three_mean_ph": initial, "last_three_mean_ph": recent,
            "difference_ph": delta, "absolute_difference_ph": abs(delta),
            "limit_ph": DRIFT_LIMIT_PH, "failed": abs(delta) > DRIFT_LIMIT_PH}

def decide(ph, settled, calibration_valid, adc_fault):
    if not calibration_valid:
        return "TECHNICAL", None, "CALIBRATION_INVALID"
    if adc_fault:
        return "TECHNICAL", None, "ADC_FAULT"
    if ph is None or not (0 <= ph <= 14):
        return "TECHNICAL", None, "INVALID_VALUE"
    if not settled:
        return "TECHNICAL", None, "NOT_SETTLED"
    if ph <= 5.5:
        return "NORMAL", "GASTRIC_RANGE", "VALID"
    if ph <= 6.0:
        return "ADVISORY", "ESCALATE", "VALID"
    return "CRITICAL", "DO_NOT_FEED", "VALID"


COLORS = {
    "NORMAL": (0, 8, 0),
    "ADVISORY": (8, 3, 0),
    "CRITICAL": (8, 0, 0),
    "TECHNICAL": (0, 8, 8),
}

# Seven days from the recorded calibration completion, not from startup.
CAL_LIFETIME_SECONDS = 7 * 24 * 60 * 60
calibration_operator = None
calibration_load_error = None
calibrated_at = None
clock_unix_ms = None
clock_tick = ticks_ms()
record = None
reboot_locked = True
try:
    with open("calibration_record.json") as file:
        record = json.load(file)
    r4, r7 = float(record["raw_ph4"]), float(record["raw_ph7"])
    if not (100 < r4 < r7 < 65435 and r7-r4 > 500):
        raise ValueError("Invalid calibration coefficients")
    RAW_PH4, RAW_PH7 = r4, r7
    CAL_ID = record["calibration_id"]
    calibration_operator = record["operator"]
    calibrated_at = record.get("calibrated_at_unix")
    if calibrated_at is not None and (type(calibrated_at) is not int or calibrated_at <= 0):
        raise ValueError("Invalid calibration timestamp")
except (OSError, ValueError, KeyError, TypeError) as exc:
    calibration_load_error = str(exc)

def update_clock():
    global clock_tick, clock_unix_ms
    now_tick = ticks_ms()
    delta = ticks_diff(now_tick, clock_tick)
    clock_tick = now_tick
    if clock_unix_ms is not None:
        clock_unix_ms += max(0, delta)

def calibration_remaining():
    if calibration_load_error or calibrated_at is None or clock_unix_ms is None:
        return 0
    age_ms = clock_unix_ms - calibrated_at * 1000
    if age_ms < 0:
        return 0
    return max(0, CAL_LIFETIME_SECONDS * 1000 - age_ms)

def handle_clock_command(cmd):
    global clock_unix_ms, clock_tick, calibrated_at, reboot_locked
    epoch = cmd.get("unix_time")
    if type(epoch) is not int or epoch < 1700000000:
        raise ValueError("Invalid laptop UTC time")
    update_clock()
    if clock_unix_ms is not None and epoch*1000 < clock_unix_ms-5000:
        raise ValueError("Laptop clock moved backwards")
    clock_unix_ms = max(epoch*1000, clock_unix_ms or 0)
    clock_tick = ticks_ms()
    if cmd["command"] == "REGISTER_CAL_TIME":
        stamp = cmd.get("calibrated_at_unix")
        if calibration_load_error or cmd.get("calibration_id") != CAL_ID:
            raise ValueError("Calibration mismatch")
        if calibrated_at is not None:
            raise ValueError("Calibration timestamp already recorded; recalibrate to renew")
        if type(stamp) is not int or not (1700000000 <= stamp <= epoch):
            raise ValueError("Invalid calibration completion time")
        updated = dict(record)
        updated["calibrated_at_unix"] = stamp
        updated["validity_seconds"] = CAL_LIFETIME_SECONDS
        updated["time_basis"] = "Operator-entered actual completion UTC; laptop clock"
        with open("calibration_record.tmp", "w") as file:
            json.dump(updated, file)
        os.rename("calibration_record.tmp", "calibration_record.json")
        calibrated_at = stamp
        print(json.dumps({"event_type": "CALIBRATION_TIME_REGISTERED", "calibration_id": CAL_ID,
                          "calibrated_at_unix": stamp, "expires_at_unix": stamp+CAL_LIFETIME_SECONDS}))
    reboot_locked = calibration_load_error is not None or calibrated_at is None

filter_values = []
filtered_ph = None
stuck_baseline = None
known_buffer_changed = False
stuck_info = None
capture = {}
last_slot = 0
first_three = []
last_three = []
reading_count = 0
drift_info = None
window = []
start = ticks_ms()
stable_since = None
sample_id = None
sample_stopped = False
terminal_reason = "SAMPLE_STOPPED"
deadline_checked = False
stopped_elapsed = None
last_measurement = None
sample_started_ms = None
command_buffer = ""
discard_command = False
command_poll = select.poll()
command_poll.register(sys.stdin, select.POLLIN)

def start_sample(new_id, baseline=None, known_change=False):
    global sample_id, sample_started_ms, window, stable_since
    global filter_values, filtered_ph, stuck_baseline, known_buffer_changed, stuck_info
    global first_three, last_three, reading_count, drift_info, capture, last_slot
    global sample_stopped, stopped_elapsed, last_measurement, terminal_reason, deadline_checked
    if not isinstance(new_id, str) or not (1 <= len(new_id) <= 48):
        raise ValueError("Invalid sample ID")
    if not all(c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in new_id):
        raise ValueError("Invalid sample ID characters")
    if baseline is not None and (type(baseline) not in (int,float) or not 0 <= baseline <= 14):
        raise ValueError("Invalid previous sample baseline")
    if type(known_change) is not bool:
        raise ValueError("Invalid buffer-change flag")
    if known_change and baseline is None:
        raise ValueError("Known-buffer response check requires a measured baseline")
    # Duplicate delivery of the same request must not restart settling.
    duplicate = new_id == sample_id
    if not duplicate:
        filter_values = []
        filtered_ph = None
        stuck_baseline = baseline
        known_buffer_changed = known_change
        stuck_info = None
        capture = {}
        last_slot = 0
        first_three = []
        last_three = []
        reading_count = 0
        drift_info = None
        sample_stopped = False
        terminal_reason = "SAMPLE_STOPPED"
        deadline_checked = False
        stopped_elapsed = None
        last_measurement = None
        sample_id = new_id
        sample_started_ms = ticks_ms()
        window = []
        stable_since = None
        ring.fill(CYAN)
        ring.write()
    print(json.dumps({
        "event_type": "NEW_SAMPLE_STARTED", "sample_id": sample_id,
        "sample_started_ms": ticks_diff(sample_started_ms, start),
        "elapsed_ms": ticks_diff(ticks_ms(), start),
        "duplicate": duplicate
    }))

def stop_sample():
    global sample_stopped, stopped_elapsed, window, stable_since, terminal_reason
    if sample_id is None or (sample_stopped and terminal_reason == "SAMPLE_STOPPED"):
        return
    sample_stopped = True
    terminal_reason = "SAMPLE_STOPPED"
    stopped_elapsed = ticks_diff(ticks_ms(), sample_started_ms)
    window = []
    stable_since = None
    ring.fill(OFF)
    ring.write()
    print(json.dumps({
        "event_type": "SAMPLE_STOPPED", "sample_id": sample_id,
        "elapsed_ms": ticks_diff(ticks_ms(), start),
        "sample_elapsed_ms": stopped_elapsed,
        "source": "PHYSICAL_BUTTON", "last_measurement": last_measurement
    }))

def poll_commands():
    global command_buffer, discard_command
    # Bound processing so button polling and measurement keep progressing.
    for _ in range(64):
        if not command_poll.poll(0):
            break
        char = sys.stdin.read(1)
        if not char:
            break
        if char == "\r":
            continue
        if char == "\n":
            text = command_buffer
            command_buffer = ""
            if discard_command:
                discard_command = False
                continue
            if not text:
                continue
            try:
                cmd = json.loads(text)
                if not isinstance(cmd, dict):
                    raise ValueError("Unknown command")
                if cmd.get("command") in ("TIME_SYNC", "REGISTER_CAL_TIME"):
                    handle_clock_command(cmd)
                elif cmd.get("command") == "NEW_SAMPLE":
                    start_sample(cmd.get("sample_id"),cmd.get("baseline_ph"),cmd.get("known_buffer_changed",False))
                else:
                    raise ValueError("Unknown command")
            except (ValueError, TypeError) as exc:
                print(json.dumps({"event_type": "COMMAND_ERROR", "error": str(exc)}))
        elif not discard_command:
            command_buffer += char
            if len(command_buffer) > 256:
                command_buffer = ""
                discard_command = True
                print(json.dumps({"event_type": "COMMAND_ERROR", "error": "Command too long"}))

button = Pin(14, Pin.IN, Pin.PULL_UP)
button_last = button.value()
button_stable = button_last
button_changed_ms = ticks_ms()
press_id = 0

def wait_with_button(duration_ms):
    global button_last, button_stable
    global button_changed_ms, press_id

    wait_start = ticks_ms()

    while ticks_diff(ticks_ms(), wait_start) < duration_ms:
        update_clock()
        poll_commands()
        now = ticks_ms()
        value = button.value()

        if value != button_last:
            button_last = value
            button_changed_ms = now

        if (
            value != button_stable
            and ticks_diff(now, button_changed_ms) >= 30
        ):
            button_stable = value

            if value == 0:
                press_id += 1
                print(json.dumps({
                    "event_type": "ACK_PRESS",
                    "press_id": press_id,
                    "elapsed_ms": ticks_diff(now, start),
                    "source": "PHYSICAL_BUTTON",
                    "sample_id": sample_id
                }))

                stop_sample()

        sleep_ms(10)
        
try:
    while True:
        update_clock()
        poll_commands()
        now = ticks_ms()
        elapsed = ticks_diff(now, start)
        sample_elapsed = None if sample_started_ms is None else ticks_diff(now, sample_started_ms)
        if sample_stopped:
            # Heartbeats preserve USB monitoring without taking new measurements.
            print(json.dumps({
                "elapsed_ms": elapsed, "sample_id": sample_id,
                "sample_elapsed_ms": stopped_elapsed,
                "state": "TECHNICAL", "reason": terminal_reason,
                "pH_estimate": None, "raw": None, "spread_pH": None,
                "settled": False, "verdict": None, "sample_stopped": True,
                "last_measurement": last_measurement, "drift_check": drift_info, "stuck_check": stuck_info,
                "calibration_valid": calibration_remaining() > 0,
                "calibration_remaining_ms": calibration_remaining(),
                "calibration_id": CAL_ID, "calibrated_at_unix": calibrated_at, "bench_only": True,
                "input_source": "SENSOR", "firmware_version": "sample_response_v8"
            }))
            wait_with_button(1000)
            continue
        # Anchor acquisition to NEW SAMPLE instead of accumulating sleep delays.
        slot = None if sample_elapsed is None else sample_elapsed // 1000
        if slot is not None:
            if slot < 1 or slot <= last_slot:
                wait_with_button(10)
                continue
            last_slot = slot

        evaluating = sample_id is not None and slot >= 21 and not deadline_checked
        if not evaluating:
            raw = adc.read_u16()
            ph = 4.0 + (raw - RAW_PH4) * 3.0 / (RAW_PH7 - RAW_PH4)
            if sample_id is not None:
                filter_values.append(ph)
                if len(filter_values) > 3:
                    filter_values.pop(0)
                filtered_ph = sum(filter_values)/len(filter_values)
            else:
                filtered_ph = None
            if sample_id is not None and 1 <= slot <= 20:
                capture[slot] = {"raw": raw, "ph": ph, "filtered_ph": filtered_ph, "actual_ms": sample_elapsed,
                                 "on_time": sample_elapsed - slot*1000 <= SAMPLE_TOLERANCE_MS}
        else:
            # Use the last acquired value, not a new 21-second reading.
            latest = capture.get(20)
            raw = latest["raw"] if latest else 0
            ph = latest["ph"] if latest else None
            filtered_ph = latest["filtered_ph"] if latest else None

        # User-defined signal acceptance range; does not prove cable failure.
        # Missing second-20 data is handled as MISSING_TIMED_READINGS.
        fault = signal_out_of_range(raw) if not evaluating or 20 in capture else False

        spread = None
        settled = False

        if evaluating:
            if len(window) == WINDOW_N:
                spread = max(window) - min(window)
            settled = stable_since is not None and ticks_diff(now, stable_since) >= STABLE_DWELL_MS
        elif fault:
            window = []
            stable_since = None
            state = "TECHNICAL_ADC_LIMIT"
        else:
            window.append(ph)
            if len(window) > WINDOW_N:
                window.pop(0)

            if len(window) == WINDOW_N:
                spread = max(window) - min(window)

            candidate = (
                sample_elapsed is not None
                and sample_elapsed >= MIN_WAIT_MS
                and spread is not None
                and spread <= MAX_SPREAD_PH
            )

            if candidate:
                if stable_since is None:
                    stable_since = now
                settled = (
                    ticks_diff(now, stable_since) >= STABLE_DWELL_MS
                )
            else:
                stable_since = None

            state = "STABLE_TEST" if settled else "MEASURING"

        calibration_valid = (
            calibration_remaining() > 0
        )
        ready = sample_elapsed is not None and sample_elapsed >= SETTLING_DEADLINE_MS
        state, verdict, reason = decide(filtered_ph, settled and ready, calibration_valid, fault)
        if evaluating:
            deadline_checked = True
            complete = all(s in capture and capture[s]["on_time"] for s in range(1,21))
            if complete:
                first_three = [capture[s]["ph"] for s in (1,2,3)]
                last_three = [capture[s]["ph"] for s in (18,19,20)]
                drift_info = drift_summary(first_three, last_three, 20)
                if drift_info is not None:
                    drift_info["first_seconds"] = [1,2,3]
                    drift_info["last_seconds"] = [18,19,20]
                    drift_info["actual_first_ms"] = [capture[s]["actual_ms"] for s in (1,2,3)]
                    drift_info["actual_last_ms"] = [capture[s]["actual_ms"] for s in (18,19,20)]
            stuck_info = stuck_summary(capture, stuck_baseline, known_buffer_changed)
            if not calibration_valid:
                reason = "CALIBRATION_INVALID"
            elif not complete:
                reason = "MISSING_TIMED_READINGS"
            elif any(signal_out_of_range(capture[s]["raw"]) for s in capture):
                reason = "SIGNAL_OUT_OF_RANGE"
            elif any(not (0 <= capture[s]["ph"] <= 14) for s in capture):
                reason = "INVALID_VALUE"
            elif stuck_info["failed"]:
                reason = "STUCK_FAILURE"
            elif not known_buffer_changed and drift_info["failed"]:
                reason = "DRIFT_FAILURE"
            elif not settled:
                reason = "UNABLE_TO_SETTLE"
            if reason == "VALID" and known_buffer_changed:
                state, verdict = "NORMAL", "PROBE_RESPONSE_DETECTED"
            if reason != "VALID":
                sample_stopped = True
                terminal_reason = reason
                stopped_elapsed = sample_elapsed
                state, verdict = "TECHNICAL", None
            print(json.dumps({"event_type": "FIXED_WINDOW_RESULT", "sample_id": sample_id,
                "elapsed_ms": elapsed, "sample_elapsed_ms": sample_elapsed,
                "reason": reason, "verdict": verdict, "drift_check": drift_info, "stuck_check": stuck_info,
                "complete_timed_capture": complete, "spread_pH": spread}))
        if ready and reason == "VALID" and known_buffer_changed:
            state, verdict = "NORMAL", "PROBE_RESPONSE_DETECTED"
        settled = settled and ready and not sample_stopped

        if calibration_valid and sample_id is None:
            state, verdict, reason = "TECHNICAL", None, "NO_SAMPLE"

        # Collect faults during the timed test; publish every result at 21 s.
        if fault and ready:
            state, verdict, reason = "TECHNICAL", None, "SIGNAL_OUT_OF_RANGE"
            settled = False
            if sample_id is not None:
                sample_stopped = True
                terminal_reason = reason
                stopped_elapsed = sample_elapsed

        if sample_id is not None and not ready:
            state, verdict, reason = "TECHNICAL", None, "MEASURING"
            settled = False
        ring.fill(OFF if sample_id is None else DIM if not ready else COLORS[state])
        ring.write()

        last_measurement = {
            "raw": raw, "pH_estimate": None if filtered_ph is None else round(filtered_ph, 3), "state": state,
            "reason": reason, "verdict": verdict, "elapsed_ms": elapsed,
            "sample_id": sample_id
        }
        print(json.dumps({
            "sample_stopped": sample_stopped,
            "test_mode": "PROBE_RESPONSE_CHECK" if known_buffer_changed else "ROUTINE_SAMPLE",
            "adc_min": ADC_MIN,
            "adc_max": ADC_MAX,
            "scheduled_second": slot,
            "measurement_actual_ms": (capture.get(20) or {}).get("actual_ms") if evaluating else sample_elapsed,
            "settling_deadline_ms": SETTLING_DEADLINE_MS,
            "drift_check": drift_info,
            "stuck_check": stuck_info,
            "settling_spread_limit_ph": MAX_SPREAD_PH,
            "elapsed_ms": elapsed,
            "sample_id": sample_id,
            "sample_elapsed_ms": sample_elapsed,
            "calibration_remaining_ms": calibration_remaining(),
            "firmware_version": "sample_response_v8",
            "spread_pH": None if spread is None else round(spread, 3),
            "raw": raw,
            "unfiltered_pH": None if ph is None else round(ph,3),
            "filter": "3-reading moving average",
            "pH_estimate": None if filtered_ph is None else round(filtered_ph, 3),
            "settled": settled,
            "state": state,
            "reason": reason,
            "calibration_id": CAL_ID, "calibrated_at_unix": calibrated_at,
            "calibration_valid": calibration_valid,
            "calibration_status": "PROVISIONAL_BENCH_ONLY",
            "verdict": verdict,
            "bench_only": True,
            "input_source": "SENSOR",
            "test_id": "T27_NEW_SAMPLE",
            "calibration_operator": calibration_operator,
            "calibration_load_error": calibration_load_error,
            "restart_locked": reboot_locked,
        }))
        
        wait_with_button(1000 if sample_id is None else 10)
finally:
    ring.fill(OFF)
    ring.write()