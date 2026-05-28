import { redirect } from '@sveltejs/kit';

export const ssr = false;

/**
 * /users has been folded into /mailboxes — the Mailboxes table now shows
 * display names and escalation emails for all 9 mailboxes, covering what
 * the old per-role Users form used to surface. Permanent (307) so any
 * bookmarked /users links are quietly forwarded.
 */
export function load(): never {
  throw redirect(307, '/mailboxes');
}
