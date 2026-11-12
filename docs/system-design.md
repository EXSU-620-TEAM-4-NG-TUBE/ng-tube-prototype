# System design

## II. System architecture (Deliverable D2)

The sensing chain consists of a glass pH electrode, BNC connection and pH meter V1.1 conditioning board. The board converts the electrode response into an analogue signal read at GP26 on the Pico 2 W through the Grove shield. The Pico also controls the 16-pixel ring on GP15 and reads an active-low button on GP14. [E03, E17]

Figure 1. Implemented functional architecture. The Pico performs measurement checks. The Windows service owns serial communication, audit writes and audio. The browser is an interface to that service. Remote notification is a separate internet-dependent path. [E03, E13]

The Pico uses MicroPython rather than the CircuitPython runtime suggested in the project card. It transmits newline-delimited JSON over USB. Its wireless capability is not used for measurement transport. The service exposes a local HTTP interface at 127.0.0.1:8765 and supplies a browser display with a trace, result, calibration details and recent events.

USB provides both power and communication in the documented arrangement. Laptop audio replaces the separate PAM8302 amplifier and speaker following overheating during assembly. The failed amplifier is not counted as a working subsystem. [E01, E02]

The architecture is dependent on a functioning laptop and service. Local logging and display do not require internet, but phone messages do. The prototype has not demonstrated independent audible warning when the laptop loses power or the service stops.

### Calibration and measurement processing

The calibration script asks for nominal pH 4.00 and 7.00 liquids. It waits 60 seconds after each operator confirmation and then acquires 30 readings at one-second intervals. It rejects raw readings at or beyond 100 and 65435, separation of 500 counts or less, reversed order, or a capture spread greater than 0.95 estimated pH. It saves both complete captures, their means, operator initials, an identifier and provisional reference status. [E04]

The conversion is:

pH estimate = 4.00 + 3.00 × (raw − R4) / (R7 − R4)

R4 and R7 are the saved mean raw readings. The final archive bench-59daedbc contains stored means 31220.868 and 38102.332. Recomputed means differ by only about 0.0013 counts. Its estimated-pH spreads are 0.06278 and 0.04883, both below the configured 0.95 capture criterion. This describes within-capture variation, not independent accuracy. [E05]

| Stage | Latest implementation |
| --- | --- |
| Start | NEW_SAMPLE clears the preceding capture, filter, stability and result; duplicate delivery of the same ID does not restart it. |
| Acquire | One raw reading in each scheduled second 1-20, with a 250 ms acquisition tolerance. |
| Filter | Three-reading moving average of converted pH values. |
| Settle | Latest ten unfiltered values have range ≤0.35 pH for a ten-second dwell. |
| Evaluate | At 21 s, check calibration, completeness, signal range, pH validity, mode-specific response or drift, and settling. |
| Hold | Freeze a valid completed result; continue status and button handling without new ADC acquisition. |

The routine result is the three-reading average at second 20, using readings 18–20, classified before rounding. A steady value alone cannot identify a stuck sensor because two unknown samples may have similar pH. We therefore use a separate known-buffer response check: the operator records the previous sample baseline, moves the probe to a buffer with a known different pH and explicitly starts the response check. If the filtered signal remains within ±0.10 pH of the baseline throughout the specified observation interval, the software reports STUCK_FAILURE. A meaningful response that also meets the settling rule returns PROBE_RESPONSE_DETECTED, not a feeding verdict. Routine samples are not assessed for stuck behaviour. [E03]

The calibration archive has no completion timestamp. Runtime log E08 records an operator-entered completion time of 10 November 2026 at 14:35 UTC for the same calibration ID. The registration is located in records 113–114 of the original E08 JSONL file; these are log line numbers, not report pages. The time is operator supplied rather than an independently timestamped capture. [E05, E08]

### Alarms and operator interaction

The browser starts in Ready. During measurement it withholds the main pH and verdict while counting down. A completed result is held; a failed capture displays its technical reason. Raw information, calibration metadata, history and response-check controls are available under More info. [E13]

| State | Current ring | Programmed laptop pattern |
| --- | --- | --- |
| NORMAL | Green | Silent. |
| ADVISORY | Amber | Three 800 Hz tones, 150 ms each. |
| CRITICAL | Red | Ten 1200 Hz tones, 150 ms each. |
| TECHNICAL | Cyan | One 1500 Hz tone, 100 ms. |
| Measuring | Dim white | Muted. |
| Physically stopped | OFF | Muted. |
| Host reconnecting | No confirmed host control of ring | Muted in the latest browser service. |

The light-ring and alarm operation was recorded in demonstration videos. With pH above 6.0, the monitor shows Critical, the ring turns red and ten bursts near 1200 Hz support the selected alarm pattern. The audio alarm ceases when the physical ACK/STOP button is pressed. The two recordings are identified as E19 (light and alarm demonstration) and E21 (ACK/STOP demonstration). [E19, E21]

Project evidence location: Team 4 GitHub repository

An on-screen acknowledgement mutes audio for 120 seconds. The physical button generates an ACK event and stops the Pico sample. The Pico repeatedly sends OFF to the ring after stopping. The host removes the current measurement from its main result while retaining the last measurement in the audit. Starting again requires pressing NEW SAMPLE.

The host’s critical latch is a separate memory. It remains until an acknowledgement has occurred and a valid normal reading returns. The current browser panel and ring may nevertheless show a newer advisory sample, or turn off after stopping. This was introduced to avoid displaying an old critical category as the current sample’s result. It also means the ring is not a continuously latched critical indicator. [E03, E13]

After communication loss, the service clears the current sample gate, withholds the host verdict and mutes sound. The browser monitor states “Pico not connected”, a blank pH, paused timer and “Connection lost - reconnect USB”. [E22] It cannot prove the ring’s physical state if the Pico remains powered independently. Closing the browser tab does not stop the service. Restarting the service creates a new session and does not reconstruct critical latch or consent state from historical storage.

### Audit model and design alternatives

Each saved event contains received_utc, run_id, operator, sample label, kind and payload. Measurement payloads include sample_id, device elapsed time, pH, raw ADC, calibration ID, validity, state and quality-check information. Device time and host reception time are different clocks and are not interchangeable latency measurements. [E13]

SQLite stores events in one table. A separate JSONL file retains each service run. The service writes and flushes JSONL before inserting and committing SQLite. These writes are not one transaction across both stores. The current snapshots reconcile, but an interrupted write can leave them inconsistent. There is no demonstrated automatic reconciliation or durable replay of the in-memory alarm and recipient state.

The browser shows recent events rather than a complete persistent audit browser. Historical data remain accessible in SQLite and JSONL. An earlier label correction is preserved in a separate sidecar file without altering the original records; it is not an implemented label-editing API. [E12, E13, E15]

| Choice | Rationale and remaining trade-off |
| --- | --- |
| MicroPython | Retained the working Thonny environment and machine ADC interface. The runtime substitution is declared. |
| Browser and local REST service | Replaced the earlier Tkinter interface and supports the course’s browser/service architecture. The backend uses Python’s standard HTTP server, rather than FastAPI or Flask. |
| Laptop audio | Avoided reusing the failed amplifier. It introduces dependence on Windows, the service and laptop speakers. |
| ntfy Android messages | Provides a demonstrable phone path. It substitutes for the suggested WhatsApp options; specific approval of this substitution is not documented. |
| Held completed results | Prevents later probe movement from changing a completed sample. A new measurement must be explicitly requested. |
| Dedicated response challenge | Avoids misclassifying similar unknown samples as a stuck probe. It depends on the operator actually transferring between known buffers. |

The revised service offers notifications for completed Normal, Advisory, Critical and Technical results. Technical messages identify why a verdict was withheld. Consent is logged before queueing. The public ntfy topic is accessible to subscribers, so messages contain bench sample information only. [E23]

## III. Component, module and interface (Deliverable D3)

### Component and module table

| Module | Components and role |
| --- | --- |
| Sensing | Glass probe, BNC lead and pH meter V1.1 board condition the liquid response. |
| Control | Pico 2 W, Grove shield and MicroPython perform timed acquisition and quality gating. |
| Local interaction | Sixteen-pixel ring and momentary button provide visual status and physical stop. |
| Mechanical | Printed case, lid, probe holder and sample-cup position organize the assembly. |
| Host | Windows laptop, Python service, browser, SQLite and JSONL provide interface, audio and audit. |
| Remote | ntfy service and an opted-in Android phone provide optional notification. |

### Interfaces

| Interface and direction | Signal and range or constraint |
| --- | --- |
| USB → Pico and shield | Nominal 5 V power plus serial communication. Team meter observations were approximately 5.1 V. |
| Shield supply → sensor + and ring V+ | Nominal 5 V supply; common ground. Actual harness continuity is not established solely by code. |
| Sensor A → GP26 through A0 | Nominal ADC domain 0-3.3 V; read_u16 returns 0-65535 counts. Software gate 500-60000 inclusive. Direct wiring has no documented overvoltage protection. [E16] |
| GP15 → ring DIN | Pixel data at nominal 3.3 V GPIO levels; sixteen RGB pixels. Ring supply is 5 V; level compatibility has not been physically qualified. [E16] |
| Button → GP14 and GND | Active-low 3.3 V input with internal pull-up; pressed to GND; 30 ms debounce. [E16] |
| Pico ↔ laptop | Newline-delimited JSON measurements and commands; host opens the port at 115200. |
| Browser ↔ service | Local HTTP JSON at port 8765; POST requests use a per-process request token. |
| Service → storage | Append JSONL and commit SQLite event records. |
| Service → ntfy → phone | Internet-dependent HTTPS messaging; delivery confirmation is a separate operator action. |

The hardware uses a Raspberry Pi Pico 2 W connected through a Seeed Studio Grove Shield to the analogue pH board and 16-pixel NeoPixel ring. The final blue enclosure, lid-mounted ring, button and probe support organize the assembly and sample handling. The team reports PLA printing at 15% infill. This is a demonstration enclosure; production mechanical strength has not been established. Splash guards surround the openings to reduce exposure to water or aspirate spills, but no water-resistance rating is claimed.

The speaker is connected to the laptop rather than the Pico amplifier path. The team reports a PAM8302A short circuit during soldering, after which laptop-driven audio was used. The amplifier is excluded from the final working system. Earlier assembly photographs are available in the repository hardware folder; the cited videos document the enclosed final appearance. [E17, E19, E21]

Hardware photographs: GitHub hardware folder

Source [Final report PDF](EXSU620_Team4_Final_Report.pdf).
