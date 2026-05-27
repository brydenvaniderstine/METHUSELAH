// METHUSELAH // ESP32S3 BLE BRIDGE // CONFIG
// Board: Seeed Studio XIAO ESP32S3
// Do not modify without updating firmware spec

#pragma once

// ── Device Identity ────────────────────────────────────────────────────────
#define DEVICE_NAME         "METHUSELAH"

// ── BLE UUIDs ──────────────────────────────────────────────────────────────
// Glucose Service (IEEE 11073 standard)
#define SERVICE_UUID        "00001808-0000-1000-8000-00805f9b34fb"
#define CHARACTERISTIC_UUID "00002a18-0000-1000-8000-00805f9b34fb"

// ── Hardware ───────────────────────────────────────────────────────────────
// XIAO ESP32S3 onboard LED
#define LED_PIN             21

// ── Serial ─────────────────────────────────────────────────────────────────
#define SERIAL_BAUD         115200

// ── Thresholds ─────────────────────────────────────────────────────────────
// Locked per METHUSELAH Build Guidelines
#define THRESHOLD_GLUCOSE   5.8f   // mmol/L — above → 24-hour water fast
#define THRESHOLD_HRV       40.0f  // ms     — below → 45-min Zone 2
#define THRESHOLD_LACTATE   2.0f   // mmol/L — above → active recovery

// ── Broadcast Format ───────────────────────────────────────────────────────
// CSV string: glucose,hrv,lactate
// Example: "5.4,45,1.1"
