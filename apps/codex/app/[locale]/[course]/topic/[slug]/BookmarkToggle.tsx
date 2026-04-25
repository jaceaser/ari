'use client';

import { useState, useEffect } from 'react';
import { Bookmark } from 'lucide-react';

interface BookmarkToggleProps {
  entityId: string;
}

export function BookmarkToggle({ entityId }: BookmarkToggleProps) {
  const [bookmarked, setBookmarked] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem('codex-bookmarks');
      if (saved) {
        const list: string[] = JSON.parse(saved);
        setBookmarked(list.includes(entityId));
      }
    } catch {
      // ignore
    }
  }, [entityId]);

  const toggle = () => {
    try {
      const saved = localStorage.getItem('codex-bookmarks');
      const list: string[] = saved ? JSON.parse(saved) : [];
      const updated = bookmarked
        ? list.filter((id) => id !== entityId)
        : [...list, entityId];
      localStorage.setItem('codex-bookmarks', JSON.stringify(updated));
      setBookmarked(!bookmarked);
    } catch {
      // ignore
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      className="flex w-full items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-2 text-sm transition-colors hover:bg-[var(--muted)]"
      style={{
        color: bookmarked ? 'hsl(var(--ari-gold-hsl))' : 'var(--muted-foreground)',
        borderColor: bookmarked ? 'hsl(var(--ari-gold-hsl) / 0.4)' : undefined,
      }}
    >
      <Bookmark
        className="h-4 w-4"
        fill={bookmarked ? 'currentColor' : 'none'}
      />
      {bookmarked ? 'Bookmarked' : 'Save for later'}
    </button>
  );
}
