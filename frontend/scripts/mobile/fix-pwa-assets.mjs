import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..', '..');
const generatedIconsDir = path.join(projectRoot, 'icons');
const publicIconsDir = path.join(projectRoot, 'public', 'icons');
const manifestPath = path.join(projectRoot, 'public', 'manifest.webmanifest');

mkdirSync(publicIconsDir, { recursive: true });

if (existsSync(generatedIconsDir)) {
  for (const entry of readdirSync(generatedIconsDir, { withFileTypes: true })) {
    if (!entry.isFile()) {
      continue;
    }

    const sourcePath = path.join(generatedIconsDir, entry.name);
    const targetPath = path.join(publicIconsDir, entry.name);
    copyFileSync(sourcePath, targetPath);
  }
}

const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
const publicRoot = path.join(projectRoot, 'public');

manifest.icons = (manifest.icons ?? [])
  .map((icon) => {
    const fileName = path.basename(icon.src ?? '');
    if (!fileName) {
      return null;
    }

    const publicIconPath = path.join(publicIconsDir, fileName);
    if (!existsSync(publicIconPath)) {
      return null;
    }

    return {
      ...icon,
      src: `/icons/${fileName}`,
      type: 'image/webp',
    };
  })
  .filter(Boolean);

if (Array.isArray(manifest.screenshots)) {
  manifest.screenshots = manifest.screenshots.filter((shot) => existsSync(path.join(publicRoot, shot.src.replace(/^\//, ''))));
  if (manifest.screenshots.length === 0) {
    delete manifest.screenshots;
  }
}

if (Array.isArray(manifest.shortcuts)) {
  manifest.shortcuts = manifest.shortcuts
    .map((shortcut) => {
      if (!Array.isArray(shortcut.icons)) {
        return shortcut;
      }

      const icons = shortcut.icons.filter((icon) => existsSync(path.join(publicRoot, icon.src.replace(/^\//, ''))));
      if (icons.length === 0) {
        const { icons: _ignored, ...rest } = shortcut;
        return rest;
      }

      return { ...shortcut, icons };
    })
    .filter(Boolean);

  if (manifest.shortcuts.length === 0) {
    delete manifest.shortcuts;
  }
}

writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
