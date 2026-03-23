import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { documentService } from '../../services/documentService';
import { getLocaleForLanguage } from '../../utils/locale';
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
    recurring_transactions?: Array<{
      id: number;
      description: string;
      amount: number;
      frequency: string;
      is_active: boolean;
    }>;
    linked_mietvertrag?: {
      document_id: number;
      file_name: string;
    };
  };
}

const DeleteDocumentDialog = ({
  documentId,
  onConfirm,
  onCancel,
}: DeleteDocumentDialogProps) => {
  const { t, i18n } = useTranslation();
  const [relatedData, setRelatedData] = useState<RelatedData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedMode, setSelectedMode] = useState<'document_only' | 'with_data'>('document_only');
  const [showContent, setShowContent] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [showButtons, setShowButtons] = useState(false);

  useEffect(() => {
    loadRelatedData();
  }, [documentId]);

  useEffect(() => {
    if (!loading) {
      setIsTyping(true);
      const t1 = setTimeout(() => {
        setIsTyping(false);
        setShowContent(true);
        const t2 = setTimeout(() => setShowButtons(true), 300);
        return () => clearTimeout(t2);
      }, 600);
      return () => clearTimeout(t1);
    }
  }, [loading]);

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
    return new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(getLocaleForLanguage(i18n.language));
  };

  const handleConfirm = () => {
    onConfirm(selectedMode);
  };

  if (loading) {
    return (
      <div className="cfd-overlay" role="dialog" aria-modal="true">
        <div className="cfd-dialog ddd-dialog">
          <div className="cfd-header">
            <div className="cfd-avatar">
              <span className="cfd-avatar-icon">🤖</span>
              <span className="cfd-avatar-pulse" />
            </div>
            <div className="cfd-header-info">
              <span className="cfd-assistant-name">Taxja AI</span>
              <span className="cfd-status">{t('ai.typing', 'Typing...')}</span>
            </div>
          </div>
          <div className="cfd-chat">
            <div className="cfd-bubble-row">
              <div className="cfd-bubble-avatar">🤖</div>
              <div className="cfd-bubble cfd-bubble--danger">
                <div className="cfd-typing-dots"><span /><span /><span /></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="cfd-overlay" onClick={onCancel} role="dialog" aria-modal="true">
      <div className="cfd-dialog ddd-dialog" onClick={(e) => e.stopPropagation()}>
        {/* AI Assistant header */}
        <div className="cfd-header">
          <div className="cfd-avatar">
            <span className="cfd-avatar-icon">🤖</span>
            <span className="cfd-avatar-pulse" />
          </div>
          <div className="cfd-header-info">
            <span className="cfd-assistant-name">Taxja AI</span>
            <span className="cfd-status">
              {isTyping ? t('ai.typing', 'Typing...') : t('ai.online', 'Online')}
            </span>
          </div>
        </div>

        {/* Chat area */}
        <div className="cfd-chat ddd-chat">
          <div className="cfd-bubble-row">
            <div className="cfd-bubble-avatar">🤖</div>
            <div className="cfd-bubble cfd-bubble--danger">
              {isTyping ? (
                <div className="cfd-typing-dots"><span /><span /><span /></div>
              ) : showContent ? (
                <div className="ddd-content">
                  <div className="cfd-bubble-title">🗑️ {t('documents.deleteDialog.title')}</div>

                  {relatedData?.has_related_data && (
                    <div className="ddd-related">
                      <p className="ddd-warning-text">{t('documents.deleteDialog.hasRelatedData')}</p>
                      {relatedData.related_data.property && (
                        <div className="ddd-related-item">
                          <strong>{t('documents.deleteDialog.property')}:</strong>
                          <span>{relatedData.related_data.property.address}</span>
                          <span className="ddd-meta">
                            {formatCurrency(relatedData.related_data.property.purchase_price)} • {formatDate(relatedData.related_data.property.purchase_date)}
                          </span>
                        </div>
                      )}
                      {relatedData.related_data.linked_mietvertrag && (
                        <div className="ddd-related-item">
                          <strong>{t('documents.deleteDialog.linkedMietvertrag', 'Linked Rental Contract')}:</strong>
                          <span>📄 {relatedData.related_data.linked_mietvertrag.file_name}</span>
                          <span className="ddd-meta ddd-meta--warn">
                            {t('documents.deleteDialog.linkedMietvertragWarn', 'Choosing \'Delete Everything\' will also delete this rental contract and its recurring transactions')}
                          </span>
                        </div>
                      )}
                      {relatedData.related_data.recurring_transactions && relatedData.related_data.recurring_transactions.length > 0 && (
                        <div className="ddd-related-item">
                          <strong>{t('documents.deleteDialog.recurringTransactions', 'Recurring Transactions')} ({relatedData.related_data.recurring_transactions.length}):</strong>
                          {relatedData.related_data.recurring_transactions.map((r) => (
                            <div key={r.id} className="ddd-txn">
                              <span>{r.description}</span>
                              <span>{formatCurrency(r.amount)} • {r.frequency}{r.is_active ? '' : ` (${t('common.expired', 'Expired')})`}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {relatedData.related_data.recurring_transaction && (
                        <div className="ddd-related-item">
                          <strong>{t('documents.deleteDialog.recurringTransaction')}:</strong>
                          <span>{relatedData.related_data.recurring_transaction.description}</span>
                          <span className="ddd-meta">
                            {formatCurrency(relatedData.related_data.recurring_transaction.amount)} • {relatedData.related_data.recurring_transaction.frequency}
                          </span>
                        </div>
                      )}
                      {relatedData.related_data.transactions && relatedData.related_data.transactions.length > 0 && (
                        <div className="ddd-related-item">
                          <strong>{t('documents.deleteDialog.transactions')} ({relatedData.related_data.transactions.length}):</strong>
                          {relatedData.related_data.transactions.slice(0, 3).map((txn) => (
                            <div key={txn.id} className="ddd-txn">
                              <span>{txn.description}</span>
                              <span>{formatCurrency(txn.amount)}</span>
                            </div>
                          ))}
                          {relatedData.related_data.transactions.length > 3 && (
                            <span className="ddd-meta">+{relatedData.related_data.transactions.length - 3} {t('common.more', 'more')}</span>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  <div className="ddd-options">
                    <label className={`ddd-option ${selectedMode === 'document_only' ? 'ddd-option--selected' : ''}`}>
                      <input type="radio" name="deleteMode" value="document_only"
                        checked={selectedMode === 'document_only'}
                        onChange={() => setSelectedMode('document_only')} />
                      <div>
                        <div className="ddd-option-title">✅ {t('documents.deleteDialog.documentOnly')}</div>
                        <div className="ddd-option-desc">{t('documents.deleteDialog.documentOnlyDesc')}</div>
                      </div>
                    </label>
                    <label className={`ddd-option ddd-option--danger ${selectedMode === 'with_data' ? 'ddd-option--selected' : ''}`}>
                      <input type="radio" name="deleteMode" value="with_data"
                        checked={selectedMode === 'with_data'}
                        onChange={() => setSelectedMode('with_data')} />
                      <div>
                        <div className="ddd-option-title">🗑️ {t('documents.deleteDialog.withData')}</div>
                        <div className="ddd-option-desc">{t('documents.deleteDialog.withDataDesc')}</div>
                      </div>
                    </label>
                  </div>

                  {selectedMode === 'with_data' && (
                    <div className="ddd-warn-box">⚠️ {t('documents.deleteDialog.warning')}</div>
                  )}
                  {selectedMode === 'document_only' && relatedData?.has_related_data && (
                    <div className="ddd-info-box">💡 {t('documents.deleteDialog.recommendation')}</div>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        </div>

        {/* Action buttons */}
        <div className={`cfd-actions${showButtons ? ' cfd-actions--visible' : ''}`}>
          <button className="cfd-btn cfd-btn--cancel" onClick={onCancel}>
            {t('documents.deleteDialog.cancel')}
          </button>
          <button
            className={`cfd-btn ${selectedMode === 'with_data' ? 'cfd-btn--danger' : 'cfd-btn--info'}`}
            onClick={handleConfirm}
            disabled={!showButtons}
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
