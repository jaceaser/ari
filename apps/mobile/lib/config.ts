export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'https://api.reilabs.ai';
export const DEEP_LINK_SCHEME = 'ari';
export const DEEP_LINK_VERIFY_PATH = `${DEEP_LINK_SCHEME}://verify`;

// Universal Link / App Link redirect URI — used when a Universal Link build is active.
// Falls back to the custom ari:// scheme in development / Expo Go.
export const APP_DOMAIN = 'https://reilabs.ai';
export const UNIVERSAL_VERIFY_PATH = `${APP_DOMAIN}/auth/verify`;
