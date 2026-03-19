import { describe, expect, it } from 'vitest';
import {
  buildUploadEntries,
  buildMergedEntry,
  shouldStageFiles,
  sortFilesByName,
} from '../utils/documentUploadGrouping';

const createFile = (name: string, type: string, content = 'data') =>
  new File([content], name, { type });

describe('document upload grouping', () => {
  it('returns individual entries for multiple images (staging handles grouping now)', () => {
    const files = [
      createFile('page-1.jpg', 'image/jpeg'),
      createFile('page-2.jpg', 'image/jpeg'),
      createFile('page-3.png', 'image/png'),
    ];
    const entries = buildUploadEntries(files);

    expect(entries).toHaveLength(3);
    expect(entries.every((e) => e.uploadMode === 'single')).toBe(true);
  });

  it('keeps mixed selections as separate uploads', () => {
    const entries = buildUploadEntries([
      createFile('receipt.jpg', 'image/jpeg'),
      createFile('statement.pdf', 'application/pdf'),
    ]);

    expect(entries).toHaveLength(2);
    expect(entries.every((entry) => entry.uploadMode === 'single')).toBe(true);
  });

  it('keeps a single image as a normal upload', () => {
    const entries = buildUploadEntries([
      createFile('receipt.jpg', 'image/jpeg'),
    ]);

    expect(entries).toHaveLength(1);
    expect(entries[0].uploadMode).toBe('single');
    expect(entries[0].pageCount).toBe(1);
    expect(entries[0].displayFile.name).toBe('receipt.jpg');
  });

  it('shouldStageFiles returns true for 2+ images', () => {
    expect(shouldStageFiles([
      createFile('a.jpg', 'image/jpeg'),
      createFile('b.png', 'image/png'),
    ])).toBe(true);
  });

  it('shouldStageFiles returns true for single image', () => {
    expect(shouldStageFiles([createFile('a.jpg', 'image/jpeg')])).toBe(true);
  });

  it('shouldStageFiles returns false for mixed types', () => {
    expect(shouldStageFiles([
      createFile('a.jpg', 'image/jpeg'),
      createFile('b.pdf', 'application/pdf'),
    ])).toBe(false);
  });

  it('buildMergedEntry creates a grouped entry', () => {
    const files = [
      createFile('page-1.jpg', 'image/jpeg'),
      createFile('page-2.jpg', 'image/jpeg'),
    ];
    const entry = buildMergedEntry(files);

    expect(entry.uploadMode).toBe('image_group');
    expect(entry.pageCount).toBe(2);
    expect(entry.sourceFiles).toHaveLength(2);
    expect(entry.displayFile.name).toContain('pages.pdf');
    expect(entry.displayFile.type).toBe('application/pdf');
  });

  it('sortFilesByName sorts numerically', () => {
    const files = [
      createFile('IMG_20250318_003.jpg', 'image/jpeg'),
      createFile('IMG_20250318_001.jpg', 'image/jpeg'),
      createFile('IMG_20250318_002.jpg', 'image/jpeg'),
    ];
    const sorted = sortFilesByName(files);

    expect(sorted[0].name).toBe('IMG_20250318_001.jpg');
    expect(sorted[1].name).toBe('IMG_20250318_002.jpg');
    expect(sorted[2].name).toBe('IMG_20250318_003.jpg');
  });
});
