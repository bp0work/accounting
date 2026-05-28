export const DISPLAY_USER_KEY = 'client_admin_display_user';

export type CachedDisplayUser = {
  username: string;
  display_name: string;
  email?: string;
};

export function setCachedDisplayUser(user: CachedDisplayUser): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(DISPLAY_USER_KEY, JSON.stringify(user));
}

export function getCachedDisplayUser(): CachedDisplayUser | null {
  if (typeof localStorage === 'undefined') return null;
  const raw = localStorage.getItem(DISPLAY_USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CachedDisplayUser;
  } catch {
    return null;
  }
}

export function clearCachedDisplayUser(): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(DISPLAY_USER_KEY);
}
