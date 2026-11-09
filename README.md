# EXSU 620 – NG Tube pH Verification Prototype

## Project Overview

This project was developed for EXSU 620 – Digital Prototyping at McGill University.

The objective is to design and evaluate a digital prototype that measures the pH of simulated nasogastric (NG) tube aspirate to support the assessment of tube placement.

The system uses a Raspberry Pi Pico 2 W connected to a pH sensor, a NeoPixel LED ring, a physical button, and laptop-based monitoring software.

**Important:** This is an educational, bench-top prototype only. It is not validated or approved for clinical use. Its readings must not be used to determine actual NG tube placement or feeding safety.

## Hardware Components

- Raspberry Pi Pico 2 W
- Analog pH sensor and electrode
- NeoPixel LED ring
- Physical push button
- Grove expansion shield and connecting wires
- 3D-printed electronics enclosure
- Laptop for monitoring and data recording

## System Functionality

The prototype is designed to:

1. Measure pH using an analog sensor.
2. Convert the sensor voltage into an estimated pH value using calibration coefficients.
3. Evaluate measurement stability before displaying a result.
4. Categorize measurements according to predefined pH thresholds.
5. Display status using LED indicators and laptop-based monitoring.
6. Provide audible alerts and phone notifications where implemented.
7. Record test results and calibration information.

## Prototype Decision Thresholds

| Measured pH | Prototype category |
|---|---|
| ≤ 5.5 | Gastric-range pH |
| > 5.5 to 6.0 | Advisory / Escalate |
| > 6.0 | Critical / Do Not Feed |
| Invalid or unstable | Technical failure / Repeat |

These categories are part of the prototype's experimental logic and do not independently establish NG tube placement.

## Repository Structure

- `firmware/` — MicroPython firmware and calibration scripts.
- `laptop/` — Laptop monitor, phone notifications, launcher, and software dependencies.
- `database/` — Database schema and example records.
- `hardware/` — Wiring diagrams, component information, assembly photographs, and CAD files.
- `tests/` — Software tests and test instructions.
- `verification/` — Experimental results, calibration records, logs, and verification evidence.
- `docs/` — Engineering requirements, diagrams, risk analysis, traceability matrix, and final dossier.

## Calibration and Testing

The prototype uses reference pH buffer solutions for calibration and verification.

The project includes evaluation of:

- Calibration accuracy and repeatability
- Sensor settling time and measurement drift
- Decision thresholds
- LED and audio alerts
- Button acknowledgement
- Sensor and communication failures
- Data recording and notification functionality

Detailed procedures, results, and outstanding tests are documented in `verification/`.

## Software Setup

The Pico firmware uses MicroPython, while the laptop monitoring software uses Python.

The final firmware, software dependencies, configuration instructions, and operating procedures will be provided in their respective repository folders.

## Limitations

- The prototype has been evaluated using laboratory buffer solutions rather than patient samples.
- Sensor calibration and stability may vary over time.
- Some fault-detection and verification procedures require further testing.
- The system requires additional validation before any clinical application.

## Team

EXSU 620 – Team 4

McGill University

## Disclaimer

**For educational and research demonstration purposes only. Not a medical device. Not for clinical decision-making or patient use.**
