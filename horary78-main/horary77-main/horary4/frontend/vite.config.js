import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ command }) => {
  const isDev = command === 'serve';
  
  return {
    plugins: [react()],
    
    base: '/',
    
    server: {
      port: 3000,
      open: true,
      cors: true,
      strictPort: true,
      host: 'localhost', // Changed from 0.0.0.0 to localhost for security
    },
    
    build: {
      outDir: 'dist',
      sourcemap: isDev,
      minify: !isDev,
      
      rollupOptions: {
        input: {
          main: resolve(__dirname, 'index.html')
        },
        
        output: {
          // Optimize chunk splitting
          manualChunks: {
            vendor: ['react', 'react-dom'],
            icons: ['lucide-react']
          }
        }
      },
      
      // Target modern environments
      target: 'es2015',
      
      assetsDir: 'assets',
      chunkSizeWarningLimit: 1000,
    },
    
    // Environment variables for the app
    define: {
      global: 'globalThis',
      __APP_VERSION__: JSON.stringify(process.env.npm_package_version || '1.1.0'),
      __IS_DEV__: JSON.stringify(isDev)
    },
    
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
        '@components': resolve(__dirname, 'src/components'),
        '@utils': resolve(__dirname, 'src/utils'),
        '@assets': resolve(__dirname, 'src/assets'),
      }
    },
    
    // Optimization
    optimizeDeps: {
      include: ['react', 'react-dom', 'lucide-react'],
      // Force pre-bundling of CJS dependencies
      force: isDev
    },
    
    // CSS configuration - simplified
    css: {
      devSourcemap: isDev
    },
    
    // Preview configuration
    preview: {
      port: 4173,
      strictPort: true,
      host: 'localhost'
    },
    
    
  }
})