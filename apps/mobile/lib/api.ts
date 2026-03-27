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

export async function verifyReviewCode(
  code: string,
): Promise<{ token: string; user: { id: string; email: string } }> {
  return apiFetch('/auth/review-code', {
    method: 'POST',
    body: JSON.stringify({ code }),
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
  // Backend returns a plain array; handle both array and {sessions:[]} shapes.
  const data = await apiFetch<unknown>('/sessions');
  const arr: any[] = Array.isArray(data) ? data : ((data as any)?.sessions ?? []);
  return arr.map((s: any) => ({
    id: s.id,
    title: s.title ?? '',
    createdAt: s.createdAt ?? (s.created_at ? new Date(s.created_at).getTime() : 0),
    updatedAt: s.updatedAt ?? (s.updated_at ? new Date(s.updated_at).getTime() : undefined),
  }));
}

export async function createSession(id: string): Promise<Session> {
  return apiFetch('/sessions', {
    method: 'POST',
    body: JSON.stringify({ id }),
  });
}

export async function getSession(id: string): Promise<Session> {
  const data = await apiFetch<any>(`/sessions/${id}`);
  return {
    id: data.id,
    title: data.title ?? '',
    createdAt: data.createdAt ?? (data.created_at ? new Date(data.created_at).getTime() : 0),
    updatedAt: data.updatedAt ?? (data.updated_at ? new Date(data.updated_at).getTime() : undefined),
  };
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

// ─── Attachments ─────────────────────────────────────────────────────────────

export type Attachment = {
  uri: string;
  mimeType: string;
  filename: string;
  isImage: boolean;
};

export type UploadedFile = {
  url: string;
  pathname: string;
  contentType: string;
};

export function uploadFile(
  fileUri: string,
  mimeType: string,
  filename: string,
): Promise<UploadedFile> {
  return getToken().then((token) => {
    return new Promise<UploadedFile>((resolve, reject) => {
      const formData = new FormData();
      // React Native FormData accepts {uri, type, name} for files
      formData.append('file', { uri: fileUri, type: mimeType, name: filename } as any);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE_URL}/documents/upload`, true);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText) as UploadedFile);
          } catch {
            reject(new Error('Invalid upload response'));
          }
        } else {
          let msg = `Upload failed (${xhr.status})`;
          try {
            const b = JSON.parse(xhr.responseText) as { detail?: string };
            if (b.detail) msg = b.detail;
          } catch { /* ignore */ }
          reject(new Error(msg));
        }
      };
      xhr.onerror = () => reject(new Error('Network error during upload'));
      xhr.ontimeout = () => reject(new Error('Upload timed out'));
      xhr.timeout = 60000;

      xhr.send(formData);
    });
  });
}

// ─── Streaming ───────────────────────────────────────────────────────────────

export function streamMessage(
  sessionId: string,
  content: string,
  images: string[] | undefined,
  documents: Array<{ url: string; mediaType: string }> | undefined,
  onChunk: (text: string) => void,
  onDone: (complete: boolean) => void,
  onError: (err: Error) => void,
): { promise: Promise<void>; abort: () => void } {
  // Use XMLHttpRequest with onprogress — the only reliable streaming
  // approach in React Native (response.body ReadableStream is flaky).
  let xhrRef: XMLHttpRequest | null = null;
  const promise = getToken().then((token) => {
    return new Promise<void>((resolve) => {
      const xhr = new XMLHttpRequest();
      xhrRef = xhr;
      let processed = 0;
      let buffer = '';
      let settled = false;
      // Track whether the server sent the SSE [DONE] sentinel.
      // If onload fires without us ever seeing [DONE], the stream was truncated
      // (common on iOS where NSURLSession can close the socket early).
      let doneSeen = false;

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
          if (data === '[DONE]') { doneSeen = true; continue; }
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
          // Flush any SSE data that onprogress didn't finish processing.
          // This handles the case where onload fires before onprogress delivers
          // the final bytes (common on React Native), leaving text stuck in buffer.
          const finalData = xhr.responseText.slice(processed);
          if (finalData || buffer) {
            const lines = (buffer + finalData).split('\n');
            for (const line of lines) {
              if (!line.startsWith('data: ')) continue;
              const data = line.slice(6).trim();
              if (data === '[DONE]') { doneSeen = true; continue; }
              try {
                const parsed = JSON.parse(data) as {
                  choices?: Array<{ delta?: { content?: string } }>;
                };
                const text = parsed.choices?.[0]?.delta?.content;
                if (text) onChunk(text);
              } catch { /* non-JSON line — skip */ }
            }
          }
          settle(() => onDone(doneSeen));
        }
      };

      xhr.onerror = () => settle(() => onError(new Error('Network error')));
      xhr.ontimeout = () => settle(() => onError(new Error('Request timed out')));
      xhr.timeout = 120000; // 2 min timeout

      const body: Record<string, unknown> = { content };
      if (images?.length) body.images = images;
      if (documents?.length) body.documents = documents;
      xhr.send(JSON.stringify(body));
    });
  });
  return {
    promise,
    abort: () => { xhrRef?.abort(); },
  };
}

// ─── User profile ────────────────────────────────────────────────────────────

export type UserProfile = {
  email: string;
  tier: string;
};

export async function getUserProfile(): Promise<UserProfile> {
  return apiFetch('/billing/me');
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
