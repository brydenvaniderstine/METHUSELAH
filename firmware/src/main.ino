// METHUSELAH // ESP32S3 BLE BRIDGE FIRMWARE
// Board: Seeed Studio XIAO ESP32S3
// Library: NimBLE-Arduino
// Service UUID: 00001808-0000-1000-8000-00805f9b34fb (Glucose Service)
// Characteristic UUID: 00002a18-0000-1000-8000-00805f9b34fb
// Broadcast format: glucose,hrv,lactate (e.g. "5.4,45,1.1")
// Serial input at 115200 baud
// LED blinks on BLE connect

#include <NimBLEDevice.h>

// ── UUIDs ──────────────────────────────────────────────────────────────────
#define SERVICE_UUID        "00001808-0000-1000-8000-00805f9b34fb"
#define CHARACTERISTIC_UUID "00002a18-0000-1000-8000-00805f9b34fb"
#define DEVICE_NAME         "METHUSELAH"

// ── LED ────────────────────────────────────────────────────────────────────
// XIAO ESP32S3 onboard LED is GPIO 21
#define LED_PIN 21

// ── Globals ────────────────────────────────────────────────────────────────
NimBLEServer*         pServer         = nullptr;
NimBLECharacteristic* pCharacteristic = nullptr;
bool                  deviceConnected = false;
String                bioPayload      = "0.0,0,0.0"; // default safe state

// ── Connection Callbacks ───────────────────────────────────────────────────
class ServerCallbacks : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer* pSvr) override {
    deviceConnected = true;
    Serial.println("[BLE] CLIENT CONNECTED");
  }

  void onDisconnect(NimBLEServer* pSvr) override {
    deviceConnected = false;
    Serial.println("[BLE] CLIENT DISCONNECTED — RESTARTING ADVERTISING");
    NimBLEDevice::startAdvertising();
  }
};

// ── Helpers ────────────────────────────────────────────────────────────────
void blinkLED(int times, int delayMs) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(delayMs);
    digitalWrite(LED_PIN, LOW);
    delay(delayMs);
  }
}

bool isValidPayload(const String& s) {
  // Expect exactly two commas: "float,int,float"
  int first  = s.indexOf(',');
  int second = s.indexOf(',', first + 1);
  return (first > 0 && second > first && second < (int)s.length() - 1);
}

// ── Setup ──────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.println();
  Serial.println("██ METHUSELAH ESP32S3 BLE BRIDGE ██");
  Serial.println("Initializing NimBLE stack...");

  // Init BLE
  NimBLEDevice::init(DEVICE_NAME);
  NimBLEDevice::setPower(ESP_PWR_LVL_P9); // max TX power

  // Server
  pServer = NimBLEDevice::createServer();
  pServer->setCallbacks(new ServerCallbacks());

  // Service
  NimBLEService* pService = pServer->createService(SERVICE_UUID);

  // Characteristic — READ + NOTIFY
  pCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_UUID,
    NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY
  );
  pCharacteristic->setValue(bioPayload.c_str());

  // Start service
  pService->start();

  // Advertising
  NimBLEAdvertising* pAdvertising = NimBLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  NimBLEDevice::startAdvertising();

  Serial.println("[BLE] Advertising as: " DEVICE_NAME);
  Serial.println("[SERIAL] Waiting for input: glucose,hrv,lactate");
  Serial.println("Example: 5.4,45,1.1");

  blinkLED(3, 150); // boot blink
}

// ── Loop ───────────────────────────────────────────────────────────────────
void loop() {
  // Read serial input
  if (Serial.available()) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim();

    if (incoming.length() > 0) {
      if (isValidPayload(incoming)) {
        bioPayload = incoming;
        pCharacteristic->setValue(bioPayload.c_str());

        Serial.print("[DATA] Payload accepted: ");
        Serial.println(bioPayload);

        // Notify connected client
        if (deviceConnected) {
          pCharacteristic->notify();
          Serial.println("[BLE] Notified client.");
        }

        // ── METHUSELAH Logic Thresholds ──────────────────────────────────
        float glucose = bioPayload.substring(0, bioPayload.indexOf(',')).toFloat();
        int   comma1  = bioPayload.indexOf(',');
        int   comma2  = bioPayload.indexOf(',', comma1 + 1);
        float hrv     = bioPayload.substring(comma1 + 1, comma2).toFloat();
        float lactate = bioPayload.substring(comma2 + 1).toFloat();

        Serial.println("── THRESHOLD ANALYSIS ─────────────────");
        if (glucose > 5.8) {
          Serial.println("⚡ GLUCOSE > 5.8 → INITIATE 24-HOUR WATER FAST");
        }
        if (hrv < 40.0) {
          Serial.println("⚡ HRV < 40ms → EXECUTE 45-MIN ZONE 2 OUTPUT");
        }
        if (lactate > 2.0) {
          Serial.println("⚡ LACTATE > 2.0 → INITIATE ACTIVE RECOVERY PROTOCOL");
        }
        Serial.println("───────────────────────────────────────");

      } else {
        Serial.print("[ERROR] Invalid format. Expected glucose,hrv,lactate. Got: ");
        Serial.println(incoming);
      }
    }
  }

  // Blink LED when connected
  if (deviceConnected) {
    digitalWrite(LED_PIN, HIGH);
    delay(50);
    digitalWrite(LED_PIN, LOW);
    delay(950); // slow heartbeat blink = connected
  }

  delay(10);
}
