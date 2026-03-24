import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { documentService } from '../../services/documentService';

interface TaxImportDocumentPreviewProps {
  documentId?: number;
  embedded?: boolean;
}

const TaxImportDocumentPreview = ({ documentId, embedded = false }: TaxImportDocumentPreviewProps) => {
  const { t } = useTranslation();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [mimeType, setMimeType] = useState('');
  const [loading, setLoading] = useState(Boolean(documentId));
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!documentId) {
      setPreviewUrl(null);
      setMimeType('');
      setLoading(false);
      setError(false);
      return;
    }

    let objectUrl: string | null = null;
    let cancelled = false;

    setLoading(true);
    setError(false);

    void documentService.downloadDocument(documentId)
      .then((blob) => {
        if (cancelled) {
          return;
        }

        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
        setMimeType(blob.type || '');
      })
      .catch(() => {
        if (!cancelled) {
          setError(true);
          setPreviewUrl(null);
          setMimeType('');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [documentId]);

  const isPdf = mimeType === 'application/pdf';
  const isImage = mimeType.startsWith('image/');
  const previewLabel = t('documents.preview');
  const previewUnavailableLabel = t('documents.previewNotAvailable');
  const loadingLabel = t('common.loading');
  const previewBody = loading ? (
    <div className="tax-import-preview-fallback">{loadingLabel}</div>
  ) : error || !previewUrl ? (
    <div className="tax-import-preview-fallback">{previewUnavailableLabel}</div>
  ) : isPdf ? (
    <iframe
      src={previewUrl}
      title={previewLabel}
      className="tax-import-preview-frame"
    />
  ) : isImage ? (
    <img
      src={previewUrl}
      alt={previewLabel}
      className="tax-import-preview-image"
    />
  ) : (
    <div className="tax-import-preview-fallback">{previewUnavailableLabel}</div>
  );

  if (embedded) {
    return <div className="preview-container tax-import-preview-container">{previewBody}</div>;
  }

  return (
    <section className="bescheid-document-pane bescheid-surface">
      <div className="bescheid-document-header">
        <h4>{previewLabel}</h4>
      </div>
      <div className="bescheid-document-viewer">
        {previewBody}
      </div>
    </section>
  );
};

export default TaxImportDocumentPreview;
