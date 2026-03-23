import path from 'path';
import { defineConfig, Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

// Prevent CDNs (Cloudflare) from caching Service Worker files
function noCacheSW(): Plugin {
  return {
    name: 'no-cache-sw',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url && /^\/(sw|registerSW|workbox-)/.test(req.url)) {
          res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0');
          res.setHeader('CDN-Cache-Control', 'no-store');
          res.setHeader('Cloudflare-CDN-Cache-Control', 'no-store');
        }
        next();
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const isMobileBuild = mode === 'mobile';

  return {
    plugins: [
      noCacheSW(),
      react(),
      !isMobileBuild &&
        VitePWA({
          registerType: 'autoUpdate',
          includeAssets: ['favicon.ico', 'robots.txt', 'apple-touch-icon.png'],
          manifest: {
            name: 'Taxja - Austrian Tax Management',
            short_name: 'Taxja',
            description: 'Automated tax management for Austrian taxpayers',
            theme_color: '#1976d2',
            background_color: '#ffffff',
            display: 'standalone',
            orientation: 'portrait',
            scope: '/',
            start_url: '/',
            icons: [
              {
                src: 'icons/icon-192.webp',
                sizes: '192x192',
                type: 'image/webp',
                purpose: 'any maskable',
              },
              {
                src: 'icons/icon-512.webp',
                sizes: '512x512',
                type: 'image/webp',
                purpose: 'any maskable',
              },
            ],
          },
          workbox: {
            runtimeCaching: [
              {
                urlPattern: /^https:\/\/api\.taxja\.at\/api\/v1\/.*/i,
                handler: 'NetworkFirst',
                options: {
                  cacheName: 'api-cache',
                  expiration: {
                    maxEntries: 100,
                    maxAgeSeconds: 60 * 60 * 24,
                  },
                  cacheableResponse: {
                    statuses: [0, 200],
                  },
                },
              },
              {
                urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
                handler: 'CacheFirst',
                options: {
                  cacheName: 'image-cache',
                  expiration: {
                    maxEntries: 50,
                    maxAgeSeconds: 60 * 60 * 24 * 30,
                  },
                },
              },
              {
                urlPattern: /\.(?:woff|woff2|ttf|eot)$/,
                handler: 'CacheFirst',
                options: {
                  cacheName: 'font-cache',
                  expiration: {
                    maxEntries: 10,
                    maxAgeSeconds: 60 * 60 * 24 * 365,
                  },
                },
              },
              {
                urlPattern: /\.(?:js|css)$/,
                handler: 'StaleWhileRevalidate',
                options: {
                  cacheName: 'static-cache',
                  expiration: {
                    maxEntries: 50,
                    maxAgeSeconds: 60 * 60 * 24 * 7,
                  },
                },
              },
            ],
            cleanupOutdatedCaches: true,
            skipWaiting: true,
            clientsClaim: true,
          },
          devOptions: {
            enabled: false,
            type: 'module',
          },
        }),
    ].filter(Boolean),
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom', 'react-router-dom'],
            'form-vendor': ['react-hook-form', 'zod', '@hookform/resolvers'],
            'chart-vendor': ['recharts'],
            'i18n-vendor': ['i18next', 'react-i18next'],
          },
        },
      },
      chunkSizeWarningLimit: 1000,
      minify: 'terser',
      terserOptions: {
        compress: {
          drop_console: true,
          drop_debugger: true,
        },
      },
      sourcemap: false,
    },
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        'react-router-dom',
        'zustand',
        'react-hook-form',
        'zod',
        'recharts',
        'i18next',
        'react-i18next',
        'axios',
      ],
    },
    server: {
      port: 5173,
      host: '0.0.0.0',
      hmr: {
        clientPort: 5173,
      },
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
      allowedHosts: true,
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/test-setup.ts'],
    },
  };
});
