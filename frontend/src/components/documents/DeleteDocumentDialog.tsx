import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { useThemeStore } from '../../stores/themeStore';
import RobotMascot from '../common/RobotMascot';
import { documentService } from '../../services/documentService';
import { getLocaleForLanguage } from '../../utils/locale';
import '../common/ConfirmDialog.css';
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

const ROBOT_SIZE = 320;

const DeleteDocumentDialog = ({
  documentId,
  onConfirm,
  onCancel,
}: DeleteDocumentDialogProps) => {
  const { t, i18n } = useTranslation();
  const theme = useThemeStore((s) => s.theme);
  const isCyber = theme === 'cyber';

  const [relatedData, setRelatedData] = useState<RelatedData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedMode, setSelectedMode] = useState<'document_only' | 'with_data'>('document_only');
  const [showBubble, setShowBubble] = useState(false);
  const [isTyping, setIsTyping] = useState(true);
  const [showButtons, setShowButtons] = useState(false);

  useEffect(() => {
    if (isCyber) {
      setShowBubble(false);
      setIsTyping(true);
      setShowButtons(false);
      const bubbleTimer = window.setTimeout(() => setShowBubble(true), 220);
      return () => window.clearTimeout(bubbleTimer);
    } else {
      setShowBubble(true);
      setIsTyping(false);
      setShowButtons(true);
    }
  }, [documentId, isCyber]);

  useEffect(() => {
    void loadRelatedData();
  }, [documentId]);

  useEffect(() => {
    if (!isCyber) {
      // Classic mode: show immediately once loaded
      if (!loading) {
        setIsTyping(false);
        setShowButtons(true);
      }
      return undefined;
    }

    if (!showBubble) return undefined;
    if (loading) {
      setIsTyping(true);
      setShowButtons(false);
      return undefined;
    }

    setIsTyping(true);
    setShowButtons(false);
    const typingTimer = window.setTimeout(() => {
      setIsTyping(false);
      setShowButtons(true);
    }, 420);
    return () => window.clearTimeout(typingTimer);
  }, [loading, showBubble, isCyber]);

  const loadRelatedData = async () => {
    setLoading(true);
    try {
      const data = await documentService.getDocumentRelatedData(documentId);
      setRelatedData(data);
    } catch (error) {
      console.error('Failed to load related data:', error);
      setRelatedData(null);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat(getLocaleForLanguage(i18n.language), {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);

  const formatDate = (dateString: string) =>
    new Date(dateString).toLocaleDateString(getLocaleForLanguage(i18n.language));

  const handleConfirm = () => {
    onConfirm(selectedMode);
  };

  const introText = relatedData?.has_related_data
    ? t(
        'documents.deleteDialog.hasRelatedData',
        'This document is linked to other records. Choose how much should be removed.'
      )
    : t(
        'documents.deleteDialog.recommendation',
        'Choose whether to delete only the document file or every linked record as well.'
      );

  if (typeof document === 'undefined') return null;

  /* ── Shared content (used by both modes) ── */
  const dialogContent = (
    <>
      {isTyping ? (
        <div className="ddd-loading">
          {isCyber ? (
            <div className="cfd-typing-dots" aria-hidden="true">
              <span /><span /><span />
            </div>
          ) : (
            <div className="ddd-loading-text">{t('common.loading', 'Loading...')}</div>
          )}
        </div>
      ) : (
        <div className={`ddd-content ${isCyber ? '' : 'ddd-content--standard'}`}>
          <p className={`ddd-lead ${isCyber ? '' : 'ddd-lead--standard'}`}>{introText}</p>

          {relatedData?.has_related_data && (
            <div className={`ddd-related ${isCyber ? '' : 'ddd-related--standard'}`}>
              {relatedData.related_data.property && (
                <div className="ddd-related-item">
                  <strong>{t('documents.deleteDialog.property')}:</strong>
                  <span>{relatedData.related_data.property.address}</span>
                  <span className="ddd-meta">
                    {formatCurrency(relatedData.related_data.property.purchase_price)} •{' '}
                    {formatDate(relatedData.related_data.property.purchase_date)}
                  </span>
                </div>
              )}

              {relatedData.related_data.linked_mietvertrag && (
                <div className="ddd-related-item">
                  <strong>
                    {t('documents.deleteDialog.linkedMietvertrag', 'Linked rental contract')}:
                  </strong>
                  <span>{relatedData.related_data.linked_mietvertrag.file_name}</span>
                  <span className="ddd-meta ddd-meta--warn">
                    {t(
                      'documents.deleteDialog.linkedMietvertragWarn',
                      "Deleting everything will also remove this rental contract and its recurring transactions."
                    )}
                  </span>
                </div>
              )}

              {relatedData.related_data.recurring_transactions &&
                relatedData.related_data.recurring_transactions.length > 0 && (
                  <div className="ddd-related-item">
                    <strong>
                      {t('documents.deleteDialog.recurringTransactions', 'Recurring transactions')}{' '}
                      ({relatedData.related_data.recurring_transactions.length}):
                    </strong>
                    {relatedData.related_data.recurring_transactions.map((transaction) => (
                      <div key={transaction.id} className="ddd-txn">
                        <span>{transaction.description}</span>
                        <span>
                          {formatCurrency(transaction.amount)} • {transaction.frequency}
                          {transaction.is_active ? '' : ` (${t('common.expired', 'Expired')})`}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

              {relatedData.related_data.recurring_transaction && (
                <div className="ddd-related-item">
                  <strong>{t('documents.deleteDialog.recurringTransaction')}:</strong>
                  <span>{relatedData.related_data.recurring_transaction.description}</span>
                  <span className="ddd-meta">
                    {formatCurrency(relatedData.related_data.recurring_transaction.amount)} •{' '}
                    {relatedData.related_data.recurring_transaction.frequency}
                  </span>
                </div>
              )}

              {relatedData.related_data.transactions &&
                relatedData.related_data.transactions.length > 0 && (
                  <div className="ddd-related-item">
                    <strong>
                      {t('documents.deleteDialog.transactions')} (
                      {relatedData.related_data.transactions.length}):
                    </strong>
                    {relatedData.related_data.transactions.slice(0, 3).map((transaction) => (
                      <div key={transaction.id} className="ddd-txn">
                        <span>{transaction.description}</span>
                        <span>{formatCurrency(transaction.amount)}</span>
                      </div>
                    ))}
                    {relatedData.related_data.transactions.length > 3 && (
                      <span className="ddd-meta">
                        +{relatedData.related_data.transactions.length - 3}{' '}
                        {t('common.more', 'more')}
                      </span>
                    )}
                  </div>
                )}
            </div>
          )}

          <div className={`ddd-options ${isCyber ? '' : 'ddd-options--standard'}`}>
            <label
              className={`ddd-option ${isCyber ? '' : 'ddd-option--std'} ${
                selectedMode === 'document_only' ? 'ddd-option--selected' : ''
              }`}
            >
              <input
                type="radio"
                name="deleteMode"
                value="document_only"
                checked={selectedMode === 'document_only'}
                onChange={() => setSelectedMode('document_only')}
              />
              <div>
                <div className={`ddd-option-title ${isCyber ? '' : 'ddd-option-title--std'}`}>
                  {t('documents.deleteDialog.documentOnly')}
                </div>
                <div className={`ddd-option-desc ${isCyber ? '' : 'ddd-option-desc--std'}`}>
                  {t('documents.deleteDialog.documentOnlyDesc')}
                </div>
              </div>
            </label>

            <label
              className={`ddd-option ${isCyber ? '' : 'ddd-option--std'} ddd-option--danger ${
                selectedMode === 'with_data' ? 'ddd-option--selected' : ''
              }`}
            >
              <input
                type="radio"
                name="deleteMode"
                value="with_data"
                checked={selectedMode === 'with_data'}
                onChange={() => setSelectedMode('with_data')}
              />
              <div>
                <div className={`ddd-option-title ${isCyber ? '' : 'ddd-option-title--std'}`}>
                  {t('documents.deleteDialog.withData')}
                </div>
                <div className={`ddd-option-desc ${isCyber ? '' : 'ddd-option-desc--std'}`}>
                  {t('documents.deleteDialog.withDataDesc')}
                </div>
              </div>
            </label>
          </div>

          {selectedMode === 'with_data' ? (
            <div className={`ddd-warn-box ${isCyber ? '' : 'ddd-warn-box--standard'}`}>
              {t('documents.deleteDialog.warning')}
            </div>
          ) : (
            relatedData?.has_related_data && (
              <div className={`ddd-info-box ${isCyber ? '' : 'ddd-info-box--standard'}`}>
                {t('documents.deleteDialog.recommendation')}
              </div>
            )
          )}
        </div>
      )}
    </>
  );

  /* ── Cyber mode: robot overlay ── */
  if (isCyber) {
    return createPortal(
      <div
        className="cfd-robot-overlay"
        onClick={onCancel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-document-dialog-title"
      >
        <div className="cfd-robot-scene ddd-robot-scene" onClick={(event) => event.stopPropagation()}>
          <div className="cfd-robot-container ddd-robot-container">
            <RobotMascot size={ROBOT_SIZE} />
          </div>

          {showBubble && (
            <div className="cfd-robot-bubble cfd-robot-bubble--danger ddd-robot-bubble">
              <div className="ddd-assistant-line">Taxja AI</div>
              <div className="cfd-robot-bubble-title" id="delete-document-dialog-title">
                {t('documents.deleteDialog.title')}
              </div>
              {dialogContent}
              <div className={`cfd-robot-actions${showButtons ? ' cfd-robot-actions--visible' : ''}`}>
                <button className="cfd-robot-btn cfd-robot-btn--cancel" onClick={onCancel}>
                  {t('documents.deleteDialog.cancel')}
                </button>
                <button
                  className="cfd-robot-btn cfd-robot-btn--confirm"
                  style={{ '--btn-color': selectedMode === 'with_data' ? '#dc2626' : '#7c3aed' } as React.CSSProperties}
                  onClick={handleConfirm}
                  disabled={!showButtons}
                >
                  {selectedMode === 'document_only'
                    ? t('documents.deleteDialog.confirmDocumentOnly')
                    : t('documents.deleteDialog.confirmWithData')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>,
      document.body
    );
  }

  /* ── Classic mode: standard modal ── */
  return createPortal(
    <div
      className="cfd-overlay"
      onClick={onCancel}
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-document-dialog-title"
    >
      <div className="cfd-modal cfd-modal--danger ddd-modal--standard" onClick={(event) => event.stopPropagation()}>
        <div className="cfd-modal-title" id="delete-document-dialog-title">
          {t('documents.deleteDialog.title')}
        </div>
        {dialogContent}
        <div className="cfd-modal-actions">
          <button className="cfd-modal-btn cfd-modal-btn--cancel" onClick={onCancel}>
            {t('documents.deleteDialog.cancel')}
          </button>
          <button
            className={`cfd-modal-btn cfd-modal-btn--confirm ${selectedMode === 'with_data' ? 'cfd-modal-btn--danger' : 'cfd-modal-btn--info'}`}
            onClick={handleConfirm}
            disabled={!showButtons}
          >
            {selectedMode === 'document_only'
              ? t('documents.deleteDialog.confirmDocumentOnly')
              : t('documents.deleteDialog.confirmWithData')}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default DeleteDocumentDialog;
