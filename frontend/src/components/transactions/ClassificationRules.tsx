import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import api from '../../services/api';
import { aiToast } from '../../stores/aiToastStore';
import { formatTransactionCategoryLabel } from '../../utils/formatTransactionCategoryLabel';
import { getLocaleForLanguage } from '../../utils/locale';
import ConfirmDialog from '../common/ConfirmDialog';
import './ClassificationRules.css';

interface ClassificationRule {
  id: number;
  normalized_description: string;
  original_description: string | null;
  txn_type: string;
  category: string;
  hit_count: number;
  confidence: number;
  rule_type: string;
  frozen: boolean;
  conflict_count: number;
  last_hit_at: string | null;
  created_at: string | null;
}

interface DeductibilityRule {
  id: number;
  normalized_description: string;
  original_description: string | null;
  expense_category: string;
  is_deductible: boolean;
  reason: string | null;
  hit_count: number;
  last_hit_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

type DeleteKind = 'classification' | 'deductibility';
type SectionKey = 'classification' | 'automation' | 'deductibility';

type DeleteTarget = {
  kind: DeleteKind;
  ids: number[];
} | null;

const EMPTY_VALUE = '-';
const PAGE_SIZE = 10;

const formatDateTime = (value: string | null, language = 'de'): string => {
  if (!value) {
    return EMPTY_VALUE;
  }

  const normalizedValue = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
    ? value
    : `${value}Z`;
  const parsed = new Date(normalizedValue);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString(getLocaleForLanguage(language), {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const toggleId = (ids: number[], id: number): number[] => (
  ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id]
);

const matchesText = (search: string, ...values: Array<string | null | undefined>) => {
  if (!search) {
    return true;
  }

  const normalizedSearch = search.toLowerCase();
  return values.some((value) => value?.toLowerCase().includes(normalizedSearch));
};

const hasMeaningfulVariation = (values: Array<string | null | undefined>) => {
  const normalizedValues = values
    .map((value) => value?.trim())
    .filter((value): value is string => Boolean(value));

  if (normalizedValues.length <= 1) {
    return false;
  }

  return new Set(normalizedValues).size > 1;
};

const ClassificationRules = () => {
  const { t, i18n } = useTranslation();
  const [rules, setRules] = useState<ClassificationRule[]>([]);
  const [deductibilityRules, setDeductibilityRules] = useState<DeductibilityRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<DeleteTarget>(null);
  const [pendingDelete, setPendingDelete] = useState<DeleteTarget>(null);
  const [selectedClassificationIds, setSelectedClassificationIds] = useState<number[]>([]);
  const [selectedAutomationIds, setSelectedAutomationIds] = useState<number[]>([]);
  const [selectedDeductibilityIds, setSelectedDeductibilityIds] = useState<number[]>([]);
  const [classificationPage, setClassificationPage] = useState(1);
  const [automationPage, setAutomationPage] = useState(1);
  const [deductibilityPage, setDeductibilityPage] = useState(1);
  const [classSearch, setClassSearch] = useState('');
  const [automationSearch, setAutomationSearch] = useState('');
  const [deductSearch, setDeductSearch] = useState('');
  const [expandedSections, setExpandedSections] = useState<Record<SectionKey, boolean>>({
    classification: false,
    automation: false,
    deductibility: false,
  });

  useEffect(() => {
    void fetchRules();
  }, []);

  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const [classificationRes, deductibilityRes] = await Promise.all([
        api.get('/classification-rules/'),
        api.get('/classification-rules/deductibility'),
      ]);
      const nextRules = classificationRes.data as ClassificationRule[];
      const nextDeductibilityRules = deductibilityRes.data as DeductibilityRule[];

      setRules(nextRules);
      setDeductibilityRules(nextDeductibilityRules);
      setSelectedClassificationIds((prev) =>
        prev.filter((id) => nextRules.some((rule) => rule.id === id && rule.rule_type !== 'auto'))
      );
      setSelectedAutomationIds((prev) =>
        prev.filter((id) => nextRules.some((rule) => rule.id === id && rule.rule_type === 'auto'))
      );
      setSelectedDeductibilityIds((prev) =>
        prev.filter((id) => nextDeductibilityRules.some((rule) => rule.id === id))
      );
    } catch {
      setError(t('classificationRules.fetchError', 'Failed to load rules'));
    } finally {
      setLoading(false);
    }
  };

  const getClassificationRuleReason = (rule: ClassificationRule): string => {
    if (rule.frozen) {
      return t(
        'classificationRules.reasonFrozen',
        'This rule was frozen after repeated conflicting corrections.'
      );
    }

    if (rule.conflict_count > 0) {
      return `${t(
        'classificationRules.reasonConflicted',
        'Conflicting corrections were detected for this description'
      )} (${rule.conflict_count}).`;
    }

    if (rule.rule_type === 'strict') {
      return t(
        'classificationRules.reasonStrict',
        'Saved from your manual category correction.'
      );
    }

    return t(
      'classificationRules.reasonAdaptive',
      'Learned adaptively from repeated confirmations.'
    );
  };

  const getAutomationRuleReason = (rule: ClassificationRule): string => {
    if (rule.frozen) {
      return t(
        'classificationRules.reasonAutomationFrozen',
        'This automatic handling rule was frozen after repeated conflicting corrections.'
      );
    }

    if (rule.conflict_count > 0) {
      return `${t(
        'classificationRules.reasonAutomationConflict',
        'The automatic handling rule was challenged by later corrections'
      )} (${rule.conflict_count}).`;
    }

    return t(
      'classificationRules.reasonAutomation',
      'Learned when you confirmed creating a bank statement transaction.'
    );
  };

  const handleDeleteRequest = (kind: DeleteKind, ids: number[]) => {
    if (ids.length === 0) return;
    setPendingDelete({ kind, ids });
  };

  const handleDeleteConfirm = async () => {
    const target = pendingDelete;
    setPendingDelete(null);
    if (!target) return;

    setDeleting(target);
    try {
      if (target.kind === 'classification') {
        await Promise.all(target.ids.map((id) => api.delete(`/classification-rules/${id}`)));
        setRules((prev) => prev.filter((rule) => !target.ids.includes(rule.id)));
        setSelectedClassificationIds((prev) =>
          prev.filter((id) => !target.ids.includes(id))
        );
        setSelectedAutomationIds((prev) =>
          prev.filter((id) => !target.ids.includes(id))
        );
      } else {
        await Promise.all(
          target.ids.map((id) => api.delete(`/classification-rules/deductibility/${id}`))
        );
        setDeductibilityRules((prev) => prev.filter((rule) => !target.ids.includes(rule.id)));
        setSelectedDeductibilityIds((prev) =>
          prev.filter((id) => !target.ids.includes(id))
        );
      }

      aiToast(
        target.ids.length > 1
          ? t('classificationRules.bulkDeleteSuccess', 'Selected rules deleted')
          : t('classificationRules.deleteSuccess', 'Rule deleted'),
        'success'
      );
    } catch {
      const message = target.ids.length > 1
        ? t('classificationRules.bulkDeleteError', 'Failed to delete selected rules')
        : t('classificationRules.deleteError', 'Failed to delete rule');
      setError(message);
      aiToast(message, 'error');
    } finally {
      setDeleting(null);
    }
  };

  const categoryRules = useMemo(
    () => rules.filter((rule) => rule.rule_type !== 'auto'),
    [rules]
  );
  const automationRules = useMemo(
    () => rules.filter((rule) => rule.rule_type === 'auto'),
    [rules]
  );

  const totalCount = categoryRules.length + automationRules.length + deductibilityRules.length;

  const filteredRules = useMemo(
    () => categoryRules.filter((rule) => matchesText(
      classSearch,
      rule.normalized_description,
      rule.original_description,
      rule.category
    )),
    [categoryRules, classSearch]
  );
  const filteredAutomationRules = useMemo(
    () => automationRules.filter((rule) => matchesText(
      automationSearch,
      rule.normalized_description,
      rule.original_description,
      rule.category
    )),
    [automationRules, automationSearch]
  );
  const filteredDeductibilityRules = useMemo(
    () => deductibilityRules.filter((rule) => matchesText(
      deductSearch,
      rule.normalized_description,
      rule.original_description,
      rule.expense_category
    )),
    [deductibilityRules, deductSearch]
  );

  const showClassificationReason = hasMeaningfulVariation(
    filteredRules.map((rule) => getClassificationRuleReason(rule))
  );
  const showClassificationConfidence = hasMeaningfulVariation(
    filteredRules.map((rule) => `${(rule.confidence * 100).toFixed(0)}%`)
  );
  const showClassificationStatus = hasMeaningfulVariation(
    filteredRules.map((rule) =>
      getStatusValue({
        frozen: rule.frozen,
        conflictCount: rule.conflict_count,
        isActive: !rule.frozen && rule.conflict_count === 0,
      })
    )
  );
  const showAutomationReason = hasMeaningfulVariation(
    filteredAutomationRules.map((rule) => getAutomationRuleReason(rule))
  );
  const showAutomationConfidence = hasMeaningfulVariation(
    filteredAutomationRules.map((rule) => `${(rule.confidence * 100).toFixed(0)}%`)
  );
  const showAutomationStatus = hasMeaningfulVariation(
    filteredAutomationRules.map((rule) =>
      getStatusValue({
        frozen: rule.frozen,
        conflictCount: rule.conflict_count,
        isActive: !rule.frozen && rule.conflict_count === 0,
      })
    )
  );
  const showDeductibilityReason = hasMeaningfulVariation(
    filteredDeductibilityRules.map((rule) => rule.reason || t('classificationRules.noReason', 'Manual override'))
  );
  const showDeductibilityConfidence = hasMeaningfulVariation(
    filteredDeductibilityRules.map(() => '100%')
  );
  const showDeductibilityStatus = hasMeaningfulVariation(
    filteredDeductibilityRules.map(() => getStatusValue({ isActive: true }))
  );

  const allClassificationIds = filteredRules.map((rule) => rule.id);
  const allAutomationIds = filteredAutomationRules.map((rule) => rule.id);
  const allDeductibilityIds = filteredDeductibilityRules.map((rule) => rule.id);
  const classificationPageCount = Math.max(1, Math.ceil(filteredRules.length / PAGE_SIZE));
  const automationPageCount = Math.max(1, Math.ceil(filteredAutomationRules.length / PAGE_SIZE));
  const deductibilityPageCount = Math.max(1, Math.ceil(filteredDeductibilityRules.length / PAGE_SIZE));
  const paginatedRules = filteredRules.slice(
    (classificationPage - 1) * PAGE_SIZE,
    classificationPage * PAGE_SIZE,
  );
  const paginatedAutomationRules = filteredAutomationRules.slice(
    (automationPage - 1) * PAGE_SIZE,
    automationPage * PAGE_SIZE,
  );
  const paginatedDeductibilityRules = filteredDeductibilityRules.slice(
    (deductibilityPage - 1) * PAGE_SIZE,
    deductibilityPage * PAGE_SIZE,
  );

  useEffect(() => {
    if (classificationPage > classificationPageCount) {
      setClassificationPage(classificationPageCount);
    }
  }, [classificationPage, classificationPageCount]);

  useEffect(() => {
    if (automationPage > automationPageCount) {
      setAutomationPage(automationPageCount);
    }
  }, [automationPage, automationPageCount]);

  useEffect(() => {
    if (deductibilityPage > deductibilityPageCount) {
      setDeductibilityPage(deductibilityPageCount);
    }
  }, [deductibilityPage, deductibilityPageCount]);

  const renderStatusCell = (options: {
    frozen?: boolean;
    conflictCount?: number;
    isActive?: boolean;
  }) => {
    if (options.frozen) {
      return (
        <span className="cr-badge frozen">
          {t('classificationRules.frozen', 'Frozen')}
        </span>
      );
    }

    if ((options.conflictCount || 0) > 0) {
      return (
        <span className="cr-badge conflict">
          {t('classificationRules.conflicts', 'Conflicts')}: {options.conflictCount}
        </span>
      );
    }

    if (options.isActive ?? true) {
      return (
        <span className="cr-badge active">
          {t('classificationRules.active', 'Active')}
        </span>
      );
    }

    return <span className="cr-muted">{EMPTY_VALUE}</span>;
  };

  function getStatusValue(options: {
    frozen?: boolean;
    conflictCount?: number;
    isActive?: boolean;
  }) {
    if (options.frozen) {
      return t('classificationRules.frozen', 'Frozen');
    }

    if ((options.conflictCount || 0) > 0) {
      return `${t('classificationRules.conflicts', 'Conflicts')}: ${options.conflictCount}`;
    }

    if (options.isActive ?? true) {
      return t('classificationRules.active', 'Active');
    }

    return EMPTY_VALUE;
  }

  const isDeletingRule = (kind: DeleteKind, id: number) => (
    deleting?.kind === kind && deleting.ids.includes(id)
  );

  const renderDeleteButton = (kind: DeleteKind, id: number) => (
    <button
      type="button"
      className="cr-delete-btn"
      onClick={() => handleDeleteRequest(kind, [id])}
      disabled={isDeletingRule(kind, id)}
      title={
        isDeletingRule(kind, id)
          ? t('classificationRules.deleting', 'Deleting...')
          : t('classificationRules.delete', 'Delete')
      }
      aria-label={
        isDeletingRule(kind, id)
          ? t('classificationRules.deleting', 'Deleting...')
          : t('classificationRules.delete', 'Delete')
      }
    >
      <Trash2 size={16} aria-hidden="true" />
    </button>
  );

  const renderSelectionControls = (
    kind: DeleteKind,
    selectedIds: number[],
    allIds: number[],
    onToggleAll: () => void,
    selectAllLabel: string,
  ) => (
    <div className="cr-section-actions">
      <label className="cr-select-all">
        <input
          type="checkbox"
          checked={allIds.length > 0 && selectedIds.length === allIds.length}
          onChange={onToggleAll}
          aria-label={selectAllLabel}
        />
        <span>{t('classificationRules.selectAll', 'Select all')}</span>
      </label>
      <button
        type="button"
        className="cr-bulk-delete-btn"
        disabled={selectedIds.length === 0 || deleting?.kind === kind}
        onClick={() => handleDeleteRequest(kind, selectedIds)}
      >
        {selectedIds.length > 0
          ? `${t('classificationRules.deleteSelected', 'Delete selected')} (${selectedIds.length})`
          : t('classificationRules.deleteSelected', 'Delete selected')}
      </button>
    </div>
  );

  const renderSectionEmpty = (message: string) => (
    <div className="cr-empty-state">
      <p className="cr-section-empty">{message}</p>
    </div>
  );

  const renderPagination = (
    currentPage: number,
    pageCount: number,
    onPageChange: (page: number) => void,
  ) => {
    if (pageCount <= 1) {
      return null;
    }

    const pages = Array.from({ length: pageCount }, (_, index) => index + 1);

    return (
      <div className="cr-pagination">
        <button
          type="button"
          className="cr-page-btn"
          disabled={currentPage === 1}
          onClick={() => onPageChange(currentPage - 1)}
        >
          {t('common.previous', 'Previous')}
        </button>
        <div className="cr-page-numbers">
          {pages.map((page) => (
            <button
              key={page}
              type="button"
              className={`cr-page-number ${page === currentPage ? 'active' : ''}`}
              onClick={() => onPageChange(page)}
              aria-current={page === currentPage ? 'page' : undefined}
            >
              {page}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="cr-page-btn"
          disabled={currentPage === pageCount}
          onClick={() => onPageChange(currentPage + 1)}
        >
          {t('common.next', 'Next')}
        </button>
      </div>
    );
  };

  const toggleSection = (section: SectionKey) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const renderSectionShell = (options: {
    section: SectionKey;
    title: string;
    subtitle: string;
    count: number;
    children: ReactNode;
  }) => {
    const isOpen = expandedSections[options.section];

    return (
      <section className={`cr-section ${isOpen ? 'open' : 'collapsed'}`}>
        <button
          type="button"
          className="cr-section-toggle"
          onClick={() => toggleSection(options.section)}
          aria-expanded={isOpen}
        >
          <div className="cr-section-toggle-copy">
            <h4>{options.title}</h4>
            <p className="cr-section-description">{options.subtitle}</p>
          </div>
          <div className="cr-section-toggle-meta">
            <span className="cr-section-count">{options.count}</span>
            {isOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </div>
        </button>
        {isOpen ? <div className="cr-section-body">{options.children}</div> : null}
      </section>
    );
  };

  if (loading) {
    return <div className="cr-loading">{t('common.loading')}</div>;
  }

  if (error) {
    return (
      <div className="cr-error">
        <p>{error}</p>
        <button type="button" onClick={() => void fetchRules()}>
          {t('common.retry')}
        </button>
      </div>
    );
  }

  return (
    <div className="classification-rules">
      <div className="cr-header cr-header--compact">
        <span className="cr-count">
          {totalCount} {t('classificationRules.rules', 'rules')}
        </span>
      </div>

      {renderSectionShell({
        section: 'classification',
        title: t('classificationRules.categorySectionTitle', 'Category rules'),
        subtitle: t(
          'classificationRules.categorySectionDescription',
          'Saved category corrections that help similar transactions land in the right bucket.'
        ),
        count: categoryRules.length,
        children: (
          <>
            <div className="cr-section-toolbar">
              {renderSelectionControls(
                'classification',
                selectedClassificationIds,
                allClassificationIds,
                () =>
                  setSelectedClassificationIds(
                    selectedClassificationIds.length === allClassificationIds.length
                      ? []
                      : allClassificationIds
                  ),
                t('classificationRules.selectAllCategory', 'Select all category rules')
              )}
            </div>
            <div className="cr-search">
              <input
                type="text"
                placeholder={t('classificationRules.searchPlaceholder', 'Search by description or category...')}
                value={classSearch}
                onChange={(e) => { setClassSearch(e.target.value); setClassificationPage(1); }}
                className="cr-search-input"
              />
              {classSearch && (
                <button type="button" onClick={() => { setClassSearch(''); setClassificationPage(1); }} className="cr-search-clear">&times;</button>
              )}
            </div>
            {filteredRules.length === 0 ? (
              renderSectionEmpty(
                t(
                  'classificationRules.categoryEmpty',
                  'No category rules yet. They will appear after you correct a transaction category.'
                )
              )
            ) : (
              <div className="cr-table-wrap">
                <table className="cr-table">
                  <thead>
                    <tr>
                      <th className="cr-checkbox-col"></th>
                      <th>{t('classificationRules.description', 'Description')}</th>
                      <th>{t('classificationRules.type', 'Type')}</th>
                      <th>{t('classificationRules.category', 'Category')}</th>
                      <th>{t('classificationRules.ruleType', 'Rule')}</th>
                      {showClassificationReason ? <th>{t('classificationRules.reason', 'Reason')}</th> : null}
                      <th>{t('classificationRules.hits', 'Hits')}</th>
                      {showClassificationConfidence ? <th>{t('classificationRules.confidence', 'Conf.')}</th> : null}
                      {showClassificationStatus ? <th>{t('classificationRules.status', 'Status')}</th> : null}
                      <th>{t('classificationRules.lastUsed', 'Last used')}</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedRules.map((rule) => (
                      <tr key={rule.id} className={rule.frozen ? 'frozen-row' : ''}>
                        <td className="cr-checkbox-col">
                          <input
                            type="checkbox"
                            checked={selectedClassificationIds.includes(rule.id)}
                            onChange={() =>
                              setSelectedClassificationIds((prev) => toggleId(prev, rule.id))
                            }
                            aria-label={t('classificationRules.selectRule', 'Select rule')}
                          />
                        </td>
                        <td
                          className="cr-desc"
                          title={rule.original_description || rule.normalized_description}
                        >
                          {rule.original_description || rule.normalized_description}
                        </td>
                        <td>
                          <span className={`cr-type-badge ${rule.txn_type}`}>
                            {t(`transactions.types.${rule.txn_type}`, rule.txn_type)}
                          </span>
                        </td>
                        <td>
                          <span className="cr-category">
                            {formatTransactionCategoryLabel(rule.category, t)}
                          </span>
                        </td>
                        <td>
                          <span className={`cr-rule-type ${rule.rule_type}`}>
                            {rule.rule_type === 'strict'
                              ? t('classificationRules.ruleTypeStrict', 'Strict')
                              : t('classificationRules.ruleTypeAdaptive', 'Adaptive')}
                          </span>
                        </td>
                        {showClassificationReason ? (
                          <td className="cr-reason">{getClassificationRuleReason(rule)}</td>
                        ) : null}
                        <td className="cr-center">{rule.hit_count}</td>
                        {showClassificationConfidence ? (
                          <td className="cr-center">{(rule.confidence * 100).toFixed(0)}%</td>
                        ) : null}
                        {showClassificationStatus ? (
                          <td>
                            {renderStatusCell({
                              frozen: rule.frozen,
                              conflictCount: rule.conflict_count,
                              isActive: !rule.frozen && rule.conflict_count === 0,
                            })}
                          </td>
                        ) : null}
                        <td>{formatDateTime(rule.last_hit_at || rule.created_at, i18n.language)}</td>
                        <td>{renderDeleteButton('classification', rule.id)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {renderPagination(classificationPage, classificationPageCount, setClassificationPage)}
              </div>
            )}
          </>
        )
      })}

      {renderSectionShell({
        section: 'automation',
        title: t('classificationRules.automationSectionTitle', 'Automatic handling rules'),
        subtitle: t(
          'classificationRules.automationSectionDescription',
          'Patterns learned from confirmed bank statement creations that can be auto-created next time.'
        ),
        count: automationRules.length,
        children: (
          <>
            <div className="cr-section-toolbar">
              {renderSelectionControls(
                'classification',
                selectedAutomationIds,
                allAutomationIds,
                () =>
                  setSelectedAutomationIds(
                    selectedAutomationIds.length === allAutomationIds.length
                      ? []
                      : allAutomationIds
                  ),
                t('classificationRules.selectAllAutomation', 'Select all automatic handling rules')
              )}
            </div>
            <div className="cr-search">
              <input
                type="text"
                placeholder={t('classificationRules.searchAutomationPlaceholder', 'Search automatic handling rules...')}
                value={automationSearch}
                onChange={(e) => { setAutomationSearch(e.target.value); setAutomationPage(1); }}
                className="cr-search-input"
              />
              {automationSearch && (
                <button type="button" onClick={() => { setAutomationSearch(''); setAutomationPage(1); }} className="cr-search-clear">&times;</button>
              )}
            </div>
            {filteredAutomationRules.length === 0 ? (
              renderSectionEmpty(
                t(
                  'classificationRules.automationEmpty',
                  'No automatic handling rules yet. They will appear after you confirm creating a bank statement transaction.'
                )
              )
            ) : (
              <div className="cr-table-wrap">
                <table className="cr-table">
                  <thead>
                    <tr>
                      <th className="cr-checkbox-col"></th>
                      <th>{t('classificationRules.description', 'Description')}</th>
                      <th>{t('classificationRules.type', 'Type')}</th>
                      <th>{t('classificationRules.category', 'Category')}</th>
                      <th>{t('classificationRules.action', 'Action')}</th>
                      {showAutomationReason ? <th>{t('classificationRules.reason', 'Reason')}</th> : null}
                      <th>{t('classificationRules.hits', 'Hits')}</th>
                      {showAutomationConfidence ? <th>{t('classificationRules.confidence', 'Conf.')}</th> : null}
                      {showAutomationStatus ? <th>{t('classificationRules.status', 'Status')}</th> : null}
                      <th>{t('classificationRules.lastUsed', 'Last used')}</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedAutomationRules.map((rule) => (
                      <tr key={rule.id} className={rule.frozen ? 'frozen-row' : ''}>
                        <td className="cr-checkbox-col">
                          <input
                            type="checkbox"
                            checked={selectedAutomationIds.includes(rule.id)}
                            onChange={() =>
                              setSelectedAutomationIds((prev) => toggleId(prev, rule.id))
                            }
                            aria-label={t('classificationRules.selectRule', 'Select rule')}
                          />
                        </td>
                        <td
                          className="cr-desc"
                          title={rule.original_description || rule.normalized_description}
                        >
                          {rule.original_description || rule.normalized_description}
                        </td>
                        <td>
                          <span className={`cr-type-badge ${rule.txn_type}`}>
                            {t(`transactions.types.${rule.txn_type}`, rule.txn_type)}
                          </span>
                        </td>
                        <td>
                          <span className="cr-category">
                            {formatTransactionCategoryLabel(rule.category, t)}
                          </span>
                        </td>
                        <td>
                          <span className="cr-rule-type auto">
                            {t('classificationRules.automationActionAutoCreate', 'Auto-create')}
                          </span>
                        </td>
                        {showAutomationReason ? (
                          <td className="cr-reason">{getAutomationRuleReason(rule)}</td>
                        ) : null}
                        <td className="cr-center">{rule.hit_count}</td>
                        {showAutomationConfidence ? (
                          <td className="cr-center">{(rule.confidence * 100).toFixed(0)}%</td>
                        ) : null}
                        {showAutomationStatus ? (
                          <td>
                            {renderStatusCell({
                              frozen: rule.frozen,
                              conflictCount: rule.conflict_count,
                              isActive: !rule.frozen && rule.conflict_count === 0,
                            })}
                          </td>
                        ) : null}
                        <td>{formatDateTime(rule.last_hit_at || rule.created_at, i18n.language)}</td>
                        <td>{renderDeleteButton('classification', rule.id)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {renderPagination(automationPage, automationPageCount, setAutomationPage)}
              </div>
            )}
          </>
        )
      })}

      {renderSectionShell({
        section: 'deductibility',
        title: t('classificationRules.deductibilitySectionTitle', 'Deductibility overrides'),
        subtitle: t(
          'classificationRules.deductibilitySectionDescription',
          'Saved deductible and non-deductible overrides that the system will reuse next time.'
        ),
        count: deductibilityRules.length,
        children: (
          <>
            <div className="cr-section-toolbar">
              {renderSelectionControls(
                'deductibility',
                selectedDeductibilityIds,
                allDeductibilityIds,
                () =>
                  setSelectedDeductibilityIds(
                    selectedDeductibilityIds.length === allDeductibilityIds.length
                      ? []
                      : allDeductibilityIds
                  ),
                t('classificationRules.selectAllDeductibility', 'Select all deductibility rules')
              )}
            </div>
            <div className="cr-search">
              <input
                type="text"
                placeholder={t('classificationRules.searchDeductPlaceholder', 'Search by description...')}
                value={deductSearch}
                onChange={(e) => { setDeductSearch(e.target.value); setDeductibilityPage(1); }}
                className="cr-search-input"
              />
              {deductSearch && (
                <button type="button" onClick={() => { setDeductSearch(''); setDeductibilityPage(1); }} className="cr-search-clear">&times;</button>
              )}
            </div>
            {filteredDeductibilityRules.length === 0 ? (
              renderSectionEmpty(
                t(
                  'classificationRules.deductibilityEmpty',
                  'No deductibility overrides yet. They will appear after you mark a transaction or receipt item deductible or non-deductible.'
                )
              )
            ) : (
              <div className="cr-table-wrap">
                <table className="cr-table">
                  <thead>
                    <tr>
                      <th className="cr-checkbox-col"></th>
                      <th>{t('classificationRules.description', 'Description')}</th>
                      <th>{t('classificationRules.type', 'Type')}</th>
                      <th>{t('classificationRules.category', 'Category')}</th>
                      <th>{t('classificationRules.decision', 'Decision')}</th>
                      <th>{t('classificationRules.ruleType', 'Rule')}</th>
                      {showDeductibilityReason ? <th>{t('classificationRules.reason', 'Reason')}</th> : null}
                      <th>{t('classificationRules.hits', 'Hits')}</th>
                      {showDeductibilityConfidence ? <th>{t('classificationRules.confidence', 'Conf.')}</th> : null}
                      {showDeductibilityStatus ? <th>{t('classificationRules.status', 'Status')}</th> : null}
                      <th>{t('classificationRules.lastUsed', 'Last used')}</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedDeductibilityRules.map((rule) => (
                      <tr key={rule.id}>
                        <td className="cr-checkbox-col">
                          <input
                            type="checkbox"
                            checked={selectedDeductibilityIds.includes(rule.id)}
                            onChange={() =>
                              setSelectedDeductibilityIds((prev) => toggleId(prev, rule.id))
                            }
                            aria-label={t('classificationRules.selectRule', 'Select rule')}
                          />
                        </td>
                        <td
                          className="cr-desc"
                          title={rule.original_description || rule.normalized_description}
                        >
                          {rule.original_description || rule.normalized_description}
                        </td>
                        <td>
                          <span className="cr-type-badge expense">
                            {t('transactions.types.expense', 'Expense')}
                          </span>
                        </td>
                        <td>
                          <span className="cr-category">
                            {formatTransactionCategoryLabel(rule.expense_category, t)}
                          </span>
                        </td>
                        <td>
                          <span className={`cr-badge ${rule.is_deductible ? 'active' : 'conflict'}`}>
                            {rule.is_deductible
                              ? t('transactions.deductibleYes', 'Deductible')
                              : t('transactions.notDeductible', 'Not deductible')}
                          </span>
                        </td>
                        <td>
                          <span className="cr-rule-type strict">
                            {t('classificationRules.ruleTypeOverride', 'Override')}
                          </span>
                        </td>
                        {showDeductibilityReason ? (
                          <td className="cr-reason">
                            {rule.reason || t('classificationRules.noReason', 'Manual override')}
                          </td>
                        ) : null}
                        <td className="cr-center">{rule.hit_count}</td>
                        {showDeductibilityConfidence ? <td className="cr-center">100%</td> : null}
                        {showDeductibilityStatus ? <td>{renderStatusCell({ isActive: true })}</td> : null}
                        <td>{formatDateTime(rule.updated_at || rule.last_hit_at, i18n.language)}</td>
                        <td>{renderDeleteButton('deductibility', rule.id)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {renderPagination(deductibilityPage, deductibilityPageCount, setDeductibilityPage)}
              </div>
            )}
          </>
        )
      })}
      <ConfirmDialog
        isOpen={pendingDelete !== null}
        message={
          pendingDelete && pendingDelete.ids.length > 1
            ? `${t('classificationRules.confirmBulkDelete', 'Delete selected rules?')} (${pendingDelete.ids.length})`
            : t('classificationRules.confirmDelete', 'Delete this rule?')
        }
        variant="danger"
        confirmText={t('common.delete', 'Delete')}
        cancelText={t('common.cancel', 'Cancel')}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
};

export default ClassificationRules;
