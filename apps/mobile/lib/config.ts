import { Platform } from 'react-native';

const _envUrl = process.env.EXPO_PUBLIC_API_URL ?? 'https://api.reilabs.ai';

// Android emulator cannot reach `localhost` — it needs the special alias 10.0.2.2.
// iOS simulator uses regular localhost. Swap automatically so a single .env.local works for both.
export const API_BASE_URL = (__DEV__ && Platform.OS === 'android' && _envUrl.includes('localhost'))
  ? _envUrl.replace('localhost', '10.0.2.2')
  : _envUrl;
export const DEEP_LINK_SCHEME = 'ari';
export const DEEP_LINK_VERIFY_PATH = `${DEEP_LINK_SCHEME}://verify`;

// Universal Link / App Link redirect URI — used when a Universal Link build is active.
// Falls back to the custom ari:// scheme in development / Expo Go.
export const APP_DOMAIN = 'https://reilabs.ai';
export const UNIVERSAL_VERIFY_PATH = `${APP_DOMAIN}/auth/verify`;
