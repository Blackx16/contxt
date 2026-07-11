/**
 * Live client-side pull from the user's connected sources.
 *
 * Runs in the popup with the OAuth tokens obtained via chrome.identity. Each
 * function returns a flat list of { source, title, text } — the caller runs each
 * through the on-device gateway (rules) to decide SHARED vs PRIVATE, so raw
 * account data is tiered locally before anything is shown or sent.
 *
 * CORS: these hosts are in the manifest host_permissions, so the extension's
 * fetches bypass CORS (Notion's API sends no CORS headers — host permission is
 * what makes the browser call work at all).
 */

const GAPI = 'https://www.googleapis.com';

// Newsletters and forwards arrive as HTML with entities, tracking pixels, and
// zero-width padding. Strip all that so injected context is clean, not garbage.
function clean(s) {
  return String(s || '')
    .replace(/<[^>]+>/g, ' ') // HTML tags
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')
    .replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&nbsp;/g, ' ')
    .replace(/-{2,}\s*Forwarded[\s\S]*?-{2,}/gi, ' ') // "---- Forwarded from … ----"
    .replace(/\b\d+\s+email\s+trackers?\s+removed\b/gi, ' ') // Firefox Relay noise
    .replace(/[​-‍⁠͏­᠎]/g, '') // zero-width / soft hyphen
    .replace(/\s+/g, ' ')
    .trim();
}

async function gfetch(url, token) {
  const r = await fetch(url, { headers: { Authorization: 'Bearer ' + token } });
  if (r.status === 401) throw new Error('google-auth-expired');
  if (!r.ok) throw new Error('google HTTP ' + r.status);
  return r.json();
}

/** Recent PRIMARY-inbox Gmail (promos/social/updates excluded). Read-only. */
export async function pullGmail(token, max = 4) {
  const q = encodeURIComponent(
    'in:inbox newer_than:30d -category:promotions -category:social -category:updates',
  );
  const list = await gfetch(`${GAPI}/gmail/v1/users/me/messages?maxResults=${max}&q=${q}`, token);
  const ids = (list.messages || []).map((m) => m.id);
  const out = [];
  for (const id of ids) {
    const msg = await gfetch(
      `${GAPI}/gmail/v1/users/me/messages/${id}?format=metadata&metadataHeaders=Subject`,
      token,
    );
    const h = Object.fromEntries(
      (msg.payload?.headers || []).map((x) => [x.name.toLowerCase(), x.value]),
    );
    const subject = clean(h.subject || '(no subject)');
    const snippet = clean(msg.snippet || '').slice(0, 140);
    out.push({ source: 'gmail', title: subject, text: `${subject}. ${snippet}`.trim() });
  }
  return out;
}

/** Upcoming Calendar events → {summary, description, attendees}. */
export async function pullCalendar(token, max = 5) {
  const timeMin = new Date().toISOString();
  const data = await gfetch(
    `${GAPI}/calendar/v3/calendars/primary/events` +
      `?maxResults=${max}&singleEvents=true&orderBy=startTime&timeMin=${encodeURIComponent(timeMin)}`,
    token,
  );
  return (data.items || []).map((e) => {
    const title = clean(e.summary || '(untitled event)');
    const desc = clean(e.description || '').slice(0, 140);
    return { source: 'calendar', title, text: `${title}. ${desc}`.trim() };
  });
}

/** Recently-edited Notion pages/databases → {title}. */
export async function pullNotion(token, max = 5) {
  const r = await fetch('https://api.notion.com/v1/search', {
    method: 'POST',
    headers: {
      Authorization: 'Bearer ' + token,
      'Content-Type': 'application/json',
      'Notion-Version': '2022-06-28',
    },
    body: JSON.stringify({
      page_size: max,
      sort: { direction: 'descending', timestamp: 'last_edited_time' },
    }),
  });
  if (r.status === 401) throw new Error('notion-auth-expired');
  if (!r.ok) throw new Error('notion HTTP ' + r.status);
  const data = await r.json();
  return (data.results || []).map((p) => {
    const title = clean(notionTitle(p));
    return { source: 'notion', title, text: title };
  });
}

function notionTitle(page) {
  const props = page.properties || {};
  for (const key of Object.keys(props)) {
    const p = props[key];
    if (p?.type === 'title' && Array.isArray(p.title)) {
      const t = p.title.map((x) => x.plain_text).join('');
      if (t) return t;
    }
  }
  if (Array.isArray(page.title)) {
    return page.title.map((x) => x.plain_text).join('') || '(untitled)';
  }
  return '(untitled Notion item)';
}
