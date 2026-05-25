import { redirect } from '@sveltejs/kit';

export const ssr = false;

export function load() {
  throw redirect(302, '/travel-info');
}
