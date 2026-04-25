import { LocaleProvider } from '@/lib/locale-context'
import type { Locale } from '@/lib/translations'
import { SUPPORTED_LOCALES } from '@/lib/translations'

interface LocaleLayoutProps {
  children: React.ReactNode
  params: Promise<{ locale: string }>
}

export default async function LocaleLayout({ children, params }: LocaleLayoutProps) {
  const { locale } = await params
  const safeLocale: Locale = SUPPORTED_LOCALES.includes(locale as Locale)
    ? (locale as Locale)
    : 'en'

  return (
    <LocaleProvider value={safeLocale}>
      {children}
    </LocaleProvider>
  )
}
