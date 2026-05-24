import { writable } from 'svelte/store';
import type { SessionUser } from '$lib/api/auth';
import { getSessionUser, setSessionUser as persistSessionUser } from '$lib/api/client';

export const sessionUser = writable<SessionUser | null>(null);

export function initSessionUser(): void {
  sessionUser.set(getSessionUser());
}

export function updateSessionUser(user: SessionUser): void {
  persistSessionUser(user);
  sessionUser.set(user);
}

export function patchSessionUser(patch: Partial<SessionUser>): void {
  const current = getSessionUser();
  if (!current) return;
  updateSessionUser({ ...current, ...patch });
}
