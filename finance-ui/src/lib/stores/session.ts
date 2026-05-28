import { writable } from 'svelte/store';
import type { SessionUser } from '$lib/api/auth';
import { fetchMe, sessionUserFromLogin } from '$lib/api/auth';
import {
  getSessionUser,
  getToken,
  setSessionUser as persistSessionUser,
} from '$lib/api/client';
import { profileDisplayLabel } from '$lib/displayUser';

/** Current finance user — survives route changes; set on login and initAuth. */
export const sessionUser = writable<SessionUser | null>(null);

/** Alias for layout/auth consumers preferring "currentUser". */
export const currentUser = sessionUser;

/** False until token + user profile are resolved (or confirmed absent). */
export const authReady = writable(false);

export function navDisplayName(user: SessionUser | null): string {
  return profileDisplayLabel(user) ?? 'User';
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

/** @deprecated Use initAuth — kept for callers that only need localStorage sync. */
export function initSessionUser(): void {
  sessionUser.set(getSessionUser());
}

/**
 * Read access token and session user from localStorage; fetch /auth/me when needed.
 * Sets authReady when finished so the shell can render nav without flashing empty chrome.
 */
export async function initAuth(): Promise<boolean> {
  authReady.set(false);
  try {
    const token = getToken();
    if (!token) {
      sessionUser.set(null);
      return false;
    }

    const cached = getSessionUser();
    if (cached && profileDisplayLabel(cached)) {
      sessionUser.set(cached);
      return true;
    }

    try {
      const me = await fetchMe();
      updateSessionUser(sessionUserFromLogin(me));
      return true;
    } catch {
      if (cached) {
        sessionUser.set(cached);
        return true;
      }
      sessionUser.set(null);
      return false;
    }
  } finally {
    authReady.set(true);
  }
}

export function clearAuth(): void {
  sessionUser.set(null);
}
