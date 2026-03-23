import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
// SubpageBackLink removed — using unified properties-header layout
import LiabilityDetailPanel from '../components/liabilities/LiabilityDetail';
import LiabilityForm from '../components/liabilities/LiabilityForm';
import LiabilityList from '../components/liabilities/LiabilityList';
import { useConfirm } from '../hooks/useConfirm';
import { documentService } from '../services/documentService';
import { liabilityService } from '../services/liabilityService';
import { propertyService } from '../services/propertyService';
import { Document, DocumentType } from '../types/document';
import { getApiErrorMessage } from '../utils/apiError';
import { formatDocumentFieldList } from '../utils/documentFieldLabel';
import {
  LiabilityCreatePayload,
  LiabilityDetail,
  LiabilityRecord,
  LiabilityUpdatePayload,
} from '../types/liability';
import './LiabilitiesPage.css';

type ManageMode = 'detail' | 'create' | 'edit';

type PropertyOption = {
  value: string;
  label: string;
};

const LiabilitiesPage = () => {
  const { t } = useTranslation();
  const { confirm, alert } = useConfirm();
  const navigate = useNavigate();
  const location = useLocation();
  const { id } = useParams<{ id: string }>();

  const [includeInactive, setIncludeInactive] = useState(false);
  const [liabilities, setLiabilities] = useState<LiabilityRecord[]>([]);
  const [loanDocuments, setLoanDocuments] = useState<Document[]>([]);
  const [selectedLiability, setSelectedLiability] = useState<LiabilityDetail | null>(null);
  const [propertyOptions, setPropertyOptions] = useState<PropertyOption[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingLoanDocuments, setLoadingLoanDocuments] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const manageMode: ManageMode = useMemo(() => {
    if (location.pathname.endsWith('/new')) {
      return 'create';
    }
    if (id) {
      return selectedLiability ? 'detail' : 'detail';
    }
    return 'detail';
  }, [id, location.pathname, selectedLiability]);

  const [editing, setEditing] = useState(false);

  const pendingLoanDocuments = useMemo(() => {
    const linkedDocumentIds = new Set(
      liabilities
        .map((liability) => liability.source_document_id)
        .filter((value): value is number => typeof value === 'number'),
    );

    return loanDocuments.filter((document) => {
      if (linkedDocumentIds.has(document.id)) {
        return false;
      }

      const suggestion = document.ocr_result?.import_suggestion;
      const status = suggestion?.status;
      return status === 'pending' || status === 'needs_input';
    });
  }, [liabilities, loanDocuments]);

  const activeLiabilityCount = useMemo(
    () => liabilities.filter((liability) => liability.is_active).length,
    [liabilities],
  );
  const inactiveLiabilityCount = liabilities.length - activeLiabilityCount;

  const refreshList = async () => {
    setLoadingList(true);
    try {
      const data = await liabilityService.list(includeInactive);
      setLiabilities(data.items);
    } catch (error) {
      console.error('Failed to load liabilities', error);
      await alert(t('liabilities.errors.loadList'), {
        variant: 'danger',
      });
    } finally {
      setLoadingList(false);
    }
  };

  const refreshProperties = async () => {
    try {
      const data = await propertyService.getProperties(true);
      const options = (data.properties || []).map((property) => ({
        value: String(property.id),
        label: property.address,
      }));
      setPropertyOptions(options);
    } catch (error) {
      console.error('Failed to load properties for liabilities', error);
    }
  };

  const refreshLoanDocuments = async () => {
    setLoadingLoanDocuments(true);
    try {
      const data = await documentService.getDocuments(
        { document_type: DocumentType.LOAN_CONTRACT },
        1,
        50,
      );
      setLoanDocuments(data.documents);
    } catch (error) {
      console.error('Failed to load loan documents for liabilities', error);
    } finally {
      setLoadingLoanDocuments(false);
    }
  };

  const refreshDetail = async (liabilityId: number) => {
    setLoadingDetail(true);
    try {
      const detail = await liabilityService.get(liabilityId);
      setSelectedLiability(detail);
    } catch (error) {
      console.error('Failed to load liability detail', error);
      setSelectedLiability(null);
      await alert(t('liabilities.errors.loadDetail'), {
        variant: 'danger',
      });
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => {
    void refreshProperties();
    void refreshLoanDocuments();
  }, []);

  useEffect(() => {
    void refreshList();
  }, [includeInactive]);

  useEffect(() => {
    if (!id) {
      setSelectedLiability(null);
      setEditing(false);
      return;
    }
    const liabilityId = Number(id);
    if (!Number.isFinite(liabilityId)) {
      return;
    }
    void refreshDetail(liabilityId);
  }, [id]);

  const handleCreate = async (payload: LiabilityCreatePayload | LiabilityUpdatePayload) => {
    setSubmitting(true);
    try {
      const created = await liabilityService.create(payload as LiabilityCreatePayload);
      await refreshList();
      setEditing(false);
      navigate(`/liabilities/${created.id}`);
      await refreshDetail(created.id);
    } catch (error) {
      console.error('Failed to create liability', error);
      await alert(
        getApiErrorMessage(error, t('liabilities.errors.create')),
        {
          variant: 'danger',
        },
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdate = async (payload: LiabilityCreatePayload | LiabilityUpdatePayload) => {
    if (!selectedLiability) {
      return;
    }
    setSubmitting(true);
    try {
      await liabilityService.update(selectedLiability.id, payload as LiabilityUpdatePayload);
      await Promise.all([refreshList(), refreshDetail(selectedLiability.id)]);
      setEditing(false);
    } catch (error) {
      console.error('Failed to update liability', error);
      await alert(
        getApiErrorMessage(error, t('liabilities.errors.update')),
        {
          variant: 'danger',
        },
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async () => {
    if (!selectedLiability) {
      return;
    }
    const accepted = await confirm(
      t('liabilities.confirm.deactivate'),
      {
        title: t('liabilities.actions.deactivate'),
        confirmText: t('common.continue'),
        cancelText: t('common.cancel'),
        variant: 'warning',
      },
    );

    if (!accepted) {
      return;
    }

    setSubmitting(true);
    try {
      await liabilityService.remove(selectedLiability.id);
      await refreshList();
      navigate('/liabilities');
      setSelectedLiability(null);
      setEditing(false);
    } catch (error) {
      console.error('Failed to deactivate liability', error);
      await alert(
        getApiErrorMessage(error, t('liabilities.errors.delete')),
        {
          variant: 'danger',
        },
      );
    } finally {
      setSubmitting(false);
    }
  };

  const openCreate = () => {
    setEditing(false);
    navigate('/liabilities/new');
  };

  const openSelect = (liabilityId: number) => {
    setEditing(false);
    navigate(`/liabilities/${liabilityId}`);
  };

  const closeManagePane = () => {
    setEditing(false);
    navigate('/liabilities');
  };

  const getPendingLoanDocumentStatus = (document: Document) => {
    const suggestion = document.ocr_result?.import_suggestion;
    if (suggestion?.status === 'needs_input') {
      return t('liabilities.documents.pendingNeedsInput');
    }

    const missingFields = suggestion?.data?.missing_fields;
    if (Array.isArray(missingFields) && missingFields.length > 0) {
      return t('liabilities.documents.pendingMissingFields', {
        fields: formatDocumentFieldList(missingFields, t),
      });
    }

    return t('liabilities.documents.pendingReview');
  };

  // Form rendering is now handled at the top level (full-page mode)

  // Full-page form mode (like asset form)
  if (manageMode === 'create') {
    return (
      <div className="liabilities-page liabilities-page--form-mode">
        <div className="liabilities-header">
          <div className="liabilities-title">
            <h1>{t('liabilities.page.title')}</h1>
            <p>{t('liabilities.page.manageSub')}</p>
          </div>
        </div>
        <div className="liabilities-form-shell card">
          <button type="button" className="liabilities-back-strip" onClick={closeManagePane}>
            {t('common.back')}
          </button>
          <div className="liabilities-form-stage">
            <LiabilityForm
              propertyOptions={propertyOptions}
              submitting={submitting}
              onCancel={closeManagePane}
              onSubmit={handleCreate}
            />
          </div>
        </div>
      </div>
    );
  }

  if (selectedLiability && editing) {
    return (
      <div className="liabilities-page liabilities-page--form-mode">
        <div className="liabilities-header">
          <div className="liabilities-title">
            <h1>{t('liabilities.page.title')}</h1>
            <p>{t('liabilities.page.manageSub')}</p>
          </div>
        </div>
        <div className="liabilities-form-shell card">
          <button type="button" className="liabilities-back-strip" onClick={() => setEditing(false)}>
            {t('common.back')}
          </button>
          <div className="liabilities-form-stage">
            <LiabilityForm
              initialValue={selectedLiability}
              propertyOptions={propertyOptions}
              submitting={submitting}
              onCancel={() => setEditing(false)}
              onSubmit={handleUpdate}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="liabilities-page">
      <div className="properties-header">
        <div className="properties-title">
          <h1>{t('liabilities.page.title')}</h1>
          <p className="properties-subtitle">{t('liabilities.page.manageSub')}</p>
        </div>
        <div className="properties-actions">
          <button type="button" className="btn btn-primary" onClick={openCreate}>
            {t('liabilities.actions.new')}
          </button>
        </div>
      </div>

      <div className="properties-overview-link" style={{ marginBottom: '16px' }}>
        <Link to="/liabilities/overview" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', width: '100%', justifyContent: 'center', textDecoration: 'none' }}>
          {t('liabilities.overview.pageTitle', 'Liability Overview')}
        </Link>
      </div>

      <div className="list-header">
        <div className="list-stats">
          <span className="stat-item">
            <strong>{activeLiabilityCount}</strong> {t('liabilities.manage.countLabel')}
          </span>
          {pendingLoanDocuments.length > 0 && (
            <span className="stat-item" style={{ marginLeft: '8px' }}>
              <strong>{pendingLoanDocuments.length}</strong>{' '}
              {t('liabilities.documents.pendingTitle')}
            </span>
          )}
          {includeInactive && inactiveLiabilityCount > 0 && (
            <span className="stat-item muted">
              ({inactiveLiabilityCount} {t('common.inactive')})
            </span>
          )}
        </div>
        <div className="toggle-archived">
          <label>
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
            />
            {t('liabilities.filters.includeInactive')}
          </label>
        </div>
      </div>

      {(loadingLoanDocuments || pendingLoanDocuments.length > 0) && (
        <section className="liability-panel card">
          <div className="liability-group-header">
            <div>
              <h2>{t('liabilities.documents.pendingTitle')}</h2>
              <p className="liability-hint">
                {t('liabilities.documents.pendingHint')}
              </p>
            </div>
            <span className="liability-count-badge">
              {loadingLoanDocuments ? '...' : pendingLoanDocuments.length}
            </span>
          </div>

          {loadingLoanDocuments ? (
            <p className="liability-hint">{t('common.loading')}</p>
          ) : (
            <div className="liability-list-items">
              {pendingLoanDocuments.map((document) => (
                <article key={document.id} className="liability-pending-doc-card">
                  <div>
                    <strong>{document.file_name || `${t('documents.document')} #${document.id}`}</strong>
                    <p>{getPendingLoanDocumentStatus(document)}</p>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => navigate(`/documents/${document.id}`)}
                  >
                    {t('liabilities.documents.openSourceDocument')}
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      <div className="liabilities-content">
        {loadingList ? (
          <section className="liability-panel card">
            <h2>{t('liabilities.manage.listTitle')}</h2>
            <p className="liability-hint">{t('common.loading')}</p>
          </section>
        ) : (
          <LiabilityList liabilities={liabilities} selectedId={selectedLiability?.id ?? null} onSelect={openSelect} />
        )}
        {selectedLiability && !editing && (
          <LiabilityDetailPanel
            liability={selectedLiability}
            loading={loadingDetail}
            onEdit={() => setEditing(true)}
            onDeactivate={handleDeactivate}
          />
        )}
        {!selectedLiability && (
          <LiabilityDetailPanel
            liability={null}
            loading={false}
            onEdit={() => {}}
            onDeactivate={() => Promise.resolve()}
          />
        )}
      </div>
    </div>
  );
};

export default LiabilitiesPage;
