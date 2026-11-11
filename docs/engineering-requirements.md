# Engineering requirements

## D1 Clinical need and requirements

### Need statement and intended scope

A way to reduce uncertainty during nasogastric tube placement checks in patients requiring enteral feeding in order to support timely, appropriate feeding decisions.

The course project asks for a numerical pH measurement, explicit decision categories, refusal when the measurement cannot be trusted, and a retrievable record. Our prototype explores this workflow using bench liquids. No patient samples, tube-location ground truth or clinical outcomes are included. The intended benefit of reduced uncertainty has therefore not been measured in clinical practice. [C1]

| Clinical requirement | Course meaning |
| --- | --- |
| CR1 | The pH of a nasogastric aspirate shall be measured and displayed to one decimal place, with a clear indication of when the reading has settled. |
| CR2 | The device shall state a verdict against the accepted rule: at or below pH 5.5 gastric, 5.6 to 6.0 escalate, above 6.0 do not feed. |
| CR3 | The device shall refuse to give a verdict when its calibration is older than the configured interval, or when the electrode is drifting or unresponsive. |
| CR4 | Every test shall be recorded with the value, the verdict, the operator and the calibration state, and shall be retrievable for audit. |

The following eight engineering requirements retain the draft’s numerical targets and identify the latest implemented settings. These requirements reflect our final design, including changes we made during development. Not all of them were established before testing began. Requirements are assessed separately from whether an individual run completed. [E01-E04]

| ID and trace | Requirement and acceptance criterion |
| --- | --- |
| ER1 • CR1 | Estimate pH over the proposed nominal range 4.00-10.01 and display one decimal. Every independent reference check must be within ±0.30 pH, with reference identity, temperature and uncertainty documented. A display or a two-point fit alone does not pass accuracy. |
| ER2 • CR1 CR3 | Acquire readings at seconds 1-20 after accepted sample start, each within 250 ms of schedule. Publish no verdict before 21.000 s and one outcome by 21.250 s on the device clock. A valid outcome also requires a ten-reading pH range ≤0.35 maintained for a ten-second dwell. |

The evaluated nominal range is broader than the 4-7 calibration interval. Values above pH 7 are extrapolated. ER1 is a target to be verified, not an established continuous operating range. ER2 measures software acquisition and publication timing; it does not guarantee electrode equilibrium within 20 seconds.

### D1 Decision and alarm requirements

| ID and trace | Requirement and acceptance criterion |
| --- | --- |
| ER3 • CR2 | Apply categories to the unrounded final filtered estimate. pH ≤5.5 is NORMAL; 5.5 < pH ≤6.0 is ADVISORY; pH >6.0 is CRITICAL. Values immediately below, at and above both boundaries must classify correctly. Invalid measurements must not produce a verdict. |
| ER4 • CR3 | Before a verdict, reject incomplete or late captures, implausible input and the defined drift or response-check failure. Any raw value <500 or >60000, estimated pH outside 0-14, drift >0.40 pH, missing timed reading or failed known-buffer response check must produce a technical result with no verdict at the decision point. |
| ER5 • CR3 CR4 | Limit calibration use to 604800 seconds from recorded completion. A restart or new sample must not renew the interval. Missing clock, invalid coefficients, future completion time and the expiry boundary must withhold a new verdict. Physical accuracy throughout that interval requires separate verification. |
| ER6 • CR2 CR3 | Provide the specified normal, advisory, critical and technical indications; retain critical history until acknowledged and a valid normal returns. Normal is green and silent, advisory amber with three tones, critical red with ten, and technical cyan with one. The physical button must stop acquisition, mute sound through the host and command OFF. Current indication and retained critical history must be distinguishable. |

The signal limits in ER4 are provisional software settings. They are neither measured fault boundaries nor electrical protection. The evidence PDF refers to an older upper limit of 45000; the latest code uses 60000. A valid high-pH signal exceeded the older limit, demonstrating why a signal gate cannot itself identify the cause of a fault. [E01, E03, E08]

The drift rule compares the mean of readings 1-3 with readings 18-20. A difference exactly equal to 0.40 pH passes; a greater absolute difference fails in routine mode. This is a net-change test. It can respond to a jump and may miss changes that return to their initial level.

Stuck assessment is limited to a dedicated known-buffer response check. A three-reading moving average must remain within ±0.10 pH of the previous measured baseline throughout seconds 3-20 for at least 15 seconds to fail. The actual observation interval is approximately 17 seconds. Routine NEW SAMPLE measurements do not assess stuck behaviour. [E03]

ER6 uses a deliberate deviation from continuously latched red indication: the ring shows the current sample and physical STOP turns it off, while the host retains critical history. Approval of this latch deviation is not documented. The separately reported instructor approval for laptop audio does not establish approval of latch behaviour. Selected functions are demonstrated; remaining physical pattern coverage is stated in D7. [E19-E21]

### D1 Audit and notification requirements

| ID and trace | Requirement and acceptance criterion |
| --- | --- |
| ER7 • CR3 CR4 | Attribute each accepted NEW SAMPLE to a distinct sample ID, operator, label and calibration context. Reset its timer and acquisition history. After link loss or more than five seconds without a valid heartbeat, withhold the host’s current verdict. Reconnection must require a new sample. Corresponding JSONL and SQLite events must agree, and interruptions and label corrections must remain retrievable. |
| ER8 • CR2 CR4 | With prior consent, queue one message per eligible completed Normal, Advisory, Critical or Technical sample. Include the sample ID and outcome, with the reason for technical refusal. Match the provider message ID to an independently observed phone receipt. Idle, measuring and manually stopped cases shall produce no result message. |

### Acceptance rationale

The team chose a seven-day calibration policy to reduce repeated calibration work. It is not a manufacturer-validated lifetime established by this project. A stored timestamp permits age checking, while a longitudinal reference study is needed to justify the duration physically. No new sample, browser action or reboot should be described as recalibration.

The latest stability condition is a maximum-minus-minimum range of 0.35 pH across ten unfiltered readings, followed by a ten-second qualifying dwell. The evidence notes describe ±0.35 around a mean for 20 seconds; that is a different algorithm and is not used here. The calibration script’s separate 0.95 pH capture-spread limit is also not an accuracy tolerance. [E01, E03, E04]

Classification uses full internal precision before the packet is rounded. Consequently, the final recorded value 6.029 is critical even though the browser displays 6.0. This avoids silently rounding a value down across the decision boundary, but the display still needs to explain such cases to users. [E06]

Source [Team 4 final report](EXSU620_Team4_Final_Report.pdf).
