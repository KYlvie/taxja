import { Capacitor } from '@capacitor/core';
import { Camera, CameraResultType, CameraSource } from '@capacitor/camera';
import { FilePicker, type PickedFile } from '@capawesome/capacitor-file-picker';
import { Directory, Filesystem } from '@capacitor/filesystem';
import { Share } from '@capacitor/share';
import { isNativeApp } from './runtime';

const sanitizeFileName = (fileName: string) =>
  fileName.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '-').replace(/\s+/g, ' ').trim();

const blobToBase64 = async (blob: Blob): Promise<string> => {
  const reader = new FileReader();

  return new Promise((resolve, reject) => {
    reader.onerror = () => reject(reader.error);
    reader.onload = () => {
      const result = reader.result;

      if (typeof result !== 'string') {
        reject(new Error('Failed to read file.'));
        return;
      }

      const [, base64 = ''] = result.split(',');
      resolve(base64);
    };

    reader.readAsDataURL(blob);
  });
};

const base64ToBlob = (data: string, mimeType: string): Blob => {
  const byteCharacters = atob(data);
  const bytes = new Uint8Array(byteCharacters.length);

  for (let index = 0; index < byteCharacters.length; index += 1) {
    bytes[index] = byteCharacters.charCodeAt(index);
  }

  return new Blob([bytes.buffer], { type: mimeType });
};

const blobFromNativePath = async (path: string): Promise<Blob> => {
  const fileUrl = Capacitor.convertFileSrc(path);
  const response = await fetch(fileUrl);

  if (!response.ok) {
    throw new Error('Failed to read selected file.');
  }

  return response.blob();
};

const pickedFileToFile = async (pickedFile: PickedFile): Promise<File> => {
  if (pickedFile.blob) {
    return new File([pickedFile.blob], pickedFile.name, {
      type: pickedFile.mimeType,
      lastModified: pickedFile.modifiedAt ?? Date.now(),
    });
  }

  if (pickedFile.path) {
    const blob = await blobFromNativePath(pickedFile.path);
    return new File([blob], pickedFile.name, {
      type: pickedFile.mimeType || blob.type,
      lastModified: pickedFile.modifiedAt ?? Date.now(),
    });
  }

  if (pickedFile.data) {
    const blob = base64ToBlob(pickedFile.data, pickedFile.mimeType);
    return new File([blob], pickedFile.name, {
      type: pickedFile.mimeType,
      lastModified: pickedFile.modifiedAt ?? Date.now(),
    });
  }

  throw new Error('No readable file data returned by the device.');
};

export const pickNativeFiles = async (types: string[]): Promise<File[]> => {
  const result = await FilePicker.pickFiles({ types, limit: 0 });
  return Promise.all(result.files.map((pickedFile) => pickedFileToFile(pickedFile)));
};

export const pickNativeSingleFile = async (types: string[]): Promise<File | null> => {
  const files = await pickNativeFiles(types);
  return files[0] ?? null;
};

export const capturePhotoAsFile = async (): Promise<File | null> => {
  const photo = await Camera.getPhoto({
    quality: 90,
    resultType: CameraResultType.Uri,
    source: CameraSource.Camera,
    saveToGallery: false,
    correctOrientation: true,
  });

  if (!photo.webPath) {
    return null;
  }

  const response = await fetch(photo.webPath);
  const blob = await response.blob();
  const extension = (photo.format || 'jpeg').toLowerCase();
  const fileName = `taxja-scan-${Date.now()}.${extension}`;

  return new File([blob], fileName, {
    type: blob.type || `image/${extension}`,
    lastModified: Date.now(),
  });
};

export const saveBlobWithNativeShare = async (
  blob: Blob,
  fileName: string,
  dialogTitle?: string
): Promise<void> => {
  if (!isNativeApp()) {
    const url = window.URL.createObjectURL(blob);
    const anchor = window.document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    window.document.body.appendChild(anchor);
    anchor.click();
    window.URL.revokeObjectURL(url);
    window.document.body.removeChild(anchor);
    return;
  }

  const safeName = sanitizeFileName(fileName || `taxja-export-${Date.now()}`);
  const filePath = `exports/${Date.now()}-${safeName}`;
  const base64 = await blobToBase64(blob);
  const writeResult = await Filesystem.writeFile({
    path: filePath,
    data: base64,
    directory: Directory.Cache,
    recursive: true,
  });

  const canShare = await Share.canShare();
  if (canShare.value) {
    await Share.share({
      title: dialogTitle || safeName,
      dialogTitle: dialogTitle || safeName,
      files: [writeResult.uri],
    });
  }
};

export const supportsNativeFileActions = (): boolean => isNativeApp();
