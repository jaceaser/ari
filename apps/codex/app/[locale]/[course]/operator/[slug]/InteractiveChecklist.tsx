'use client';

import { useState, useEffect } from 'react';
import { CheckSquare, Square } from 'lucide-react';

interface InteractiveChecklistProps {
  items: string[];
  cardId: string;
}

export function InteractiveChecklist({ items, cardId }: InteractiveChecklistProps) {
  const [checked, setChecked] = useState<boolean[]>(() => items.map(() => false));

  // Persist to localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`checklist-${cardId}`);
      if (saved) {
        const parsed: boolean[] = JSON.parse(saved);
        setChecked(parsed.length === items.length ? parsed : items.map(() => false));
      }
    } catch {
      // ignore
    }
  }, [cardId, items]);

  const toggle = (index: number) => {
    const updated = checked.map((v, i) => (i === index ? !v : v));
    setChecked(updated);
    try {
      localStorage.setItem(`checklist-${cardId}`, JSON.stringify(updated));
    } catch {
      // ignore
    }
  };

  const completedCount = checked.filter(Boolean).length;
  const progress = items.length > 0 ? (completedCount / items.length) * 100 : 0;

  return (
    <div>
      {/* Progress bar */}
      <div className="mb-4 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--muted)]">
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{
              width: `${progress}%`,
              backgroundColor: 'hsl(var(--ari-gold-hsl))',
            }}
          />
        </div>
        <span className="text-sm text-[var(--muted-foreground)]">
          {completedCount}/{items.length}
        </span>
      </div>

      {/* Items */}
      <ul className="space-y-2">
        {items.map((item, i) => (
          <li key={i}>
            <button
              type="button"
              onClick={() => toggle(i)}
              className="flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-[var(--muted)]"
            >
              {checked[i] ? (
                <CheckSquare
                  className="mt-0.5 h-5 w-5 shrink-0"
                  style={{ color: 'hsl(var(--ari-gold-hsl))' }}
                />
              ) : (
                <Square className="mt-0.5 h-5 w-5 shrink-0 text-[var(--muted-foreground)]" />
              )}
              <span
                className={`text-sm transition-colors ${
                  checked[i]
                    ? 'text-[var(--muted-foreground)] line-through'
                    : 'text-[var(--foreground)]'
                }`}
              >
                {item}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
