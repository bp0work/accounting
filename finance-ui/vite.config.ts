import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/approvals': 'http://localhost:8000',
      '/cases': 'http://localhost:8000',
      '/notifications': 'http://localhost:8000',
      '/notification-templates': 'http://localhost:8000',
      '/users': 'http://localhost:8000',
      '/events': 'http://localhost:8000',
    },
  },
});
