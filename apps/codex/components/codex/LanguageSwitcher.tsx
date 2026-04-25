'use client'
import { useLocale } from '@/lib/locale-context'
import { usePathname, useRouter } from 'next/navigation'

export function LanguageSwitcher() {
  const locale = useLocale()
  const pathname = usePathname()
  const router = useRouter()

  function switchLocale() {
    const next = locale === 'en' ? 'es' : 'en'
    // Replace first segment (locale) with new locale
    const segments = pathname.split('/')
    segments[1] = next
    router.push(segments.join('/'))
  }

  return (
    <button
      onClick={switchLocale}
      className="text-sm font-medium text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors px-2 py-1 rounded border border-[var(--border)] hover:border-[var(--primary)]"
      style={{
        color: 'rgba(255,255,255,0.35)',
        borderColor: 'rgba(255,255,255,0.12)',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = 'rgba(255,255,255,0.85)';
        e.currentTarget.style.borderColor = 'hsl(41 92% 67% / 0.5)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = 'rgba(255,255,255,0.35)';
        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)';
      }}
    >
      {locale === 'en' ? 'Español' : 'English'}
    </button>
  )
}
