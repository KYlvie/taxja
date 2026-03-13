import React, { useState, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { documentService } from '../../services/documentService';
import { useDocumentStore } from '../../stores/documentStore';
import { UploadProgress } from '../../types/document';
import './DocumentUpload.css';

const DocumentUpload: React.FC = () => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploads, setUploads] = useState<UploadProgress[]>([]);
  const addDocument = useDocumentStore((state) => state.addDocument);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;

      const fileArray = Array.from(files);
      const newUploads: UploadProgress[] = fileArray.map((file) => ({
        file,
        progress: 0,
        status: 'pending',
      }));

      setUploads((prev) => [...prev, ...newUploads]);

      // Upload files sequentially
      for (let i = 0; i < fileArray.length; i++) {
        const file = fileArray[i];
        const uploadIndex = uploads.length + i;

        try {
          setUploads((prev) =>
            prev.map((upload, idx) =>
              idx === uploadIndex ? { ...upload, status: 'uploading' } : upload
            )
          );

          const document = await documentService.uploadDocument(
            file,
            (progress) => {
              setUploads((prev) =>
                prev.map((upload, idx) =>
                  idx === uploadIndex ? { ...upload, progress } : upload
                )
              );
            }
          );

          setUploads((prev) =>
            prev.map((upload, idx) =>
              idx === uploadIndex
                ? {
                    ...upload,
                    status: 'processing',
                    progress: 100,
                    document,
                  }
                : upload
            )
          );

          // Poll for OCR completion (max 3min, every 3s)
          const pollOCR = async (docId: number, maxAttempts = 60) => {
            for (let attempt = 0; attempt < maxAttempts; attempt++) {
              await new Promise((r) => setTimeout(r, 3000));
              try {
                const updated = await documentService.getDocument(docId);
                // OCR done: has result, has confidence, or has been processed (even if failed)
                const ocrDone =
                  updated.ocr_result ||
                  updated.confidence_score > 0 ||
                  (updated as any).processed_at;
                if (ocrDone) {
                  setUploads((prev) =>
                    prev.map((upload, idx) =>
                      idx === uploadIndex
                        ? { ...upload, status: 'completed', document: updated }
                        : upload
                    )
                  );
                  addDocument(updated);
                  return;
                }
              } catch {
                // ignore polling errors, keep trying
              }
            }
            // Timeout: mark completed with original data
            setUploads((prev) =>
              prev.map((upload, idx) =>
                idx === uploadIndex
                  ? { ...upload, status: 'completed' }
                  : upload
              )
            );
            addDocument(document);
          };

          pollOCR(document.id);
        } catch (error: any) {
          setUploads((prev) =>
            prev.map((upload, idx) =>
              idx === uploadIndex
                ? {
                    ...upload,
                    status: 'error',
                    error: error.response?.data?.detail || t('documents.upload.error'),
                  }
                : upload
            )
          );
        }
      }
    },
    [uploads.length, addDocument, t]
  );

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    handleFiles(files);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    // Reset input so same file can be selected again
    e.target.value = '';
  };

  const handleCameraCapture = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    e.target.value = '';
  };

  const clearCompleted = () => {
    setUploads((prev) =>
      prev.filter((upload) => upload.status !== 'completed')
    );
  };

  const retryFailed = (index: number) => {
    const upload = uploads[index];
    if (upload.status === 'error') {
      handleFiles(new DataTransfer().files);
      const dt = new DataTransfer();
      dt.items.add(upload.file);
      handleFiles(dt.files);
    }
  };

  return (
    <div className="document-upload">
      <div
        className={`upload-zone ${isDragging ? 'dragging' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <div className="upload-icon">📄</div>
        <h3>{t('documents.upload.title')}</h3>
        <p>{t('documents.upload.dragDrop')}</p>
        <p className="upload-hint">{t('documents.upload.formats')}</p>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,.pdf"
          multiple
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </div>

      <div className="upload-actions">
        <button
          className="btn btn-primary"
          onClick={() => fileInputRef.current?.click()}
        >
          📁 {t('documents.upload.selectFiles')}
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => cameraInputRef.current?.click()}
        >
          📷 {t('documents.upload.takePhoto')}
        </button>
        <input
          ref={cameraInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleCameraCapture}
          style={{ display: 'none' }}
        />
      </div>

      {uploads.length > 0 && (
        <div className="upload-progress-list">
          <div className="progress-header">
            <h4>{t('documents.upload.progress')}</h4>
            {uploads.some((u) => u.status === 'completed') && (
              <button className="btn-link" onClick={clearCompleted}>
                {t('documents.upload.clearCompleted')}
              </button>
            )}
          </div>

          {uploads.map((upload, index) => (
            <div key={index} className={`upload-item ${upload.status}`}>
              <div className="upload-item-info">
                <span className="file-name">{upload.file.name}</span>
                <span className="file-size">
                  {(upload.file.size / 1024).toFixed(1)} KB
                </span>
              </div>

              {upload.status === 'uploading' && (
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${upload.progress}%` }}
                  />
                </div>
              )}

              {upload.status === 'processing' && (
                <div className="status-message processing">
                  {t('documents.upload.processing')}
                </div>
              )}

              {upload.status === 'completed' && (
                <div className="status-message completed">
                  ✓ {t('documents.upload.completed')}
                </div>
              )}

              {upload.status === 'error' && (
                <div className="status-message error">
                  ✗ {upload.error}
                  <button
                    className="btn-link"
                    onClick={() => retryFailed(index)}
                  >
                    {t('documents.upload.retry')}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DocumentUpload;
