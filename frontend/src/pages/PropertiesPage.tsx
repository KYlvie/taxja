import { useState, useEffect, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useConfirm } from '../hooks/useConfirm';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { usePropertyStore } from '../stores/propertyStore';
import { propertyService } from '../services/propertyService';
import { documentService } from '../services/documentService';
import PropertyList from '../components/properties/PropertyList';
import PropertyForm from '../components/properties/PropertyForm';
import PropertyDetail from '../components/properties/PropertyDetail';
import DisposalDialog from '../components/properties/DisposalDialog';
import { Property, PropertyFormData, DisposalRequest } from '../types/property';
import { Document, DocumentType } from '../types/document';
import { useRefreshStore } from '../stores/refreshStore';
import { formatDocumentFieldList } from '../utils/documentFieldLabel';
import { BarChart3 } from 'lucide-react';
import './PropertiesPage.css';

type AssetImportSuggestion = {
  type?: string;
  status?: string;
  data?: {
    missing_fields?: string[];
  };
};

type AssetDocumentOcrResult = Document['ocr_result'] & {
  import_suggestion?: AssetImportSuggestion;
};

type AssetCreatePayload = {
  asset_type: string;
  name: string;
  sub_category?: string;
  purchase_date: string;
  purchase_price: number;
  supplier?: string;
  business_use_percentage?: number;
  useful_life_years?: number;
};

type RealEstateCreatePayload = {
  property_type: PropertyType;
  street: string;
  city: string;
  postal_code: string;
  purchase_date: string;
  purchase_price: number;
  rental_percentage?: number;
  building_value?: number;
  construction_year?: number;
  depreciation_rate?: number;
  grunderwerbsteuer?: number;
  notary_fees?: number;
  registry_fees?: number;
  monthly_rent?: number;
};

type PropertyUpdatePayload = {
  property_type?: PropertyType;
  street?: string;
  city?: string;
  postal_code?: string;
  purchase_date?: string;
  purchase_price?: number;
  rental_percentage?: number;
  building_value?: number;
  construction_year?: number;
  depreciation_rate?: number;
  grunderwerbsteuer?: number;
  notary_fees?: number;
  registry_fees?: number;
  asset_type?: string;
  name?: string;
  sub_category?: string;
  supplier?: string;
  business_use_percentage?: number;
  useful_life_years?: number;
  put_into_use_date?: string;
};

const toNumber = (value: number | string | undefined): number | undefined => {
  if (value === undefined || value === '') return undefined;
  const parsed = typeof value === 'string' ? parseFloat(value) : value;
  return Number.isFinite(parsed) ? parsed : undefined;
};

const toInteger = (value: number | string | undefined): number | undefined => {
  if (value === undefined || value === '') return undefined;
  const parsed = typeof value === 'string' ? parseInt(value, 10) : value;
  return Number.isFinite(parsed) ? parsed : undefined;
};

const PropertiesPage = () => {
  const { t } = useTranslation();
  const { alert: showAlert } = useConfirm();
  const { propertyId } = useParams<{ propertyId: string }>();
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);
  const [editingProperty, setEditingProperty] = useState<Property | undefined>(undefined);
  const [otherAssets, setOtherAssets] = useState<Property[]>([]);
  const [disposalTarget, setDisposalTarget] = useState<Property | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [assetDocuments, setAssetDocuments] = useState<Document[]>([]);
  const [loadingAssetDocuments, setLoadingAssetDocuments] = useState(false);

  const {
    properties,
    selectedProperty,
    isLoading,
    error,
    fetchProperties,
    fetchProperty,
    createProperty,
    updateProperty,
    disposeProperty,
    deleteProperty,
    clearError,
  } = usePropertyStore();

  const propertiesVersion = useRefreshStore((s) => s.propertiesVersion);

  const pendingAssetDocuments = useMemo(() => {
    const linkedDocumentIds = new Set(
      [...properties, ...otherAssets]
        .map((property) => property.kaufvertrag_document_id)
        .filter((v): v is number => typeof v === 'number'),
    );

    return assetDocuments.filter((doc) => {
      if (linkedDocumentIds.has(doc.id)) return false;
      const ocrResult = doc.ocr_result as AssetDocumentOcrResult | undefined;
      const suggestion = ocrResult?.import_suggestion;
      // Match any document whose import_suggestion is a pending asset creation
      if (suggestion?.type !== 'create_asset') return false;
      const status = suggestion?.status;
      return status === 'pending' || status === 'needs_input';
    });
  }, [properties, otherAssets, assetDocuments]);

  const refreshAssetDocuments = useCallback(async () => {
    setLoadingAssetDocuments(true);
    try {
      // Fetch document types that can produce assets: purchase contracts, invoices, receipts
      const [contracts, invoices, receipts] = await Promise.all([
        documentService.getDocuments({ document_type: DocumentType.PURCHASE_CONTRACT }, 1, 50),
        documentService.getDocuments({ document_type: DocumentType.INVOICE }, 1, 50),
        documentService.getDocuments({ document_type: DocumentType.RECEIPT }, 1, 50),
      ]);
      setAssetDocuments([...contracts.documents, ...invoices.documents, ...receipts.documents]);
    } catch (error) {
      console.error('Failed to load asset documents', error);
    } finally {
      setLoadingAssetDocuments(false);
    }
  }, []);

  const getPendingAssetDocumentStatus = (doc: Document) => {
    const ocrResult = doc.ocr_result as AssetDocumentOcrResult | undefined;
    const suggestion = ocrResult?.import_suggestion;
    if (suggestion?.status === 'needs_input') {
      return t('properties.pendingDocuments.needsInput', 'Needs input');
    }
    const missingFields = suggestion?.data?.missing_fields;
    // put_into_use_date is deferrable — user can fill it after asset creation
    const deferrableFields = new Set(['put_into_use_date']);
    const blockingMissing = Array.isArray(missingFields)
      ? missingFields.filter((f: string) => !deferrableFields.has(f))
      : [];
    if (blockingMissing.length > 0) {
      return t('properties.pendingDocuments.missingFields', {
        defaultValue: 'Missing: {{fields}}',
        fields: formatDocumentFieldList(blockingMissing, t),
      });
    }
    return t('properties.pendingDocuments.awaitingConfirmation', 'Awaiting confirmation');
  };

  const refreshAll = useCallback((archived = showArchived) => {
    fetchProperties(archived);
    propertyService
      .getAssets(archived)
      .then((response) => setOtherAssets(response.assets || []))
      .catch(() => {});
  }, [fetchProperties, showArchived]);

  useEffect(() => {
    refreshAll();
    void refreshAssetDocuments();
  }, [propertiesVersion, refreshAll, refreshAssetDocuments]);

  useEffect(() => {
    if (propertyId) {
      fetchProperty(propertyId);
    }
  }, [propertyId, fetchProperty]);

  const handleCreateProperty = async (data: PropertyFormData) => {
    try {
      if (data.asset_category === 'other') {
        // Non-real-estate asset: use /assets endpoint
        const assetData: AssetCreatePayload = {
          asset_type: data.asset_type,
          name: data.asset_name,
          purchase_date: data.purchase_date,
          purchase_price: Number(data.purchase_price),
        };
        if (data.sub_category) assetData.sub_category = data.sub_category;
        if (data.supplier) assetData.supplier = data.supplier;
        const businessUsePercentage = toNumber(data.business_use_percentage);
        if (businessUsePercentage !== undefined) assetData.business_use_percentage = businessUsePercentage;
        const usefulLifeYears = toInteger(data.useful_life_years);
        if (usefulLifeYears !== undefined) assetData.useful_life_years = usefulLifeYears;

        const newAsset = await propertyService.createAsset(assetData);
        setShowForm(false);
        fetchProperties();
        navigate(`/properties/${newAsset.id}`);
      } else {
        // Real estate: use existing /properties endpoint
        const propertyData: RealEstateCreatePayload = {
          property_type: data.property_type,
          street: data.street,
          city: data.city,
          postal_code: data.postal_code,
          purchase_date: data.purchase_date,
          purchase_price: Number(data.purchase_price),
        };
        const rentalPercentage = toNumber(data.rental_percentage);
        if (rentalPercentage !== undefined) propertyData.rental_percentage = rentalPercentage;
        const buildingValue = toNumber(data.building_value);
        if (buildingValue !== undefined) propertyData.building_value = buildingValue;
        const constructionYear = toInteger(data.construction_year);
        if (constructionYear !== undefined) propertyData.construction_year = constructionYear;
        const depreciationRate = toNumber(data.depreciation_rate);
        if (depreciationRate !== undefined) propertyData.depreciation_rate = depreciationRate / 100;
        const grunderwerbsteuer = toNumber(data.grunderwerbsteuer);
        if (grunderwerbsteuer !== undefined) propertyData.grunderwerbsteuer = grunderwerbsteuer;
        const notaryFees = toNumber(data.notary_fees);
        if (notaryFees !== undefined) propertyData.notary_fees = notaryFees;
        const registryFees = toNumber(data.registry_fees);
        if (registryFees !== undefined) propertyData.registry_fees = registryFees;
        const monthlyRent = toNumber(data.monthly_rent);
        if (monthlyRent !== undefined) propertyData.monthly_rent = monthlyRent;

        const newProperty = await createProperty(propertyData);
        setShowForm(false);
        navigate(`/properties/${newProperty.id}`);
      }
    } catch (error) {
      console.error('Failed to create property/asset:', error);
    }
  };

  const handleUpdateProperty = async (data: PropertyFormData) => {
    if (!editingProperty) return;
    try {
      const updateData: PropertyUpdatePayload = {};
      if (data.property_type) updateData.property_type = data.property_type;
      if (data.street) updateData.street = data.street;
      if (data.city) updateData.city = data.city;
      if (data.postal_code) updateData.postal_code = data.postal_code;
      if (data.purchase_date) updateData.purchase_date = data.purchase_date;
      const purchasePrice = toNumber(data.purchase_price);
      if (purchasePrice !== undefined) updateData.purchase_price = purchasePrice;
      const rentalPercentage = toNumber(data.rental_percentage);
      if (rentalPercentage !== undefined) updateData.rental_percentage = rentalPercentage;
      const buildingValue = toNumber(data.building_value);
      if (buildingValue !== undefined) updateData.building_value = buildingValue;
      const constructionYear = toInteger(data.construction_year);
      if (constructionYear !== undefined) updateData.construction_year = constructionYear;
      const depreciationRate = toNumber(data.depreciation_rate);
      if (depreciationRate !== undefined) updateData.depreciation_rate = depreciationRate / 100;
      const grunderwerbsteuer = toNumber(data.grunderwerbsteuer);
      if (grunderwerbsteuer !== undefined) updateData.grunderwerbsteuer = grunderwerbsteuer;
      const notaryFees = toNumber(data.notary_fees);
      if (notaryFees !== undefined) updateData.notary_fees = notaryFees;
      const registryFees = toNumber(data.registry_fees);
      if (registryFees !== undefined) updateData.registry_fees = registryFees;

      // Asset-specific fields
      if (data.asset_type) updateData.asset_type = data.asset_type;
      if (data.asset_name) updateData.name = data.asset_name;
      if (data.sub_category) updateData.sub_category = data.sub_category;
      if (data.supplier !== undefined) updateData.supplier = data.supplier;
      const businessUsePercentage = toNumber(data.business_use_percentage);
      if (businessUsePercentage !== undefined) updateData.business_use_percentage = businessUsePercentage;
      const usefulLifeYears = toInteger(data.useful_life_years);
      if (usefulLifeYears !== undefined) updateData.useful_life_years = usefulLifeYears;
      if (data.put_into_use_date) updateData.put_into_use_date = data.put_into_use_date;

      await updateProperty(editingProperty.id, updateData);
      setEditingProperty(undefined);
      setShowForm(false);
      if (propertyId) {
        fetchProperty(propertyId);
      } else {
        fetchProperties();
      }
    } catch (error) {
      console.error('Failed to update property:', error);
    }
  };

  const handleCancelForm = () => {
    setShowForm(false);
    setEditingProperty(undefined);
  };

  const handleEditProperty = (property: Property) => {
    setEditingProperty(property);
    setShowForm(true);
  };

  const handleViewProperty = (property: Property) => {
    navigate(`/properties/${property.id}`);
  };

  const handleArchiveProperty = (property: Property) => {
    setDisposalTarget(property);
  };

  const handleShowArchivedChange = (archived: boolean) => {
    setShowArchived(archived);
    refreshAll(archived);
  };

  const handleDispose = async (data: DisposalRequest) => {
    if (!disposalTarget) return;
    try {
      await disposeProperty(disposalTarget.id, data);
      setDisposalTarget(null);
      if (propertyId) {
        navigate('/properties');
      }
      refreshAll();
    } catch (error) {
      console.error('Failed to dispose property:', error);
      await showAlert(t('properties.disposalError'), { variant: 'danger' });
    }
  };

  const handleDeleteProperty = async (id: string) => {
    try {
      await deleteProperty(id);
      // Also remove from local otherAssets state (non-real-estate assets)
      setOtherAssets((prev) => prev.filter((a) => String(a.id) !== String(id)));
    } catch (error) {
      console.error('Failed to delete property:', error);
      await showAlert(t('properties.deleteError'), { variant: 'danger' });
    }
  };

  const handleBackToList = () => {
    navigate('/properties');
  };

  // Show property detail view if propertyId in URL
  if (propertyId && selectedProperty) {
    if (showForm && editingProperty?.id === selectedProperty.id) {
      return (
        <div className="properties-page">
          <div className="properties-header">
            <button type="button" className="btn btn-secondary" onClick={handleCancelForm} style={{ marginBottom: '8px' }}>
              &larr; {t('common.back', 'Back')}
            </button>
            <h1>{t('properties.editProperty')}</h1>
          </div>
          <div className="property-form-container">
            <PropertyForm
              property={editingProperty}
              onSubmit={handleUpdateProperty}
              onCancel={handleCancelForm}
            />
          </div>
        </div>
      );
    }

    return (
      <div className="properties-page">
        {disposalTarget && (
          <DisposalDialog
            open={!!disposalTarget}
            property={disposalTarget}
            onClose={() => setDisposalTarget(null)}
            onConfirm={handleDispose}
          />
        )}
        <PropertyDetail
          property={selectedProperty}
          onEdit={handleEditProperty}
          onArchive={handleArchiveProperty}
          onBack={handleBackToList}
        />
      </div>
    );
  }

  // Show property list view
  return (
    <div className="properties-page">
      {disposalTarget && (
        <DisposalDialog
          open={!!disposalTarget}
          property={disposalTarget}
          onClose={() => setDisposalTarget(null)}
          onConfirm={handleDispose}
        />
      )}
      <div className="properties-header">
        <div className="properties-title">
          <h1>{t('properties.title')}</h1>
          <p className="properties-subtitle">{t('properties.manageYourProperties')}</p>
        </div>
        <div className="properties-actions">
          {!showForm && (
            <button
              className="btn btn-primary"
              onClick={() => setShowForm(true)}
            >
              + {t('properties.addProperty')}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={clearError} className="error-close">&times;</button>
        </div>
      )}

      {showForm && (
        <div className="property-form-container">
          <button type="button" className="btn btn-secondary" onClick={handleCancelForm} style={{ marginBottom: '12px' }}>
            &larr; {t('common.back', 'Back')}
          </button>
          <PropertyForm
            property={editingProperty}
            onSubmit={editingProperty ? handleUpdateProperty : handleCreateProperty}
            onCancel={handleCancelForm}
          />
        </div>
      )}

      {!showForm && (
        <>
          <div className="properties-overview-link" style={{ marginBottom: '16px' }}>
            <Link to="/properties/portfolio" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              <BarChart3 size={16} /> {t('properties.viewOverview', 'Asset overview & comparison')}
            </Link>
          </div>

          {(loadingAssetDocuments || pendingAssetDocuments.length > 0) && (
            <section className="liability-panel card" style={{ marginBottom: '16px' }}>
              <div className="liability-group-header">
                <div>
                  <h2>{t('properties.pendingDocuments.title', 'Pending purchase contracts')}</h2>
                  <p className="liability-hint">
                    {t('properties.pendingDocuments.hint', 'Confirmed contracts become assets automatically. Contracts still waiting for review or missing fields stay here until you finish them in Documents.')}
                  </p>
                </div>
                <span className="liability-count-badge">
                  {loadingAssetDocuments ? '...' : pendingAssetDocuments.length}
                </span>
              </div>

              {loadingAssetDocuments ? (
                <p className="liability-hint">{t('common.loading')}</p>
              ) : (
                <div className="liability-list-items">
                  {pendingAssetDocuments.map((doc) => (
                    <article key={doc.id} className="liability-pending-doc-card">
                      <div>
                        <strong>{doc.file_name || `${t('documents.document', 'Document')} #${doc.id}`}</strong>
                        <p>{getPendingAssetDocumentStatus(doc)}</p>
                      </div>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => navigate(`/documents/${doc.id}`)}
                      >
                        {t('properties.pendingDocuments.openSourceDocument', 'Open source document')}
                      </button>
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          <PropertyList
            properties={[...properties, ...otherAssets] as Property[]}
            isLoading={isLoading}
            onView={handleViewProperty}
            onEdit={handleEditProperty}
            onArchive={handleArchiveProperty}
            onDelete={handleDeleteProperty}
            showArchived={showArchived}
            onShowArchivedChange={handleShowArchivedChange}
          />
        </>
      )}
    </div>
  );
};

export default PropertiesPage;
