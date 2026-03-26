import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { NativeModules, Platform } from 'react-native';

import en from '../locales/en.json';
import es from '../locales/es.json';

// On iOS read from SettingsManager (same source react-native-localize uses).
// On Android fall back to Intl API which works reliably with Hermes.
function getDeviceLocale(): string {
  try {
    if (Platform.OS === 'ios') {
      const settings = NativeModules.SettingsManager?.settings;
      const lang: string | undefined =
        settings?.AppleLanguages?.[0] ?? settings?.AppleLocale;
      if (lang) return lang;
    }
    return Intl.DateTimeFormat().resolvedOptions().locale ?? 'en';
  } catch {
    return 'en';
  }
}

const deviceLocale = getDeviceLocale();
const supportedLocale = deviceLocale.toLowerCase().startsWith('es') ? 'es' : 'en';
console.log('[i18n] device locale:', deviceLocale, '→', supportedLocale);

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      es: { translation: es },
    },
    lng: supportedLocale,
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
    initImmediate: false, // synchronous init — resources are inline so no async needed
  });

export default i18n;
