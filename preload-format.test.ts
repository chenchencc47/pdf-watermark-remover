import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

describe('Electron preload format', () => {
  it('uses a CommonJS preload file for packaged Electron', () => {
    const preloadPath = path.join(process.cwd(), 'src/preload/preload.cts');
    const mainSource = readFileSync(path.join(process.cwd(), 'src/main/main.ts'), 'utf8');

    expect(existsSync(preloadPath)).toBe(true);
    expect(readFileSync(preloadPath, 'utf8')).toContain("require('electron')");
    expect(mainSource).toContain('../preload/preload.cjs');
  });
});
