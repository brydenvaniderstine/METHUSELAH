import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.methuselah.app',
  appName: 'METHUSELAH',
  webDir: 'build',
  plugins: {
    BluetoothLe: {
      displayStrings: {
        scanning: 'SCANNING...',
        cancel: 'ABORT',
        availableDevices: 'DETECTED NODES',
        noDeviceFound: 'NO NODES FOUND',
      },
    },
  },
};

export default config;
