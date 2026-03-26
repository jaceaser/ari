import { getRequestConfig } from 'next-intl/server';

export default getRequestConfig(async () => {
  // Default to English for server-side rendering.
  // Client-side locale detection happens via the LocaleProvider.
  const locale = 'en';

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
