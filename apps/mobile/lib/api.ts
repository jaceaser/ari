import { API_BASE_URL, DEEP_LINK_VERIFY_PATH } from './config';
import { getToken } from './auth';

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { ...headers, ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export async function sendMagicLink(email: string): Promise<void> {
  await apiFetch('/auth/magic-link/send', {
    method: 'POST',
    body: JSON.stringify({ email, redirect_uri: DEEP_LINK_VERIFY_PATH }),
  });
}

export async function verifyMagicLink(
  token: string,
): Promise<{ token: string; user: { id: string; email: string } }> {
  return apiFetch('/auth/magic-link/verify', {
    method: 'POST',
    body: JSON.stringify({ token }),
  });
}

// ─── Sessions ────────────────────────────────────────────────────────────────

export type Session = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt?: number;
};

export async function listSessions(): Promise<Session[]> {
  const data = await apiFetch<{ sessions: Session[] }>('/sessions');
  return data.sessions ?? [];
}

export async function createSession(id: string): Promise<Session> {
  return apiFetch('/sessions', {
    method: 'POST',
    body: JSON.stringify({ id }),
  });
}

export async function getSession(id: string): Promise<Session> {
  return apiFetch(`/sessions/${id}`);
}

export async function deleteSession(id: string): Promise<void> {
  await apiFetch(`/sessions/${id}`, { method: 'DELETE' });
}

export type Message = {
  id: string;
  role: 'user' | 'assistant';
  parts: Array<{ type: string; text?: string }>;
  createdAt?: number;
};

export async function getMessages(sessionId: string): Promise<Message[]> {
  const data = await apiFetch<{ messages: Message[] }>(
    `/sessions/${sessionId}/messages`,
  );
  return data.messages ?? [];
}

// ─── Streaming ───────────────────────────────────────────────────────────────

export async function streamMessage(
  sessionId: string,
  content: string,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: Error) => void,
): Promise<void> {
  const token = await getToken();
  let buffer = '';

  try {
    const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content }),
    });

    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`Stream ${res.status}: ${text}`);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6).trim();
        if (data === '[DONE]') continue;
        try {
          const parsed = JSON.parse(data) as {
            choices?: Array<{ delta?: { content?: string } }>;
          };
          const text = parsed.choices?.[0]?.delta?.content;
          if (text) onChunk(text);
        } catch {
          // non-JSON line, skip
        }
      }
    }

    onDone();
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)));
  }
}

// ─── Billing ─────────────────────────────────────────────────────────────────

export type BillingStatus = {
  active: boolean;
  plan: string | null;
  tier: string | null;
  status: string | null;
};

export async function getBillingStatus(): Promise<BillingStatus> {
  return apiFetch('/billing/status');
}

export async function createPortalSession(): Promise<{ url: string }> {
  return apiFetch('/billing/create-portal', { method: 'POST' });
}
