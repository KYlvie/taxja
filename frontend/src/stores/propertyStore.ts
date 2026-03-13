import { create } from 'zustand';
import { Property, PropertyCreate, PropertyUpdate, PropertyDetailResponse, PropertyStatus } from '../types/property';
import { propertyService } from '../services/propertyService';

interface PropertyState {
  properties: Property[];
  selectedProperty: PropertyDetailResponse | null;
  isLoading: boolean;
  error: string | null;
  includeArchived: boolean;

  // Actions
  fetchProperties: (includeArchived?: boolean) => Promise<void>;
  fetchProperty: (id: string) => Promise<void>;
  createProperty: (data: PropertyCreate) => Promise<Property>;
  updateProperty: (id: string, data: PropertyUpdate) => Promise<Property>;
  archiveProperty: (id: string, saleDate: string) => Promise<Property>;
  deleteProperty: (id: string) => Promise<void>;
  selectProperty: (id: string | null) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  setIncludeArchived: (includeArchived: boolean) => void;
  clearError: () => void;
}

export const usePropertyStore = create<PropertyState>((set, get) => ({
  properties: [],
  selectedProperty: null,
  isLoading: false,
  error: null,
  includeArchived: false,

  /**
   * Fetch all properties for the current user
   */
  fetchProperties: async (includeArchived = false) => {
    set({ isLoading: true, error: null });
    try {
      const response = await propertyService.getProperties(includeArchived);
      // Cast PropertyListItem[] to Property[] - the list items are a subset of full Property
      set({
        properties: response.properties as Property[],
        includeArchived: response.include_archived,
        isLoading: false,
      });
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to fetch properties';
      set({ error: errorMessage, isLoading: false });
      throw error;
    }
  },

  /**
   * Fetch a single property by ID with metrics
   */
  fetchProperty: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const property = await propertyService.getProperty(id);
      set({
        selectedProperty: property,
        isLoading: false,
      });
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to fetch property';
      set({ error: errorMessage, isLoading: false });
      throw error;
    }
  },

  /**
   * Create a new property with optimistic update
   */
  createProperty: async (data: PropertyCreate) => {
    set({ isLoading: true, error: null });
    try {
      const newProperty = await propertyService.createProperty(data);
      
      // Optimistic update: add to local state
      set((state) => ({
        properties: [newProperty, ...state.properties],
        isLoading: false,
      }));

      return newProperty;
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to create property';
      set({ error: errorMessage, isLoading: false });
      throw error;
    }
  },

  /**
   * Update an existing property with optimistic update
   */
  updateProperty: async (id: string, data: PropertyUpdate) => {
    set({ isLoading: true, error: null });
    
    // Store original state for rollback
    const originalProperties = get().properties;
    const originalSelected = get().selectedProperty;

    try {
      // Optimistic update: update local state immediately
      set((state) => ({
        properties: state.properties.map((p) =>
          p.id === id ? { ...p, ...data } : p
        ),
        selectedProperty: state.selectedProperty?.id === id
          ? { ...state.selectedProperty, ...data }
          : state.selectedProperty,
      }));

      const updatedProperty = await propertyService.updateProperty(id, data);
      
      // Update with actual server response
      set((state) => ({
        properties: state.properties.map((p) =>
          p.id === id ? updatedProperty : p
        ),
        selectedProperty: state.selectedProperty?.id === id
          ? { ...state.selectedProperty, ...updatedProperty }
          : state.selectedProperty,
        isLoading: false,
      }));

      return updatedProperty;
    } catch (error: any) {
      // Rollback on error
      set({
        properties: originalProperties,
        selectedProperty: originalSelected,
        error: error.response?.data?.detail || error.message || 'Failed to update property',
        isLoading: false,
      });
      throw error;
    }
  },

  /**
   * Archive a property (mark as sold) with optimistic update
   */
  archiveProperty: async (id: string, saleDate: string) => {
    set({ isLoading: true, error: null });
    
    // Store original state for rollback
    const originalProperties = get().properties;
    const originalSelected = get().selectedProperty;

    try {
      // Optimistic update: mark as archived immediately
      set((state) => ({
        properties: state.properties.map((p) =>
          p.id === id ? { ...p, status: PropertyStatus.ARCHIVED, sale_date: saleDate } : p
        ),
        selectedProperty: state.selectedProperty?.id === id
          ? { ...state.selectedProperty, status: PropertyStatus.ARCHIVED, sale_date: saleDate }
          : state.selectedProperty,
      }));

      const archivedProperty = await propertyService.archiveProperty(id, saleDate);
      
      // Update with actual server response
      set((state) => ({
        properties: state.properties.map((p) =>
          p.id === id ? archivedProperty : p
        ),
        selectedProperty: state.selectedProperty?.id === id
          ? { ...state.selectedProperty, ...archivedProperty }
          : state.selectedProperty,
        isLoading: false,
      }));

      return archivedProperty;
    } catch (error: any) {
      // Rollback on error
      set({
        properties: originalProperties,
        selectedProperty: originalSelected,
        error: error.response?.data?.detail || error.message || 'Failed to archive property',
        isLoading: false,
      });
      throw error;
    }
  },

  /**
   * Delete a property with optimistic update
   */
  deleteProperty: async (id: string) => {
    set({ isLoading: true, error: null });
    
    // Store original state for rollback
    const originalProperties = get().properties;
    const originalSelected = get().selectedProperty;

    try {
      // Optimistic update: remove from local state immediately
      set((state) => ({
        properties: state.properties.filter((p) => p.id !== id),
        selectedProperty: state.selectedProperty?.id === id ? null : state.selectedProperty,
      }));

      await propertyService.deleteProperty(id);
      
      set({ isLoading: false });
    } catch (error: any) {
      // Rollback on error
      set({
        properties: originalProperties,
        selectedProperty: originalSelected,
        error: error.response?.data?.detail || error.message || 'Failed to delete property',
        isLoading: false,
      });
      throw error;
    }
  },

  /**
   * Select a property by ID (loads from local state)
   */
  selectProperty: (id: string | null) => {
    if (id === null) {
      set({ selectedProperty: null });
      return;
    }

    const property = get().properties.find((p) => p.id === id);
    if (property) {
      set({ selectedProperty: property });
    }
  },

  /**
   * Set loading state
   */
  setLoading: (isLoading: boolean) => set({ isLoading }),

  /**
   * Set error message
   */
  setError: (error: string | null) => set({ error }),

  /**
   * Set includeArchived filter
   */
  setIncludeArchived: (includeArchived: boolean) => set({ includeArchived }),

  /**
   * Clear error message
   */
  clearError: () => set({ error: null }),
}));
