'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Search, X } from 'lucide-react';
import Fuse from 'fuse.js';
import type { SearchableEntity } from '@/lib/search-index';
import { EntityBadge } from './EntityBadge';
import type { EntityType } from '@/types/codex';
import { cn } from '@/lib/cn';

function getEntityPath(entity: SearchableEntity, courseSlug: string): string {
  const typeMap: Record<string, string> = {
    topic: 'topic',
    'case-study': 'case-study',
    pathway: 'pathway',
    glossary: 'glossary',
    'operator-card': 'operator',
  };
  const segment = typeMap[entity.type] ?? entity.type;
  return `/${courseSlug}/${segment}/${entity.slug}`;
}

function groupByType(
  results: SearchableEntity[]
): Array<{ type: string; items: SearchableEntity[] }> {
  const map = new Map<string, SearchableEntity[]>();
  for (const item of results) {
    if (!map.has(item.type)) map.set(item.type, []);
    map.get(item.type)!.push(item);
  }
  return Array.from(map.entries()).map(([type, items]) => ({ type, items }));
}

interface SearchBarProps {
  searchData: SearchableEntity[];
  courseSlug: string;
  placeholder?: string;
  className?: string;
}

export function SearchBar({ searchData, courseSlug, placeholder, className }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchableEntity[]>([]);
  const [open, setOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const fuse = useRef(
    new Fuse(searchData, {
      keys: [
        { name: 'title', weight: 2 },
        { name: 'summary', weight: 1.5 },
        { name: 'aliases', weight: 1.5 },
        { name: 'searchTerms', weight: 1.5 },
        { name: 'tags', weight: 1 },
        { name: 'plainEnglish', weight: 1 },
        { name: 'definition', weight: 1 },
      ],
      threshold: 0.4,
      includeScore: true,
    })
  );

  const handleSearch = useCallback(
    (q: string) => {
      setQuery(q);
      setSelectedIndex(-1);
      if (!q.trim()) {
        setResults([]);
        setOpen(false);
        return;
      }
      const found = fuse.current.search(q).map((r) => r.item);
      setResults(found.slice(0, 12));
      setOpen(found.length > 0);
    },
    []
  );

  const navigate = useCallback(
    (entity: SearchableEntity) => {
      router.push(getEntityPath(entity, courseSlug));
      setOpen(false);
      setQuery('');
      setResults([]);
    },
    [router, courseSlug]
  );

  const flatResults = results;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, flatResults.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, -1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex >= 0 && flatResults[selectedIndex]) {
        navigate(flatResults[selectedIndex]);
      } else if (flatResults[0]) {
        navigate(flatResults[0]);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const groups = groupByType(results);

  return (
    <div ref={containerRef} className={cn('relative w-full', className)}>
      <div className="relative flex items-center">
        <Search
          className="pointer-events-none absolute left-4 h-5 w-5"
          style={{ color: 'hsl(var(--ari-gold-hsl))' }}
        />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => query && results.length > 0 && setOpen(true)}
          placeholder={placeholder ?? 'Search topics, glossary, case studies…'}
          className="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] py-3.5 pl-12 pr-10 text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none transition-all focus:border-[hsl(var(--ari-gold-hsl))/0.5] focus:ring-1 focus:ring-[hsl(var(--ari-gold-hsl))/0.3]"
          style={{
            outline: 'none',
          }}
          autoComplete="off"
        />
        {query && (
          <button
            type="button"
            onClick={() => { setQuery(''); setResults([]); setOpen(false); inputRef.current?.focus(); }}
            className="absolute right-3 rounded p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute left-0 right-0 top-full z-50 mt-2 max-h-96 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--popover)] shadow-2xl shadow-black/40">
          {groups.map((group) => (
            <div key={group.type}>
              <div className="sticky top-0 bg-[var(--popover)] px-4 py-2 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                {group.type}
              </div>
              {group.items.map((item) => {
                const idx = flatResults.indexOf(item);
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => navigate(item)}
                    className={cn(
                      'flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-[var(--muted)]',
                      idx === selectedIndex && 'bg-[var(--muted)]'
                    )}
                  >
                    <div className="mt-0.5">
                      <EntityBadge type={item.type as EntityType} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-[var(--foreground)]">{item.title}</p>
                      <p className="mt-0.5 truncate text-sm text-[var(--muted-foreground)]">
                        {item.summary}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
