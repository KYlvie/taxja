import api from './api';
import {
  RecurringTransaction,
  RecurringTransactionListResponse,
  RentalIncomeRecurringCreate,
  LoanInterestRecurringCreate,
  RecurringTransactionUpdate,
  RecurringTransactionCreate,
} from '../types/recurring';

export const recurringService = {
  // List all recurring transactions
  async list(activeOnly: boolean = true): Promise<RecurringTransactionListResponse> {
    const response = await api.get('/recurring-transactions', {
      params: { active_only: activeOnly },
    });
    return response.data;
  },

  // Get a specific recurring transaction
  async get(id: number): Promise<RecurringTransaction> {
    const response = await api.get(`/recurring-transactions/${id}`);
    return response.data;
  },

  // Create a generic recurring transaction
  async create(data: RecurringTransactionCreate): Promise<RecurringTransaction> {
    const response = await api.post('/recurring-transactions', data);
    return response.data;
  },

  // Create rental income recurring transaction
  async createRentalIncome(data: RentalIncomeRecurringCreate): Promise<RecurringTransaction> {
    const response = await api.post('/recurring-transactions/rental-income', data);
    return response.data;
  },

  // Create loan interest recurring transaction
  async createLoanInterest(data: LoanInterestRecurringCreate): Promise<RecurringTransaction> {
    const response = await api.post('/recurring-transactions/loan-interest', data);
    return response.data;
  },

  // Update recurring transaction
  async update(id: number, data: RecurringTransactionUpdate): Promise<RecurringTransaction> {
    const response = await api.put(`/recurring-transactions/${id}`, data);
    return response.data;
  },

  // Pause recurring transaction
  async pause(id: number): Promise<RecurringTransaction> {
    const response = await api.post(`/recurring-transactions/${id}/pause`);
    return response.data;
  },

  // Resume recurring transaction
  async resume(id: number): Promise<RecurringTransaction> {
    const response = await api.post(`/recurring-transactions/${id}/resume`);
    return response.data;
  },

  // Stop recurring transaction
  async stop(id: number): Promise<RecurringTransaction> {
    const response = await api.post(`/recurring-transactions/${id}/stop`);
    return response.data;
  },

  // Delete recurring transaction
  async delete(id: number): Promise<void> {
    await api.delete(`/recurring-transactions/${id}`);
  },

  // Get recurring transactions for a property
  async getByProperty(propertyId: string, activeOnly: boolean = true): Promise<RecurringTransaction[]> {
    const response = await api.get(`/recurring-transactions/property/${propertyId}`, {
      params: { active_only: activeOnly },
    });
    return response.data;
  },
};
