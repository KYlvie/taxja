import React from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { RecurringTransaction } from '../../types/recurring';
import './RecurringTransactionCard.css';

interface RecurringTransactionCardProps {
  transaction: RecurringTransaction;
  onPause: (id: number) => void;
  onResume: (id: number) => void;
  onEdit: (transaction: RecurringTransaction) => void;
  onDelete: (id: number) => void;
}

export const RecurringTransactionCard: React.FC<RecurringTransactionCardProps> = ({
  transaction,
  onPause,
  onResume,
  onEdit,
  onDelete,
}) => {
  const { t: _t } = useTranslation();
  const navigate = useNavigate();

  const getTypeLabel = (type: string) => {
    const typeMap: Record<string, string> = {
      'rental_income': '租金收入',
      'loan_interest': '贷款利息',
      'depreciation': '折旧',
      'other_income': '其他收入',
      'other_expense': '其他支出',
      'manual': '自定义'
    };
    return typeMap[type] || type;
  };

  const getFrequencyLabel = (frequency: string) => {
    const freqMap: Record<string, string> = {
      'daily': '每日',
      'weekly': '每周',
      'monthly': '每月',
      'quarterly': '每季度',
      'yearly': '每年'
    };
    return freqMap[frequency] || frequency;
  };

  return (
    <div className="recurring-card">
      <div className="card-header">
        <div className="card-content">
          <div className="card-title-row">
            <h3 className="card-title">{transaction.description}</h3>
            <span className={`status-badge ${
              transaction.is_active ? 'status-active' : 
              (transaction.end_date && new Date(transaction.end_date) < new Date()) ? 'status-stopped' : 'status-paused'
            }`}>
              {transaction.is_active ? '活跃' : 
               (transaction.end_date && new Date(transaction.end_date) < new Date()) ? '已停止' : '已暂停'}
            </span>
          </div>
          
          <div className="card-details">
            <div className="detail-item">
              <span className="detail-label">类型:</span>
              <span className="detail-value">{getTypeLabel(transaction.recurring_type)}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">金额:</span>
              <span className="amount-value">€{Number(transaction.amount).toFixed(2)}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">频率:</span>
              <span className="detail-value">{getFrequencyLabel(transaction.frequency)}</span>
            </div>
            {transaction.next_generation_date && (
              <div className="detail-item">
                <span className="detail-label">下次生成:</span>
                <span className="detail-value">
                  {new Date(transaction.next_generation_date).toLocaleDateString('zh-CN')}
                </span>
              </div>
            )}
            {transaction.last_generated_date && (
              <div className="detail-item">
                <span className="detail-label">上次生成:</span>
                <span className="detail-value">
                  {new Date(transaction.last_generated_date).toLocaleDateString('zh-CN')}
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="card-actions">
          {/* Contract-linked recurrings: pause/resume controlled by contract end_date, not manual */}
          {transaction.source_document_id ? null : transaction.is_active ? (
            <button
              onClick={() => onPause(transaction.id)}
              className="action-btn btn-pause"
            >
              ⏸️ 暂停
            </button>
          ) : transaction.end_date && new Date(transaction.end_date) < new Date() ? (
            /* Stopped (end_date in past): no resume button */
            null
          ) : (
            <button
              onClick={() => onResume(transaction.id)}
              className="action-btn btn-resume"
            >
              ▶️ 恢复
            </button>
          )}
          
          {transaction.source_document_id ? (
            <button
              onClick={() => navigate(`/documents/${transaction.source_document_id}`)}
              className="action-btn btn-edit"
              title="如需修改请前往关联合同"
            >
              📄 查看合同
            </button>
          ) : (
            <button
              onClick={() => onEdit(transaction)}
              className="action-btn btn-edit"
            >
              ✏️ 编辑
            </button>
          )}
          
          <button
            onClick={() => onDelete(transaction.id)}
            className="action-btn btn-delete"
          >
            🗑️ 删除
          </button>
        </div>
      </div>
    </div>
  );
};
