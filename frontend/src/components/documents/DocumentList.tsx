import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { documentService } from '../../services/documentService';
import { useDocumentStore } from '../../stores/documentStore';
import { Document, DocumentType } from '../../types/document';
import './DocumentList.css';

interface DocumentListProps {
  onDocumentSelect?: (document: Document) => void;
}

const DocumentList: React.FC<DocumentListProps> = ({ onDocumentSelect }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const {
    documents,
    total,
    loading,
    filters,
    setDocuments,
    setLoading,
    setFilters,
  } = useDocumentStore();

  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [page, setPage] = useState(1);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const pageSize = 20;

  useEffect(() => {
    loadDocuments();
  }, [filters, page]);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      const result = await documentService.getDocuments(filters, page, pageSize);
      setDocuments(result.documents, result.total);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: string, value: any) => {
    setFilters({ ...filters, [key]: value });
    setPage(1);
  };

  const handleSearch = (search: string) => {
    setFilters({ ...filters, search });
    setPage(1);
  };

  const handleDocumentClick = (document: Document) => {
    if (onDocumentSelect) {
      onDocumentSelect(document);
    } else {
      navigate(`/documents/${document.id}`);
    }
  };

  const handleDownload = async (document: Document, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const blob = await documentService.downloadDocument(document.id);
      const url = window.URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      a.download = document.file_name;
      window.document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      window.document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to download document:', error);
    }
  };

  const handleDelete = async (document: Document, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(t('documents.confirmDelete'))) return;
    setDeletingId(document.id);
    try {
      await documentService.deleteDocument(document.id);
      loadDocuments();
      // Show success message
      alert(t('documents.deleteSuccess') || 'Document deleted successfully');
    } catch (error: any) {
      console.error('Failed to delete document:', error);
      // Show error message to user
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to delete document';
      alert(t('documents.deleteError') || `Error: ${errorMessage}`);
    } finally {
      setDeletingId(null);
    }
  };

  const getDocumentTypeLabel = (type: DocumentType) => {
    return t(`documents.types.${type}`);
  };

  const getDocumentIcon = (document: Document) => {
    if (document.mime_type.startsWith('image/')) return '🖼️';
    if (document.mime_type === 'application/pdf') return '📄';
    return '📎';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="document-list">
      <div className="list-header">
        <div className="search-bar">
          <input
            type="text"
            placeholder={t('documents.search.placeholder')}
            value={filters.search || ''}
            onChange={(e) => handleSearch(e.target.value)}
          />
          <button className="search-icon">🔍</button>
        </div>

        <div className="view-toggle">
          <button
            className={viewMode === 'grid' ? 'active' : ''}
            onClick={() => setViewMode('grid')}
            title={t('documents.view.grid')}
          >
            ⊞
          </button>
          <button
            className={viewMode === 'list' ? 'active' : ''}
            onClick={() => setViewMode('list')}
            title={t('documents.view.list')}
          >
            ☰
          </button>
        </div>
      </div>

      <div className="list-filters">
        <input
          type="date"
          value={filters.start_date || ''}
          onChange={(e) => handleFilterChange('start_date', e.target.value)}
          placeholder={t('documents.filters.startDate')}
        />

        <input
          type="date"
          value={filters.end_date || ''}
          onChange={(e) => handleFilterChange('end_date', e.target.value)}
          placeholder={t('documents.filters.endDate')}
        />

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={filters.needs_review || false}
            onChange={(e) =>
              handleFilterChange('needs_review', e.target.checked || undefined)
            }
          />
          {t('documents.filters.needsReview')}
        </label>

        {Object.keys(filters).length > 0 && (
          <button
            className="btn-link"
            onClick={() => {
              setFilters({});
              setPage(1);
            }}
          >
            {t('documents.filters.clear')}
          </button>
        )}
      </div>

      {loading ? (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>{t('common.loading')}</p>
        </div>
      ) : documents.length === 0 ? (
        <div className="empty-state">
          <p>{t('documents.empty')}</p>
        </div>
      ) : (
        <>
          <div className={`documents-${viewMode}`}>
            {documents.map((document) => (
              <div
                key={document.id}
                className={`document-item ${
                  document.needs_review ? 'needs-review' : ''
                }`}
                onClick={() => handleDocumentClick(document)}
              >
                {viewMode === 'grid' ? (
                  <>
                    <div className="document-thumbnail">
                      {document.mime_type.startsWith('image/') ? (
                        <img
                          src={documentService.getDocumentUrl(document.id)}
                          alt={document.file_name}
                        />
                      ) : (
                        <div className="document-icon">
                          {getDocumentIcon(document)}
                        </div>
                      )}
                      {document.needs_review && (
                        <div className="review-badge">⚠️</div>
                      )}
                    </div>
                    <div className="document-info">
                      <div className="document-name">{document.file_name}</div>
                      <div className="document-meta">
                        <span className="document-type">
                          {getDocumentTypeLabel(document.document_type)}
                        </span>
                        <span className="document-date">
                          {formatDate(document.created_at)}
                        </span>
                      </div>
                    </div>
                    <div className="document-actions">
                      <button
                        className="download-btn"
                        onClick={(e) => handleDownload(document, e)}
                        title={t('documents.download')}
                      >
                        ⬇️
                      </button>
                      <button
                        className="delete-btn"
                        onClick={(e) => handleDelete(document, e)}
                        disabled={deletingId === document.id}
                        title={t('common.delete')}
                      >
                        🗑️
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="document-icon-small">
                      {getDocumentIcon(document)}
                    </div>
                    <div className="document-details">
                      <div className="document-name">{document.file_name}</div>
                      <div className="document-meta">
                        <span>{getDocumentTypeLabel(document.document_type)}</span>
                        <span>{formatDate(document.created_at)}</span>
                        <span>{formatFileSize(document.file_size)}</span>
                        {document.confidence_score && (
                          <span>
                            {t('documents.confidence')}:{' '}
                            {(document.confidence_score * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                    </div>
                    {document.needs_review && (
                      <div className="review-badge-list">
                        ⚠️ {t('documents.needsReview')}
                      </div>
                    )}
                    <button
                      className="download-btn"
                      onClick={(e) => handleDownload(document, e)}
                      title={t('documents.download')}
                    >
                      ⬇️
                    </button>
                    <button
                      className="delete-btn"
                      onClick={(e) => handleDelete(document, e)}
                      disabled={deletingId === document.id}
                      title={t('common.delete')}
                    >
                      🗑️
                    </button>
                  </>
                )}
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="pagination">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
              >
                ← {t('common.previous')}
              </button>
              <span>
                {t('common.page')} {page} {t('common.of')} {totalPages}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page === totalPages}
              >
                {t('common.next')} →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default DocumentList;
