import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LineItem } from '../../types/document';
import './ReceiptItemChecker.css';

interface ReceiptItemCheckerProps {
  items: LineItem[];
  onItemsChange: (items: LineItem[]) => void;
  userType: string;
}

const ReceiptItemChecker: React.FC<ReceiptItemCheckerProps> = ({
  items,
  onItemsChange,
  userType,
}) => {
  const { t } = useTranslation();
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const handleToggleDeductible = (index: number) => {
    const updatedItems = [...items];
    updatedItems[index] = {
      ...updatedItems[index],
      is_deductible: !updatedItems[index].is_deductible,
    };
    onItemsChange(updatedItems);
  };

  const handleReasonChange = (index: number, reason: string) => {
    const updatedItems = [...items];
    updatedItems[index] = {
      ...updatedItems[index],
      deduction_reason: reason,
    };
    onItemsChange(updatedItems);
  };

  const calculateTotals = () => {
    const total = items.reduce((sum, item) => sum + item.amount, 0);
    const deductible = items
      .filter((item) => item.is_deductible)
      .reduce((sum, item) => sum + item.amount, 0);
    const nonDeductible = total - deductible;

    return { total, deductible, nonDeductible };
  };

  const totals = calculateTotals();

  const getDeductibilityIcon = (item: LineItem) => {
    if (item.is_deductible === undefined) return '❓';
    return item.is_deductible ? '✅' : '❌';
  };

  const getDeductibilityClass = (item: LineItem) => {
    if (item.is_deductible === undefined) return 'unknown';
    return item.is_deductible ? 'deductible' : 'non-deductible';
  };

  return (
    <div className="receipt-item-checker">
      <div className="checker-header">
        <h3>{t('documents.itemChecker.title')}</h3>
        <p className="checker-hint">
          {t('documents.itemChecker.hint', { userType })}
        </p>
      </div>

      <div className="items-list">
        {items.map((item, index) => (
          <div
            key={index}
            className={`item-row ${getDeductibilityClass(item)}`}
          >
            <div className="item-main">
              <button
                className="deductibility-toggle"
                onClick={() => handleToggleDeductible(index)}
                title={t('documents.itemChecker.toggleDeductible')}
              >
                {getDeductibilityIcon(item)}
              </button>

              <div className="item-info">
                <div className="item-description">{item.description}</div>
                {item.quantity && (
                  <div className="item-quantity">
                    {t('documents.itemChecker.quantity')}: {item.quantity}
                  </div>
                )}
              </div>

              <div className="item-amount">€{item.amount.toFixed(2)}</div>
            </div>

            {item.deduction_reason && (
              <div className="item-reason">
                <span className="reason-label">
                  {t('documents.itemChecker.reason')}:
                </span>
                <span className="reason-text">{item.deduction_reason}</span>
              </div>
            )}

            {editingIndex === index && (
              <div className="item-edit">
                <textarea
                  value={item.deduction_reason || ''}
                  onChange={(e) => handleReasonChange(index, e.target.value)}
                  placeholder={t('documents.itemChecker.reasonPlaceholder')}
                  rows={2}
                />
                <button
                  className="btn-small"
                  onClick={() => setEditingIndex(null)}
                >
                  {t('common.done')}
                </button>
              </div>
            )}

            {editingIndex !== index && (
              <button
                className="btn-link"
                onClick={() => setEditingIndex(index)}
              >
                {item.deduction_reason
                  ? t('documents.itemChecker.editReason')
                  : t('documents.itemChecker.addReason')}
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="totals-summary">
        <div className="total-row">
          <span>{t('documents.itemChecker.totalAmount')}:</span>
          <span className="total-value">€{totals.total.toFixed(2)}</span>
        </div>
        <div className="total-row deductible">
          <span>{t('documents.itemChecker.deductibleAmount')}:</span>
          <span className="total-value">€{totals.deductible.toFixed(2)}</span>
        </div>
        <div className="total-row non-deductible">
          <span>{t('documents.itemChecker.nonDeductibleAmount')}:</span>
          <span className="total-value">
            €{totals.nonDeductible.toFixed(2)}
          </span>
        </div>
      </div>

      <div className="checker-legend">
        <div className="legend-item">
          <span className="legend-icon">✅</span>
          <span>{t('documents.itemChecker.legend.deductible')}</span>
        </div>
        <div className="legend-item">
          <span className="legend-icon">❌</span>
          <span>{t('documents.itemChecker.legend.nonDeductible')}</span>
        </div>
        <div className="legend-item">
          <span className="legend-icon">❓</span>
          <span>{t('documents.itemChecker.legend.unknown')}</span>
        </div>
      </div>

      <div className="checker-info">
        <p>
          ℹ️ {t('documents.itemChecker.info')}
        </p>
      </div>
    </div>
  );
};

export default ReceiptItemChecker;
