import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.methuselah.app',
  appName: 'METHUSELAH',
  webDir: 'build',
  ios: {
    contentInset: 'always',
    scrollEnabled: false,
  },
  server: {
    androidScheme: 'https'
  },
  plugins: {
    WebView: {
      allowsLinkPreview: false,
      allowsInlineMediaPlayback: true,
      mediaTypesRequiringUserActionForPlayback: 'none',
    }
  }
};

export default config;
