# firmware/

XIAO ESP32S3 BLE bridge — PlatformIO project.

## Purpose
Embedded firmware for the hardware BLE bridge. Connects to the Oura Gen3 ring via BLE,
dumps the event buffer, and forwards packets over USB serial or WiFi to `pipeline/tools/`.

## Files
- `platformio.ini` — board, framework, library dependencies
- `config.h` — BLE UUIDs, connection parameters, pin assignments
- `src/main.ino` — main firmware loop

## Import rules
`firmware/` is an isolated embedded project. Nothing imports from it.
No web, engine, pipeline, or parser code belongs here.

## Removability
This directory can be removed without breaking any other layer. `pipeline/tools/` scripts
connect to the ring via macOS CoreBluetooth and do not depend on this firmware. The XIAO
bridge is an optional hardware path — the Python pull scripts are the primary path.

If a second sensor is added (e.g. XIAO for GSR), add a subdirectory here for its firmware.
Nothing in `pipeline/`, `engine/`, `parsers/`, or `web/` needs to change at the firmware
level — only a new decoder in `pipeline/decoders/` and a new vector in `engine/`.

## Adding a new sensor
1. Add firmware here (new subdirectory or new file in `src/`).
2. Add a decoder in `pipeline/decoders/`.
3. Add the vector to `engine/`.
4. `web/` reads the new value from `engine/`. No structural change required.
