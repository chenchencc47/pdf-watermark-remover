import { describe, expect, it } from 'vitest';
import config from './vite.config';

describe('Vite packaged Electron asset paths', () => {
  it('uses relative asset paths for file:// renderer loading', () => {
    expect(config).toMatchObject({ base: './' });
  });
});
