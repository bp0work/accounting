import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      // API only — browser navigation to /approvals is the SvelteKit page (see bypass).
      '/approvals': {
        target: 'http://localhost:8000',
        bypass(req) {
          const accept = req.headers.accept ?? '';
          if (accept.includes('text/html')) {
            return req.url;
          }
        },
      },
      '/cases': 'http://localhost:8000',
      '/notifications': 'http://localhost:8000',
      '/notification-templates': 'http://localhost:8000',
      '/users': 'http://localhost:8000',
      '/events': 'http://localhost:8000',
    },
  },
});
