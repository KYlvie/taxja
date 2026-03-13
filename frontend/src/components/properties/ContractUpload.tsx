import React, { useState, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { documentService } from '../../services/documentService';
import { PropertyFormData } from '../../types/property';
import './ContractUpload.css';

export interface ContractData {
  // Kaufvertrag fields
  property_address?: string;
  street?: string;
  city?: string;
  postal_code?: string;
  purchase_date?: string;
  purchase_price?: number;
  building_value?: number;
  buyer_name?: string;
  seller_name?: string;
  notary_name?: string;
  notary_fees?: number;
  grunderwerbsteuer?: number;
  registry_fees?: number;
  
  // Mietvertrag fields
  monthly_rent?: number;
  rental_start_date?: string;
  rental_end_date?: string;
  tenant_name?: string;
  landlord_name?: string;
  additional_costs?: number;
  utilities_included?: boolean;
  contract_type?: string;
  
  // Metadata
  confidence?: number;
  document_type?: 'kaufvertrag' | 'mietvertrag';
}

interface ContractUploadProps {
  onExtracted: (data: Partial<PropertyFormData>, contractData: ContractData) => void;
  onCancel: () => void;
}

const ContractUpload: React.FC<ContractUploadProps> = ({ onExtracted, onCancel }) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'processing' | 'extracted' | 'error'>('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [extractedData, setExtractedData] = useState<ContractData | null>(null);
  const [editableData, setEditableData] = useState<Partial<PropertyFormData>>({});

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;

      const file = files[0]; // Only process first file
      
      // Validate file type
      if (!file.type.includes('pdf') && !file.type.includes('image')) {
        setError(t('properties.contractUpload.invalidFileType'));
        return;
      }

      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        setError(t('properties.contractUpload.fileTooLarge'));
        return;
      }

      setError(null);
      setUploadStatus('uploading');
      setUploadProgress(0);

      try {
        // Upload document
        const document = await documentService.uploadDocument(
          file,
          (progress) => {
            setUploadProgress(progress);
          }
        );

        setUploadStatus('processing');
        setUploadProgress(100);

        // Wait for OCR processing (poll for results)
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Get OCR review data
        const reviewData = await documentService.getDocumentForReview(document.id);
        
        // Extract contract-specific data
        const contractData: ContractData = {
          ...reviewData.extracted_data,
          confidence: reviewData.document.confidence_score,
          document_type: reviewData.extracted_data.document_type as 'kaufvertrag' | 'mietvertrag',
        };

        setExtractedData(contractData);

        // Map to PropertyFormData
        const propertyData: Partial<PropertyFormData> = {
          street: contractData.street || '',
          city: contractData.city || '',
          postal_code: contractData.postal_code || '',
          purchase_date: contractData.purchase_date || '',
          purchase_price: contractData.purchase_price?.toString() || '',
          building_value: contractData.building_value?.toString() || '',
          notary_fees: contractData.notary_fees?.toString() || '',
          grunderwerbsteuer: contractData.grunderwerbsteuer?.toString() || '',
          registry_fees: contractData.registry_fees?.toString() || '',
        };

        setEditableData(propertyData);
        setUploadStatus('extracted');

      } catch (err: any) {
        console.error('Contract upload error:', err);
        setError(err.response?.data?.detail || t('properties.contractUpload.uploadError'));
        setUploadStatus('error');
      }
    },
    [t]
  );

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    handleFiles(files);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    e.target.value = '';
  };

  const handleFieldChange = (field: keyof PropertyFormData, value: string) => {
    setEditableData(prev => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleConfirm = () => {
    if (extractedData) {
      onExtracted(editableData, extractedData);
    }
  };

  const handleRetry = () => {
    setUploadStatus('idle');
    setError(null);
    setExtractedData(null);
    setEditableData({});
    setUploadProgress(0);
  };

  const getConfidenceColor = (confidence?: number) => {
    if (!confidence) return 'low';
    if (confidence >= 0.8) return 'high';
    if (confidence >= 0.6) return 'medium';
    return 'low';
  };

  const getConfidenceLabel = (confidence?: number) => {
    if (!confidence) return t('properties.contractUpload.confidenceLow');
    if (confidence >= 0.8) return t('properties.contractUpload.confidenceHigh');
    if (confidence >= 0.6) return t('properties.contractUpload.confidenceMedium');
    return t('properties.contractUpload.confidenceLow');
  };

  return (
    <div className="contract-upload">
      <div className="contract-upload-header">
        <h2>{t('properties.contractUpload.title')}</h2>
        <p className="subtitle">{t('properties.contractUpload.subtitle')}</p>
      </div>

      {uploadStatus === 'idle' && (
        <>
          <div
            className={`upload-zone ${isDragging ? 'dragging' : ''}`}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="upload-icon">📄</div>
            <h3>{t('properties.contractUpload.dropZoneTitle')}</h3>
            <p>{t('properties.contractUpload.dropZoneText')}</p>
            <p className="upload-hint">{t('properties.contractUpload.supportedFormats')}</p>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,image/*"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
          </div>

          <div className="contract-types">
            <div className="contract-type-card">
              <div className="contract-type-icon">📋</div>
              <h4>{t('properties.contractUpload.kaufvertragTitle')}</h4>
              <p>{t('properties.contractUpload.kaufvertragDesc')}</p>
            </div>
            <div className="contract-type-card">
              <div className="contract-type-icon">🏠</div>
              <h4>{t('properties.contractUpload.mietvertragTitle')}</h4>
              <p>{t('properties.contractUpload.mietvertragDesc')}</p>
            </div>
          </div>

          <div className="upload-actions">
            <button
              className="btn btn-secondary"
              onClick={onCancel}
            >
              {t('common.cancel')}
            </button>
            <button
              className="btn btn-primary"
              onClick={() => fileInputRef.current?.click()}
            >
              📁 {t('properties.contractUpload.selectFile')}
            </button>
          </div>
        </>
      )}

      {(uploadStatus === 'uploading' || uploadStatus === 'processing') && (
        <div className="upload-progress-container">
          <div className="upload-status-icon">
            {uploadStatus === 'uploading' ? '📤' : '🔍'}
          </div>
          <h3>
            {uploadStatus === 'uploading'
              ? t('properties.contractUpload.uploading')
              : t('properties.contractUpload.processing')}
          </h3>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
          <p className="progress-text">{uploadProgress}%</p>
        </div>
      )}

      {uploadStatus === 'extracted' && extractedData && (
        <div className="extraction-results">
          <div className="extraction-header">
            <h3>{t('properties.contractUpload.extractedData')}</h3>
            <div className={`confidence-badge ${getConfidenceColor(extractedData.confidence)}`}>
              {getConfidenceLabel(extractedData.confidence)}
              {extractedData.confidence && ` (${(extractedData.confidence * 100).toFixed(0)}%)`}
            </div>
          </div>

          {extractedData.confidence && extractedData.confidence < 0.8 && (
            <div className="warning-message">
              <span className="warning-icon">⚠️</span>
              {t('properties.contractUpload.lowConfidenceWarning')}
            </div>
          )}

          <div className="extracted-fields">
            <div className="field-group">
              <label>{t('properties.street')}</label>
              <input
                type="text"
                value={editableData.street || ''}
                onChange={(e) => handleFieldChange('street', e.target.value)}
                placeholder={t('properties.streetPlaceholder')}
              />
            </div>

            <div className="field-row">
              <div className="field-group">
                <label>{t('properties.postalCode')}</label>
                <input
                  type="text"
                  value={editableData.postal_code || ''}
                  onChange={(e) => handleFieldChange('postal_code', e.target.value)}
                  placeholder="1010"
                />
              </div>

              <div className="field-group">
                <label>{t('properties.city')}</label>
                <input
                  type="text"
                  value={editableData.city || ''}
                  onChange={(e) => handleFieldChange('city', e.target.value)}
                  placeholder="Wien"
                />
              </div>
            </div>

            {extractedData.document_type === 'kaufvertrag' && (
              <>
                <div className="field-row">
                  <div className="field-group">
                    <label>{t('properties.purchaseDate')}</label>
                    <input
                      type="date"
                      value={editableData.purchase_date || ''}
                      onChange={(e) => handleFieldChange('purchase_date', e.target.value)}
                    />
                  </div>

                  <div className="field-group">
                    <label>{t('properties.purchasePrice')}</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editableData.purchase_price || ''}
                      onChange={(e) => handleFieldChange('purchase_price', e.target.value)}
                      placeholder="350000.00"
                    />
                  </div>
                </div>

                <div className="field-group">
                  <label>{t('properties.buildingValue')}</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editableData.building_value || ''}
                    onChange={(e) => handleFieldChange('building_value', e.target.value)}
                    placeholder="280000.00"
                  />
                </div>

                <div className="field-row">
                  <div className="field-group">
                    <label>{t('properties.grunderwerbsteuer')}</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editableData.grunderwerbsteuer || ''}
                      onChange={(e) => handleFieldChange('grunderwerbsteuer', e.target.value)}
                      placeholder="0.00"
                    />
                  </div>

                  <div className="field-group">
                    <label>{t('properties.notaryFees')}</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editableData.notary_fees || ''}
                      onChange={(e) => handleFieldChange('notary_fees', e.target.value)}
                      placeholder="0.00"
                    />
                  </div>
                </div>

                <div className="field-group">
                  <label>{t('properties.registryFees')}</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editableData.registry_fees || ''}
                    onChange={(e) => handleFieldChange('registry_fees', e.target.value)}
                    placeholder="0.00"
                  />
                </div>
              </>
            )}

            {extractedData.document_type === 'mietvertrag' && (
              <div className="info-message">
                <span className="info-icon">ℹ️</span>
                {t('properties.contractUpload.mietvertragInfo')}
              </div>
            )}
          </div>

          <div className="extraction-actions">
            <button
              className="btn btn-secondary"
              onClick={handleRetry}
            >
              {t('properties.contractUpload.uploadAnother')}
            </button>
            <button
              className="btn btn-primary"
              onClick={handleConfirm}
            >
              {t('properties.contractUpload.useData')}
            </button>
          </div>
        </div>
      )}

      {uploadStatus === 'error' && (
        <div className="upload-error">
          <div className="error-icon">❌</div>
          <h3>{t('properties.contractUpload.errorTitle')}</h3>
          <p className="error-message">{error}</p>
          <div className="error-actions">
            <button
              className="btn btn-secondary"
              onClick={onCancel}
            >
              {t('common.cancel')}
            </button>
            <button
              className="btn btn-primary"
              onClick={handleRetry}
            >
              {t('properties.contractUpload.retry')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ContractUpload;
