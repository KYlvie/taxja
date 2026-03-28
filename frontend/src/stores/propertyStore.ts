import { isAxiosError } from 'axios';
import { create } from 'zustand';
import {
  DisposalRequest,
  Property,
  PropertyCreate,
  PropertyDetailResponse,
  PropertyStatus,
  PropertyUpdate,
} from '../types/property';
import { getErrorMessage, propertyService } from '../services/propertyService';

interface PropertyState {
  properties: Property[];
  selectedProperty: PropertyDetailResponse | null;
  isLoading: boolean;
  error: string | null;
  includeArchived: boolean;

  fetchProperties: (includeArchived?: boolean) => Promise<void>;
  fetchProperty: (id: string) => Promise<void>;
  createProperty: (data: PropertyCreate) => Promise<Property>;
  updateProperty: (id: string, data: PropertyUpdate) => Promise<Property>;
  archiveProperty: (id: string, saleDate: string) => Promise<Property>;
  disposeProperty: (id: string, data: DisposalRequest) => Promise<Property>;
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

  fetchProperties: async (includeArchived = false) => {
    set({ isLoading: true, error: null });
    try {
      const response = await propertyService.getProperties(includeArchived);
      set({
        properties: response.properties as Property[],
        includeArchived: response.include_archived,
        isLoading: false,
      });
    } catch (error: unknown) {
      set({
        error: getErrorMessage(error, 'Failed to fetch properties'),
        isLoading: false,
      });
      throw error;
    }
  },

  fetchProperty: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const property = await propertyService.getProperty(id);
      set({
        selectedProperty: property,
        isLoading: false,
      });
    } catch (error: unknown) {
      set({
        error: getErrorMessage(error, 'Failed to fetch property'),
        isLoading: false,
      });
      throw error;
    }
  },

  createProperty: async (data: PropertyCreate) => {
    set({ isLoading: true, error: null });
    try {
      const newProperty = await propertyService.createProperty(data);
      set((state) => ({
        properties: [newProperty, ...state.properties],
        isLoading: false,
      }));
      return newProperty;
    } catch (error: unknown) {
      set({
        error: getErrorMessage(error, 'Failed to create property'),
        isLoading: false,
      });
      throw error;
    }
  },

  updateProperty: async (id: string, data: PropertyUpdate) => {
    set({ isLoading: true, error: null });

    const originalProperties = get().properties;
    const originalSelected = get().selectedProperty;

    try {
      set((state) => ({
        properties: state.properties.map((property) => (
          property.id === id ? { ...property, ...data } : property
        )),
        selectedProperty: state.selectedProperty?.id === id
          ? { ...state.selectedProperty, ...data }
          : state.selectedProperty,
      }));

      const updatedProperty = await propertyService.updateProperty(id, data);

      set((state) => ({
        properties: state.properties.map((property) => (
          property.id === id ? updatedProperty : property
        )),
        selectedProperty: state.selectedProperty?.id === id
          ? { ...state.selectedProperty, ...updatedProperty }
          : state.selectedProperty,
        isLoading: false,
      }));

      return updatedProperty;
    } catch (error: unknown) {
      set({
        properties: originalProperties,
        selectedProperty: originalSelected,
        error: getErrorMessage(error, 'Failed to update property'),
        isLoading: false,
      });
      throw error;
    }
  },

  archiveProperty: async (id: string, saleDate: string) => {
    set({ isLoading: true, error: null });

    const originalProperties = get().properties;
    const originalSelected = get().selectedProperty;

    try {
      set((state) => ({
        properties: state.properties.map((property) => (
          property.id === id
            ? { ...property, status: PropertyStatus.ARCHIVED, sale_date: saleDate }
            : property
        )),
        selectedProperty: state.selectedProperty?.id === id
          ? { ...state.selectedProperty, status: PropertyStatus.ARCHIVED, sale_date: saleDate }
          : state.selectedProperty,
      }));

      const archivedProperty = await propertyService.archiveProperty(id, saleDate);

      set((state) => ({
        properties: state.properties.map((property) => (
          property.id === id ? archivedProperty : property
        )),
        selectedProperty: state.selectedProperty?.id === id
          ? { ...state.selectedProperty, ...archivedProperty }
          : state.selectedProperty,
        isLoading: false,
      }));

      return archivedProperty;
    } catch (error: unknown) {
      set({
        properties: originalProperties,
        selectedProperty: originalSelected,
        error: getErrorMessage(error, 'Failed to archive property'),
        isLoading: false,
      });
      throw error;
    }
  },

  disposeProperty: async (id: string, data: DisposalRequest) => {
    set({ isLoading: true, error: null });

    const originalProperties = get().properties;
    const originalSelected = get().selectedProperty;

    try {
      const disposedProperty = await propertyService.disposeProperty(id, data);

      set((state) => ({
        properties: state.properties.map((property) => (
          property.id === id ? disposedProperty : property
        )),
        selectedProperty: state.selectedProperty?.id === id
          ? { ...state.selectedProperty, ...disposedProperty }
          : state.selectedProperty,
        isLoading: false,
      }));

      return disposedProperty;
    } catch (error: unknown) {
      set({
        properties: originalProperties,
        selectedProperty: originalSelected,
        error: getErrorMessage(error, 'Failed to dispose property'),
        isLoading: false,
      });
      throw error;
    }
  },

  deleteProperty: async (id: string) => {
    set({ isLoading: true, error: null });

    const originalProperties = get().properties;
    const originalSelected = get().selectedProperty;

    try {
      set((state) => ({
        properties: state.properties.filter((property) => property.id !== id),
        selectedProperty: state.selectedProperty?.id === id ? null : state.selectedProperty,
      }));

      await propertyService.deleteProperty(id);
      set({ isLoading: false });
    } catch (error: unknown) {
      if (isAxiosError(error) && error.response?.status === 404) {
        set({ isLoading: false });
        return;
      }

      const message = getErrorMessage(error, 'Failed to delete property');
      set({
        properties: originalProperties,
        selectedProperty: originalSelected,
        error: message,
        isLoading: false,
      });
      throw error;
    }
  },

  selectProperty: (id: string | null) => {
    if (id === null) {
      set({ selectedProperty: null });
      return;
    }

    const property = get().properties.find((candidate) => candidate.id === id);
    if (property) {
      set({ selectedProperty: property });
    }
  },

  setLoading: (isLoading: boolean) => set({ isLoading }),
  setError: (error: string | null) => set({ error }),
  setIncludeArchived: (includeArchived: boolean) => set({ includeArchived }),
  clearError: () => set({ error: null }),
}));
