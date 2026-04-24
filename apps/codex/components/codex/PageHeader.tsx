import Link from 'next/link';
import { ChevronRight } from 'lucide-react';

interface Breadcrumb {
  label: string;
  href: string;
}

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: Breadcrumb[];
}

export function PageHeader({ title, subtitle, breadcrumbs }: PageHeaderProps) {
  return (
    <div className="border-b border-[var(--border)] bg-[var(--background)] pb-6 pt-8">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="mb-4 flex items-center gap-1 text-sm text-[var(--muted-foreground)]">
          {breadcrumbs.map((crumb, i) => (
            <span key={crumb.href} className="flex items-center gap-1">
              {i > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
              {i < breadcrumbs.length - 1 ? (
                <Link
                  href={crumb.href}
                  className="hover:text-[var(--foreground)] transition-colors"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span style={{ color: 'hsl(var(--ari-gold-hsl))' }}>{crumb.label}</span>
              )}
            </span>
          ))}
        </nav>
      )}
      <h1 className="text-3xl font-bold tracking-tight text-[var(--foreground)]">
        {title}
      </h1>
      {subtitle && (
        <p className="mt-2 text-lg text-[var(--muted-foreground)]">{subtitle}</p>
      )}
    </div>
  );
}
