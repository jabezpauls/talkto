import { defineConfig } from 'tsup';

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    'scripts/postinstall': 'src/scripts/postinstall.ts',
  },
  format: ['esm'],
  dts: true,
  clean: true,
  sourcemap: true,
  target: 'node18',
  shims: true,
  // @fugood/whisper.node is a native addon — must not be bundled
  external: ['@fugood/whisper.node'],
  banner: {
    js: '#!/usr/bin/env node'
  }
});
