# firmware/

XIAO ESP32S3 BLE bridge — PlatformIO project.

## Purpose
Embedded firmware for the hardware BLE bridge. Connects to the Oura Gen3 ring via BLE,
dumps the event buffer, and forwards packets over USB serial or WiFi to the pipeline.

## Structure
- `platformio.ini` — PlatformIO project config (board, framework, dependencies)
- `config.h` — hardware pin assignments, BLE UUIDs, connection parameters
- `src/main.ino` — main firmware loop

## Import rules
- `firmware/` is an isolated embedded project. Nothing imports from it.
- No web, engine, pipeline, or parser code belongs here.
- BLE protocol constants (UUIDs, characteristic handles) are documented in
  `../pipeline/data/findings/known_issues.md` and may be referenced here, but
  the findings docs are the authoritative source — not this firmware.
