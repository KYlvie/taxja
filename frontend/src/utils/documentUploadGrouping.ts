export type UploadEntry = {
  displayFile: File;
  sourceFiles: File[];
  uploadMode: 'single' | 'image_group';
  pageCount: number;
};

export const isImageFile = (file: File) => file.type.startsWith('image/');

const createGroupedDisplayFile = (files: File[]): File => {
  const timestamp = Date.now();
  const pageCount = files.length;
  const name = `taxja-scan-${timestamp}-${pageCount}-pages.pdf`;

  // This File is only used for UI metadata like name and size.
  return new File(files, name, {
    type: 'application/pdf',
    lastModified: timestamp,
  });
};

/**
 * Check whether the given file list should enter the staging area.
 * Staging is triggered when ANY image files are dropped — even a single image
 * goes to staging so the user can add more images before uploading.
 */
export const shouldStageFiles = (files: File[]): boolean =>
  files.length >= 1 && files.every(isImageFile);

/**
 * Sort files by name (covers most phone camera naming conventions
 * like IMG_20250318_001.jpg which embed timestamps).
 */
export const sortFilesByName = (files: File[]): File[] =>
  [...files].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));

/**
 * Build a single merged upload entry from an ordered list of image files.
 */
export const buildMergedEntry = (files: File[]): UploadEntry => ({
  displayFile: createGroupedDisplayFile(files),
  sourceFiles: files,
  uploadMode: 'image_group',
  pageCount: files.length,
});

/**
 * Build individual upload entries (one per file).
 */
export const buildIndividualEntries = (files: File[]): UploadEntry[] =>
  files.map((file) => ({
    displayFile: file,
    sourceFiles: [file],
    uploadMode: 'single' as const,
    pageCount: 1,
  }));

/**
 * Original auto-grouping logic — used for non-staging paths
 * (single file, mixed file types, etc.)
 */
export const buildUploadEntries = (files: File[]): UploadEntry[] => {
  // Single files or mixed types: upload individually
  return files.map((file) => ({
    displayFile: file,
    sourceFiles: [file],
    uploadMode: 'single' as const,
    pageCount: 1,
  }));
};
