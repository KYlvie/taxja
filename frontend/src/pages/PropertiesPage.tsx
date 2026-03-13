import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams, useNavigate } from 'react-router-dom';
import { usePropertyStore } from '../stores/propertyStore';
import PropertyList from '../components/properties/PropertyList';
import PropertyForm from '../components/properties/PropertyForm';
import PropertyDetail from '../components/properties/PropertyDetail';
import { Property, PropertyFormData } from '../types/property';
import './PropertiesPage.css';

const PropertiesPage = () => {
  const { t } = useTranslation();
  const { propertyId } = useParams<{ propertyId: string }>();
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);
  const [editingProperty, setEditingProperty] = useState<Property | undefined>(undefined);

  const {
    properties,
    selectedProperty,
    isLoading,
    error,
    fetchProperties,
    fetchProperty,
    createProperty,
    updateProperty,
    archiveProperty,
    deleteProperty,
    clearError,
  } = usePropertyStore();

  // Fetch properties on mount
  useEffect(() => {
    fetchProperties();
  }, [fetchProperties]);

  // Fetch property detail if propertyId in URL
  useEffect(() => {
    if (propertyId) {
      fetchProperty(propertyId);
    }
  }, [propertyId, fetchProperty]);

  const handleCreateProperty = async (data: PropertyFormData) => {
    try {
      // Convert form data to PropertyCreate format
      const propertyData: any = {
        property_type: data.property_type,
        street: data.street,
        city: data.city,
        postal_code: data.postal_code,
        purchase_date: data.purchase_date,
        purchase_price: typeof data.purchase_price === 'string' ? parseFloat(data.purchase_price) : data.purchase_price,
      };

      // Add optional fields if provided
      if (data.rental_percentage) {
        propertyData.rental_percentage = typeof data.rental_percentage === 'string' 
          ? parseFloat(data.rental_percentage) 
          : data.rental_percentage;
      }
      if (data.building_value) {
        propertyData.building_value = typeof data.building_value === 'string' 
          ? parseFloat(data.building_value) 
          : data.building_value;
      }
      if (data.construction_year) {
        propertyData.construction_year = typeof data.construction_year === 'string' 
          ? parseInt(data.construction_year) 
          : data.construction_year;
      }
      if (data.depreciation_rate) {
        propertyData.depreciation_rate = typeof data.depreciation_rate === 'string' 
          ? parseFloat(data.depreciation_rate) / 100 // Convert percentage to decimal
          : data.depreciation_rate / 100;
      }
      if (data.grunderwerbsteuer) {
        propertyData.grunderwerbsteuer = typeof data.grunderwerbsteuer === 'string' 
          ? parseFloat(data.grunderwerbsteuer) 
          : data.grunderwerbsteuer;
      }
      if (data.notary_fees) {
        propertyData.notary_fees = typeof data.notary_fees === 'string' 
          ? parseFloat(data.notary_fees) 
          : data.notary_fees;
      }
      if (data.registry_fees) {
        propertyData.registry_fees = typeof data.registry_fees === 'string' 
          ? parseFloat(data.registry_fees) 
          : data.registry_fees;
      }

      const newProperty = await createProperty(propertyData);
      setShowForm(false);
      // Navigate to the new property detail
      navigate(`/properties/${newProperty.id}`);
    } catch (error) {
      console.error('Failed to create property:', error);
    }
  };

  const handleUpdateProperty = async (data: PropertyFormData) => {
    if (!editingProperty) return;
    
    try {
      // Convert form data to PropertyUpdate format
      const updateData: any = {};

      // Only include fields that are provided
      if (data.property_type) updateData.property_type = data.property_type;
      if (data.street) updateData.street = data.street;
      if (data.city) updateData.city = data.city;
      if (data.postal_code) updateData.postal_code = data.postal_code;
      
      if (data.purchase_date) updateData.purchase_date = data.purchase_date;
      if (data.purchase_price) {
        updateData.purchase_price = typeof data.purchase_price === 'string'
          ? parseFloat(data.purchase_price)
          : data.purchase_price;
      }

      if (data.rental_percentage) {
        updateData.rental_percentage = typeof data.rental_percentage === 'string' 
          ? parseFloat(data.rental_percentage) 
          : data.rental_percentage;
      }
      if (data.building_value) {
        updateData.building_value = typeof data.building_value === 'string' 
          ? parseFloat(data.building_value) 
          : data.building_value;
      }
      if (data.construction_year) {
        updateData.construction_year = typeof data.construction_year === 'string' 
          ? parseInt(data.construction_year) 
          : data.construction_year;
      }
      if (data.depreciation_rate) {
        updateData.depreciation_rate = typeof data.depreciation_rate === 'string' 
          ? parseFloat(data.depreciation_rate) / 100 // Convert percentage to decimal
          : data.depreciation_rate / 100;
      }
      if (data.grunderwerbsteuer) {
        updateData.grunderwerbsteuer = typeof data.grunderwerbsteuer === 'string' 
          ? parseFloat(data.grunderwerbsteuer) 
          : data.grunderwerbsteuer;
      }
      if (data.notary_fees) {
        updateData.notary_fees = typeof data.notary_fees === 'string' 
          ? parseFloat(data.notary_fees) 
          : data.notary_fees;
      }
      if (data.registry_fees) {
        updateData.registry_fees = typeof data.registry_fees === 'string' 
          ? parseFloat(data.registry_fees) 
          : data.registry_fees;
      }

      await updateProperty(editingProperty.id, updateData);
      setEditingProperty(undefined);
      setShowForm(false);
      // Refresh property detail if viewing one
      if (propertyId) {
        fetchProperty(propertyId);
      } else {
        // Refresh list
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

  const handleArchiveProperty = async (property: Property) => {
    const saleDate = prompt(t('properties.enterSaleDate'), new Date().toISOString().split('T')[0]);
    
    if (!saleDate) return;
    
    try {
      await archiveProperty(property.id, saleDate);
      // Refresh list or detail view
      if (propertyId) {
        navigate('/properties');
      } else {
        fetchProperties();
      }
    } catch (error) {
      console.error('Failed to archive property:', error);
      alert(t('properties.archiveError'));
    }
  };

  const handleDeleteProperty = async (id: string) => {
    try {
      await deleteProperty(id);
      // Refresh list
      fetchProperties();
    } catch (error) {
      console.error('Failed to delete property:', error);
      alert(t('properties.deleteError'));
    }
  };

  const handleBackToList = () => {
    navigate('/properties');
  };

  // Show property detail view if propertyId in URL
  if (propertyId && selectedProperty) {
    // If editing this property, show form instead
    if (showForm && editingProperty?.id === selectedProperty.id) {
      return (
        <div className="properties-page">
          <div className="properties-header">
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
      <div className="properties-header">
        <div className="properties-title">
          <h1>{t('properties.title')}</h1>
          <p className="properties-subtitle">{t('properties.manageYourProperties')}</p>
        </div>
        <div className="properties-actions">
          {!showForm && properties.length > 0 && (
            <button
              className="btn btn-secondary"
              onClick={() => navigate('/properties/portfolio')}
            >
              📊 {t('properties.portfolio.title')}
            </button>
          )}
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
          <button onClick={clearError} className="error-close">×</button>
        </div>
      )}

      {showForm && (
        <div className="property-form-container">
          <PropertyForm
            property={editingProperty}
            onSubmit={editingProperty ? handleUpdateProperty : handleCreateProperty}
            onCancel={handleCancelForm}
          />
        </div>
      )}

      {!showForm && (
        <PropertyList
          properties={properties}
          isLoading={isLoading}
          onView={handleViewProperty}
          onEdit={handleEditProperty}
          onArchive={handleArchiveProperty}
          onDelete={handleDeleteProperty}
        />
      )}
    </div>
  );
};

export default PropertiesPage;
