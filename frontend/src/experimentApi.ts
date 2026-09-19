export type Json = Record<string, any>;
let sessionToken: string | undefined;
let sessionRequest: Promise<string> | undefined;

export async function getSessionToken(): Promise<string> {
  if (sessionToken) return sessionToken;
  sessionRequest ??= (async () => {
    const response = await fetch('/api/session', { cache: 'no-store' });
    if (!response.ok) throw new Error(`Local session request failed (${response.status})`);
    const session = await response.json();
    if (!session.enabled || typeof session.token !== 'string' || !session.token) {
      throw new Error('This action is available in the local app. / 请在本地应用中执行此操作。');
    }
    sessionToken = session.token;
    return session.token as string;
  })();
  try {
    return await sessionRequest;
  } finally {
    sessionRequest = undefined;
  }
}

export async function experimentRequest(path: string, payload?: Json): Promise<Json> {
  const token = payload === undefined ? undefined : await getSessionToken();
  const response = await fetch(path, payload === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-PCL-Session': token ?? '' }, body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : `Request failed (${response.status})`);
  }
  return response.json();
}
