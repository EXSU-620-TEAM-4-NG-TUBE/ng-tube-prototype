
"""Provisional bench calibration for Pico.
Uses nominal pH 4.00 and 7.00 buffers.
Not validated for clinical use.
"""

from machine import ADC, Pin
from time import sleep
import json
import os
import random
import neopixel

MAX_CAL_SPREAD_PH = 0.95
SESSION_LIMIT_MS = 600000

adc = ADC(26)
ring = neopixel.NeoPixel(Pin(15), 16)


def remove_if_present(path):
    try:
        os.remove(path)
    except OSError as exc:
        if exc.args[0] != 2:
            raise


def capture(label):
    input(
        "Rinse, immerse exposed tip in nominal pH "
        + label
        + ", then press Enter: "
    )

    print("Waiting 60 seconds. Keep the probe still.")
    sleep(60)

    values = []
    print("Capturing 30 readings, one per second.")

    for i in range(30):
        value = adc.read_u16()

        if value <= 100 or value >= 65435:
            raise ValueError(
                "ADC near its limit; calibration stopped"
            )

        values.append(value)

        print(json.dumps({
            "event_type": "CAL_SAMPLE",
            "buffer_nominal": label,
            "sample_index": i,
            "raw": value,
        }))

        sleep(1)

    return values


try:
    # Revoke any unused authorization before starting.
    remove_if_present("calibration_pending.json")

    ring.fill((0, 8, 8))
    ring.write()

    print("PROVISIONAL BENCH CALIBRATION")
    print("Reference accuracy remains unresolved.")
    print(
        "Calibration spread limit: {:.2f} pH"
        .format(MAX_CAL_SPREAD_PH)
    )
    print("This limit is a development setting, not validated accuracy.")

    operator = input("Operator initials: ").strip()

    if not operator:
        raise ValueError("Operator required")

    four = capture("4.00")
    seven = capture("7.00")

    raw4 = sum(four) / len(four)
    raw7 = sum(seven) / len(seven)
    delta = raw7 - raw4

    if delta <= 500:
        raise ValueError(
            "Insufficient or reversed buffer separation; "
            "no session authorized"
        )

    spread4 = (max(four) - min(four)) * 3.0 / delta
    spread7 = (max(seven) - min(seven)) * 3.0 / delta

    print("Raw means:", raw4, raw7)
    print("pH 4 spread:", spread4)
    print("pH 7 spread:", spread7)

    if max(spread4, spread7) > MAX_CAL_SPREAD_PH:
        raise ValueError(
            "Spread exceeds provisional {:.2f} pH limit; "
            "no session authorized"
            .format(MAX_CAL_SPREAD_PH)
        )

    print("Spread check passed; this does NOT verify accuracy.")
    print("Do not authorize if the voltage/ADC mismatch persists.")

    confirmation = input(
        "Type BENCH to authorize one provisional session, "
        "or CANCEL to stop: "
    ).strip()

    if confirmation != "BENCH":
        raise ValueError("No session authorized")

    record = {
        "calibration_id": "bench-%08x" % random.getrandbits(32),
        "operator": operator,
        "status": "PROVISIONAL_BENCH_ONLY",
        "reference_integrity": "UNRESOLVED",
        "reference_pH4_nominal": 4.0,
        "reference_pH7_nominal": 7.0,
        "raw_ph4": raw4,
        "raw_ph7": raw7,
        "samples_ph4": four,
        "samples_ph7": seven,
        "spread_ph4": spread4,
        "spread_ph7": spread7,
        "calibration_spread_limit_ph": MAX_CAL_SPREAD_PH,
        "session_limit_ms": SESSION_LIMIT_MS,
        "session_limit_basis":
            "10 minute development setting, "
            "not validated calibration lifetime",
        "calendar_time": None,
        "calendar_time_note":
            "Record actual calibration time in lab notes; "
            "Pico clock not established",
    }

    archive = record["calibration_id"] + ".json"

    with open(archive, "w") as f:
        json.dump(record, f)

    with open("calibration_record.json", "w") as f:
        json.dump(record, f)

    # Write authorization only after both records are saved.
    with open("calibration_pending.json", "w") as f:
        json.dump({
            "calibration_id": record["calibration_id"]
        }, f)

    print("CALIBRATION RECORD:", archive)
    print("One 10-minute provisional bench session ready.")
    print("Authorization is consumed on the first main.py startup.")

finally:
    ring.fill((0, 0, 0))
    ring.write()
