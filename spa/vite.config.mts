import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  root: 'renderer',
  base: './',
  server: {
    host: '0.0.0.0', // Listen on all network interfaces (IPv4 and IPv6)
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../dist/renderer',
    emptyOutDir: true,
    sourcemap: true,
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-mui': ['@mui/material', '@mui/icons-material', '@emotion/react', '@emotion/styled'],
          'vendor-editor': ['@monaco-editor/react', 'monaco-editor'],
          'vendor-markdown': ['react-markdown', '@uiw/react-md-editor', 'remark-gfm', 'rehype-highlight', 'rehype-raw'],
          'vendor-utils': ['axios', 'socket.io-client', 'uuid', 'd3'],
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './renderer/src'),
    },
  },
});
