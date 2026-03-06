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
  content: string;
  created_at?: string;
};

export async function getMessages(sessionId: string): Promise<Message[]> {
  const data = await apiFetch<Message[]>(`/sessions/${sessionId}/messages`);
  return Array.isArray(data) ? data : [];
}

// ─── Streaming ───────────────────────────────────────────────────────────────

export function streamMessage(
  sessionId: string,
  content: string,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: Error) => void,
): Promise<void> {
  // Use XMLHttpRequest with onprogress — the only reliable streaming
  // approach in React Native (response.body ReadableStream is flaky).
  return getToken().then((token) => {
    return new Promise<void>((resolve) => {
      const xhr = new XMLHttpRequest();
      let processed = 0;
      let buffer = '';
      let settled = false;

      const settle = (fn: () => void) => {
        if (settled) return;
        settled = true;
        fn();
        resolve();
      };

      xhr.open('POST', `${API_BASE_URL}/sessions/${sessionId}/messages`, true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

      xhr.onprogress = () => {
        const raw = xhr.responseText;
        const newData = raw.slice(processed);
        processed = raw.length;

        buffer += newData;
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') continue;
          try {
            const parsed = JSON.parse(data) as {
              choices?: Array<{ delta?: { content?: string } }>;
              error?: { message?: string };
            };
            if (parsed.error?.message) {
              settle(() => onError(new Error(parsed.error!.message)));
              return;
            }
            const text = parsed.choices?.[0]?.delta?.content;
            if (text) onChunk(text);
          } catch { /* non-JSON SSE line — skip */ }
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 400) {
          let message = `Request failed (${xhr.status})`;
          try {
            const body = JSON.parse(xhr.responseText) as { detail?: string; error?: string };
            if (body.detail) message = body.detail;
            else if (typeof body.error === 'string') message = body.error;
          } catch { /* ignore */ }
          settle(() => onError(new Error(message)));
        } else {
          settle(() => onDone());
        }
      };

      xhr.onerror = () => settle(() => onError(new Error('Network error')));
      xhr.ontimeout = () => settle(() => onError(new Error('Request timed out')));
      xhr.timeout = 120000; // 2 min timeout

      xhr.send(JSON.stringify({ content }));
    });
  });
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
