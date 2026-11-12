# Report evidence index

Evidence IDs (E01–E23) are cross-references assigned in the Team 4 report, not external publication numbers. C1 identifies course materials. A citation such as E08 lines 113–114 means those numbered lines in the original newline-delimited JSON log, not report pages.

Repository inventory checked on 11 November 2026 at commit 60d3899c2c8fcc9d604a0ff9520c0b598399628b. Presence does not independently verify every statement about file contents.

| ID | Source or repository location | Availability |
|---|---|---|
| C1 | Project card and updated course handbook | Course reference; not found in repository inventory |
| E01 | EXSU620 midterm_digital prototype (2).pdf | Team evidence notes; original not found |
| E02 | Earlier report drafts | Historical drafts; exact originals not found |
| E03 | [Pico firmware](../firmware/main.py) | Present |
| E04 | [Weekly calibration script](../firmware/calibrate_bench_weekly.py) | Present |
| E05 | bench-59daedbc.json calibration capture | [Calibration capture](../verification/calibration/bench-59daedbc.json) available |
| E06 | [v10 four samples](../database/browser-monitor/f938dda46ad0448fa5716778f8c7e2d6.jsonl) | Present |
| E07 | [v10 PH10 and receipt](../database/browser-monitor/5646b799eca54f1b93d25eafff738e7e.jsonl) | Present |
| E08 | [v9 run b6744](../database/browser-monitor/b6744ffff6cd4e06a51f3b01eb4a4199.jsonl) | Present |
| E09 | [v9 run dc68](../database/browser-monitor/dc68b79b79c84d1ba807cb82729ceba9.jsonl) | Present |
| E10 | [Earlier browser run](../database/browser-monitor/b25cf7effd82488bb293fd6208c46634.jsonl) | Present |
| E11 | [Historical T28 log](../verification/raw_logs/f93b67133c1045aa9210c638fde8c07c.jsonl) and bench-18f0c71b archive | Log present |
| E12 | sample_label_correction_cal95.json and associated run | Exact correction sidecar not found |
| E13 | [Browser monitor service and interface](../software/browser_monitor/) | Present |
| E14 | [Verification tests](../verification/tests/) | Present; distinguish old checks from current-version checks |
| E15 | [Trial index](../verification/trial_index.csv), [source manifest](../verification/source_manifest.json), [calibration audit](../verification/calibration_audit.json) | Present |
| E16 | [Official Pico 2 W datasheet](https://datasheets.raspberrypi.com/picow/pico-2-w-datasheet.pdf) | External manufacturer reference |
| E17 | [Assembly photo](../hardware/assembly_overview.png) and [close-up](../hardware/pico_shield_closeup.png) | Present; earlier assembly photos |
| E18 | ER1_User_Supplied_Comparisons.json | Selected-field transcription not found; underlying run [20fda](../database/browser-monitor/20fda0d966d2425ea3a0105a0911b8c1.jsonl) present |
| E19 | Added video evidence of interface lights sound ACK.mp4 | Two original recordings available in database folder  |
| E20 | Retrospective stop/history index | Exact derived index not found; underlying logs present |
| E21 | evidence for ack turning off the alarm.mp4 | Two original recordings available in database folder |
| E22 | evidence for connection lost.jpeg | Original image available in database folder |
| E23 | [Notification module](../software/browser_monitor/phone_notifications.py), [service](../software/browser_monitor/service.py), [message tests](../verification/tests/test_notification_messages.py), [service tests](../verification/tests/test_service.py) | Present |

## Demonstration evidence
The report describes green/normal indication, red/critical indication with a ten-tone pattern near 1200 Hz, physical ACK/STOP followed by ring OFF and audio cessation, and a disconnected display withholding pH. The two original video files are available below. The exact correspondence between their export filenames and E19 or E21 remains unverified. The original E22 screenshot is still unavailable.

- [WhatsApp Video 2026-11-10 at 7.16.42 PM.mp4](../verification/media/WhatsApp%20Video%202026-11-10%20at%207.16.42%20PM.mp4)
- [WhatsApp Video 2026-11-10 at 7.30.54 PM.mp4](../verification/media/WhatsApp%20Video%202026-11-10%20at%207.30.54%20PM.mp4)

## Updated team hardware notes
The team reports a PLA enclosure printed at 15% infill with splash guards around openings; ingress resistance and mechanical strength are not quantified. The Pico 2 W connects through a Seeed Studio Grove Shield. Laptop audio replaces the PAM8302A path after a reported short circuit during soldering. The team reports resolving unstable readings by replacing the Pico and attributes the problem to its cable connection point; the precise contact defect was not independently isolated.
