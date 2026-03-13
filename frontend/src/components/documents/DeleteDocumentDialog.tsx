import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { documentService } from '../../services/documentService';
import './DeleteDocumentDialog.css';

interface DeleteDocumentDialogProps {
  documentId: number;
  onConfirm: (deleteMode: 'document_only' | 'with_data') => void;
  onCancel: () => void;
}

interface RelatedData {
  document_id: number;
  document_type: string;
  has_related_data: boolean;
  related_data: {
    property?: {
      id: string;
      address: string;
      purchase_price: number;
      purchase_date: string;
    };
    transactions?: Array<{
      id: number;
      description: string;
      amount: number;
      date: string;
    }>;
    recurring_transaction?: {
      id: number;
      description: string;
      amount: number;
      frequency: string;
    };
  };
}

const DeleteDocumentDialog = ({
  documentId,
  onConfirm,
  onCancel,
}: DeleteDocumentDialogProps) => {
  const { t } = useTranslation();
  const [relatedData, setRelatedData] = useState<RelatedData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedMode, setSelectedMode] = useState<'document_only' | 'with_data'>('document_only');

  useEffect(() => {
    loadRelatedData();
  }, [documentId]);

  const loadRelatedData = async () => {
    try {
      const data = await documentService.getDocumentRelatedData(documentId);
      setRelatedData(data);
    } catch (error) {
      console.error('Failed to load related data:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('de-AT', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('de-AT');
  };

  const handleConfirm = () => {
    onConfirm(selectedMode);
  };

  if (loading) {
    return (
      <div className="modal-overlay">
        <div className="modal-content delete-dialog">
          <div className="loading-state">
            <div className="loading-spinner"></div>
            <p>{t('common.loading')}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content delete-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t('documents.deleteDialog.title')}</h2>
          <button className="modal-close" onClick={onCancel}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          {relatedData?.has_related_data && (
            <div className="related-data-section">
              <p className="warning-text">{t('documents.deleteDialog.hasRelatedData')}</p>
              
              {relatedData.related_data.property && (
                <div className="related-item">
                  <strong>{t('documents.deleteDialog.property')}:</strong>
                  <div className="related-details">
                    <div>{relatedData.related_data.property.address}</div>
                    <div className="related-meta">
                      {formatCurrency(relatedData.related_data.property.purchase_price)} • {formatDate(relatedData.related_data.property.purchase_date)}
                    </div>
                  </div>
                </div>
              )}

              {relatedData.related_data.recurring_transaction && (
                <div className="related-item">
                  <strong>{t('documents.deleteDialog.recurringTransaction')}:</strong>
                  <div className="related-details">
                    <div>{relatedData.related_data.recurring_transaction.description}</div>
                    <div className="related-meta">
                      {formatCurrency(relatedData.related_data.recurring_transaction.amount)} • {relatedData.related_data.recurring_transaction.frequency}
                    </div>
                  </div>
                </div>
              )}

              {relatedData.related_data.transactions && relatedData.related_data.transactions.length > 0 && (
                <div className="related-item">
                  <strong>{t('documents.deleteDialog.transactions')} ({relatedData.related_data.transactions.length}):</strong>
                  <div className="related-details">
                    {relatedData.related_data.transactions.slice(0, 3).map((txn) => (
                      <div key={txn.id} className="transaction-item">
                        <span>{txn.description}</span>
                        <span className="transaction-amount">{formatCurrency(txn.amount)}</span>
                      </div>
                    ))}
                    {relatedData.related_data.transactions.length > 3 && (
                      <div className="more-items">
                        +{relatedData.related_data.transactions.length - 3} {t('common.more')}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="delete-options">
            <h3>{t('documents.deleteDialog.deleteOptions')}</h3>

            <label className={`delete-option ${selectedMode === 'document_only' ? 'selected' : ''}`}>
              <input
                type="radio"
                name="deleteMode"
                value="document_only"
                checked={selectedMode === 'document_only'}
                onChange={() => setSelectedMode('document_only')}
              />
              <div className="option-content">
                <div className="option-title">
                  ✅ {t('documents.deleteDialog.documentOnly')}
                </div>
                <div className="option-description">
                  {t('documents.deleteDialog.documentOnlyDesc')}
                </div>
              </div>
            </label>

            <label className={`delete-option destructive ${selectedMode === 'with_data' ? 'selected' : ''}`}>
              <input
                type="radio"
                name="deleteMode"
                value="with_data"
                checked={selectedMode === 'with_data'}
                onChange={() => setSelectedMode('with_data')}
              />
              <div className="option-content">
                <div className="option-title">
                  🗑️ {t('documents.deleteDialog.withData')}
                </div>
                <div className="option-description">
                  {t('documents.deleteDialog.withDataDesc')}
                </div>
              </div>
            </label>
          </div>

          {selectedMode === 'with_data' && (
            <div className="warning-box">
              {t('documents.deleteDialog.warning')}
            </div>
          )}

          {selectedMode === 'document_only' && relatedData?.has_related_data && (
            <div className="info-box">
              {t('documents.deleteDialog.recommendation')}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onCancel}>
            {t('documents.deleteDialog.cancel')}
          </button>
          <button
            className={`btn ${selectedMode === 'with_data' ? 'btn-danger' : 'btn-primary'}`}
            onClick={handleConfirm}
          >
            {selectedMode === 'document_only'
              ? t('documents.deleteDialog.confirmDocumentOnly')
              : t('documents.deleteDialog.confirmWithData')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeleteDocumentDialog;
