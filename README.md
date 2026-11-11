# NG Tube pH Verification Prototype

**McGill University | EXSU 620 – Surgical Innovation | Project 04 | Team 4**

## Project Overview

This project presents an educational bench prototype designed to measure the pH of liquid samples and demonstrate a nasogastric tube verification workflow.

The system uses a Raspberry Pi Pico 2 W, a pH sensor, an LED ring, a physical stop button, and a Windows-based browser monitoring interface.

**This prototype is for educational bench testing only and is not validated for clinical use.**

## Main Features

- pH measurement using an analogue sensor
- Timed measurement and stability checks
- pH classification into normal, advisory, and critical categories
- LED indicators and laptop audio alerts
- Physical stop button
- Browser-based monitoring dashboard
- Measurement logging using SQLite and JSONL
- Optional Android notifications

## Repository Structure

| Folder | Contents |
|---|---|
| `firmware/` | Raspberry Pi Pico firmware and calibration scripts |
| `laptop/` | Browser monitor, Windows launcher, and alternative monitoring script |
| `database/` | SQLite database |
| `hardware/` | Prototype photographs and wiring diagrams |
| `tests/` | Software verification scripts |
| `verification/` | Raw logs, calibration evidence, and verification records |
| `docs/` | Final project report |

## System Operation

1. Connect the Pico and pH sensor to the Windows laptop.
2. Load the firmware and confirm the calibration.
3. Start the browser monitoring service.
4. Enter the operator initials and sample information.
5. Place the probe in the test liquid and select **NEW SAMPLE**.
6. Wait for the measurement and quality checks to finish.
7. Review the displayed result and save the measurement record.
8. Use the physical stop button to stop the current sample.

## Verification

The project includes software tests, calibration records, measurement logs, and hardware demonstrations.

The final report describes the completed tests, observed results, and remaining limitations.

## Documentation

See the `docs/` folder for the final EXSU 620 project report.

## Team

Sophia Lee, Seoyoung Park, Muhammad Bey Ali, Saada Hussein, and Kayla Giampa.
