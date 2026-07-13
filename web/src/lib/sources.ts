// Brand logos + provider grouping, shared by demo and live surfaces.
// Google groups Gmail + Calendar (one account), matching the live extension.
import type { Source } from './types';

export const GOOGLE_LOGO =
	'<svg viewBox="0 0 24 24" width="16" height="16" style="display:block" aria-hidden="true"><path fill="#4285F4" d="M23.52 12.27c0-.79-.07-1.54-.2-2.27H12v4.51h6.47a5.53 5.53 0 0 1-2.4 3.63v3h3.88c2.27-2.09 3.57-5.17 3.57-8.87z"/><path fill="#34A853" d="M12 24c3.24 0 5.96-1.08 7.95-2.91l-3.88-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09A11.99 11.99 0 0 0 12 24z"/><path fill="#FBBC05" d="M5.27 14.29a7.2 7.2 0 0 1 0-4.58V6.62H1.29a12 12 0 0 0 0 10.76l3.98-3.09z"/><path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.44-3.44C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.69 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z"/></svg>';

export const NOTION_LOGO =
	'<svg viewBox="0 0 24 24" width="16" height="16" style="display:block" aria-hidden="true"><rect x="2" y="2" width="20" height="20" rx="4" fill="#fff"/><path fill="#0E0E10" d="M8 7h2.06l3.94 5.86V7H16v10h-2.06L10 11.14V17H8V7z"/></svg>';

export interface Provider {
	id: 'google' | 'notion';
	label: string;
	sub: string;
	blurb: string;
	sources: Source[];
	logo: string;
}

export const PROVIDERS: Provider[] = [
	{
		id: 'google',
		label: 'Google',
		sub: 'Gmail + Calendar',
		blurb: 'Emails, threads, events & invites',
		sources: ['gmail', 'calendar'],
		logo: GOOGLE_LOGO
	},
	{ id: 'notion', label: 'Notion', sub: '', blurb: 'Docs, notes, wikis', sources: ['notion'], logo: NOTION_LOGO }
];

/** The right brand logo for a card's source (Gmail + Calendar → Google). */
export function sourceLogo(source: string): string {
	return source === 'notion' ? NOTION_LOGO : GOOGLE_LOGO;
}
