import type { CapacitorConfig } from '@capacitor/cli';

const liveReloadUrl = process.env.CAP_SERVER_URL;

const config: CapacitorConfig = {
  appId: 'at.taxja.app',
  appName: 'Taxja',
  webDir: 'dist',
  bundledWebRuntime: false,
  backgroundColor: '#f2f8fd',
  server: liveReloadUrl
    ? {
        url: liveReloadUrl,
        cleartext: true,
      }
    : undefined,
  plugins: {
    StatusBar: {
      overlaysWebView: false,
      style: 'DARK',
      backgroundColor: '#f2f8fd',
    },
  },
};

export default config;
