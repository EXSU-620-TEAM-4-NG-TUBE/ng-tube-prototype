# EXSU620 browser bench monitor

## Consent and delivery evidence
Under More info → Recipient consent & phone receipt, record each recipient's initials/nickname and explicit agreement before sending. The startup consent checkbox registers the operator as a recipient. Consent is session-specific and saved with a UTC timestamp in SQLite and JSONL. It does not control access to the public ntfy topic.

After sending, select the notification and recipient, inspect that phone for the matching sample ID, and select Confirm receipt on phone. An optional screenshot filename/note links your separately stored evidence. PHONE_RECEIPT_CONFIRMED records recipient, sample ID, consent time, confirmation time and operator. Confirmation time is not measured arrival time. Server acceptance remains a separate event and never automatically counts as phone receipt. A recipient added after a message was sent must be tested with a new message. Duplicate confirmations are not duplicated in the audit log.

Additional POST routes: /api/notifications/consent (recipient, agreed); /api/notifications/receipt (sample_id, recipient_id, observed, evidence_note).

Windows local browser dashboard backed by a Python REST service, USB serial, SQLite and JSONL. No Tkinter is used. Pico firmware remains `button_stop_update/main.py` (sample_response_v8); this migration does not change measurement rules or calibration.

## Run
1. Save the current firmware as main.py on the Pico. Close Thonny and the old desktop monitor so COM8 is available.
2. Connect the Pico. Double-click `../start_browser_monitor.cmd`.
3. Keep the service window open. The browser opens http://127.0.0.1:8765 . Enter operator initials and session label.
4. Phone notifications are optional: tick consent only for your subscribed Android device. The ntfy topic EXSU620_TEAM4_NGTUBE is public; use no personal or patient information.
5. Enter a sample label and select NEW SAMPLE. The device supplies the result at 21 seconds. The browser does not manufacture a result when the timer reaches zero.
6. On-screen ACK silences audio for 120 seconds. The physical button stops the test through Pico firmware. NEW SAMPLE restarts measurement.
7. Unplug/replug is supported without closing the browser; after reconnection choose NEW SAMPLE. Interrupted measurements are discarded. Critical latch history is retained.
8. Ctrl+C in the service window stops the service. Closing a browser tab does not stop the service or laptop alarms.

Install dependencies, if needed: `python -m pip install -r requirements.txt`. The launcher prefers the normal per-user Thonny Python installation, falling back to Python on PATH. Audio comes from the Windows service through laptop speakers.

## Architecture and evidence
Pico sensor/LED/button → USB JSON → Python service → SQLite/JSONL; browser ↔ HTTP REST ↔ service; service → ntfy → opted-in Android device. No internet is needed for local measurement; phone delivery requires internet. ntfy acceptance is logged separately from actual phone receipt, which must be checked by the operator.

Logs are in `browser_monitor/bench_logs/`: one JSONL per service run plus bench.sqlite3. More info displays raw device metadata, trace, critical latch, calibration information, recent events and the known-buffer response-check controls. Session consent is timestamped in the audit log. Existing desktop logs are not moved.

Weekly calibration age comes from the Pico record and time sync. If an existing record lacks a completion timestamp, enter its actual UTC completion time under More info; do not enter today's time for an older calibration. No new calibration is performed by that control.

Routine samples do not infer stuck behavior from similar pH values. A separate known-buffer response check captures a valid baseline before the operator transfers the probe. It uses the existing firmware stuck definition and does not issue a feeding verdict on success.

## REST API
All routes are local to 127.0.0.1. GET /api/status returns a csrf_token; POST requires it in X-CSRF-Token, JSON content and a same-origin request.

| Method | Route | Purpose |
|---|---|---|
| GET | /api/health | Service version |
| GET | /api/status | Display state, current device data and timer |
| GET | /api/events | Last 100 audit events |
| POST | /api/session | operator, label, phone_consent |
| POST | /api/samples/new | label |
| POST | /api/ack | Silence current alarm |
| POST | /api/calibration/time | completed_utc (ISO timestamp with timezone) |
| POST | /api/probe-response/prepare | Capture live valid baseline |
| POST | /api/probe-response/start | token, source_ph, target_ph, transfer_confirmed |
| POST | /api/notifications/test | Send opted-in bench test notification |

This is an educational bench prototype, not a clinical feeding authorization system. User-requested verdict labels are retained with a persistent bench-only banner. The weekly lifetime and accuracy claims require their separate justification and verification. REST/browser implementation does not itself verify hardware, alarm audibility or phone delivery. Document the instructor-approved laptop audio substitution and any approval of ntfy as the notification alternative in the report.
