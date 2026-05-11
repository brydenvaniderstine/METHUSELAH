import { BleClient } from '@capacitor-community/bluetooth-le';

const SERVICE        = '00001808-0000-1000-8000-00805f9b34fb';
const CHARACTERISTIC = '00002a18-0000-1000-8000-00805f9b34fb';
const RACP           = '00002a52-0000-1000-8000-00805f9b34fb';
const NAME_PREFIX    = 'meter+';

const isNative = () => !!(window.Capacitor?.isNativePlatform?.());

/**
 * connectRoche — routes to native CoreBluetooth (iOS) or Web Bluetooth (desktop).
 *
 * Callbacks:
 *   onData(DataView)       — raw characteristic value; caller owns SFLOAT decode
 *   onLog(msg, type)       — log line forwarded to sys-log
 *   onStatus(string)       — BLE status string (SCANNING / CONNECTING / ROCHE_LIVE / DISCONNECTED)
 *   onDevice(string)       — human-readable device name on successful connect
 *   onDisconnect()         — called on unexpected disconnect
 */
export async function connectRoche({ onData, onLog, onStatus, onDevice, onDisconnect }) {
  return isNative()
    ? connectNative({ onData, onLog, onStatus, onDevice, onDisconnect })
    : connectWebBT({ onData, onLog, onStatus, onDevice, onDisconnect });
}

// ── NATIVE PATH (Capacitor / iOS CoreBluetooth) ──────────────────────────────
// CoreBluetooth reuses the OS-level LTK established by mySugr.
// No re-pairing ceremony — bond is shared at the OS bond table level.

async function connectNative({ onData, onLog, onStatus, onDevice, onDisconnect }) {
  onStatus('SCANNING...');
  onLog('INITIATING ROCHE HANDSHAKE // NATIVE CORE-BT', 'event');

  await BleClient.initialize();

  const device = await BleClient.requestDevice({
    services: [SERVICE],
    namePrefix: NAME_PREFIX,
  });

  onStatus('CONNECTING...');

  await BleClient.connect(device.deviceId, () => {
    onStatus('DISCONNECTED');
    onDisconnect();
    onLog('ROCHE NODE DISCONNECTED // REVERTING TO SIMULATION', 'event');
  });

  try {
    await BleClient.startNotifications(
      device.deviceId, SERVICE, CHARACTERISTIC,
      (value) => onData(value)
    );

    onLog('NOTIFICATION CHANNEL OPEN // AWAITING RACP TRIGGER', 'event');

    // Subscribe to RACP response notifications before triggering
    await BleClient.startNotifications(device.deviceId, SERVICE, RACP, () => {});

    // RACP opcode 0x01 operator 0x01 — "Report All Stored Records"
    const racpCmd = new DataView(new Uint8Array([0x01, 0x01]).buffer);
    await BleClient.write(device.deviceId, SERVICE, RACP, racpCmd);

    onStatus('ROCHE_LIVE');
    onDevice(device.name ?? device.deviceId);
    onLog(`RACP TRIGGERED // VAULT OPEN // ${device.name ?? device.deviceId}`, 'event');

  } catch (err) {
    await BleClient.disconnect(device.deviceId).catch(() => {});
    throw err;
  }
}

// ── WEB BLUETOOTH PATH (desktop / Chrome fallback) ───────────────────────────

async function connectWebBT({ onData, onLog, onStatus, onDevice, onDisconnect }) {
  onStatus('SCANNING...');
  onLog('INITIATING ROCHE HANDSHAKE // WEB BT', 'event');

  const device = await navigator.bluetooth.requestDevice({
    filters: [{ namePrefix: NAME_PREFIX }],
    optionalServices: [SERVICE],
  });

  device.addEventListener('gattserverdisconnected', () => {
    onStatus('DISCONNECTED');
    onDisconnect();
    onLog('ROCHE NODE DISCONNECTED // REVERTING TO SIMULATION', 'event');
  });

  onStatus('CONNECTING...');
  const server = await device.gatt.connect();

  let service, char, racpChar;
  try {
    service   = await server.getPrimaryService(SERVICE);
    char      = await service.getCharacteristic(CHARACTERISTIC);
    racpChar  = await service.getCharacteristic(RACP);
  } catch {
    throw new Error('UUID_MISMATCH: Glucose service not found on device.');
  }

  await char.startNotifications();
  onLog('NOTIFICATION CHANNEL OPEN // AWAITING RACP TRIGGER', 'event');
  await racpChar.startNotifications();

  char.addEventListener('characteristicvaluechanged', (e) => onData(e.target.value));

  await racpChar.writeValueWithResponse(new Uint8Array([0x01, 0x01]));

  onStatus('ROCHE_LIVE');
  onDevice(device.name);
  onLog(`RACP TRIGGERED // VAULT OPEN // ${device.name}`, 'event');
}
