import { describe, it, expect, beforeAll } from '@jest/globals';
import * as fs from 'fs';
import * as path from 'path';

describe('Icon Loading', () => {
  const iconPath = path.join(__dirname, '../assets/icon.png');

  it('should have icon.png file in assets directory', () => {
    expect(fs.existsSync(iconPath)).toBe(true);
  });

  it('icon.png should be a valid PNG file', () => {
    if (fs.existsSync(iconPath)) {
      const buffer = fs.readFileSync(iconPath);
      // PNG files start with these bytes
      const pngSignature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
      const fileSignature = buffer.slice(0, 8);
      expect(fileSignature.equals(pngSignature)).toBe(true);
    }
  });
});
