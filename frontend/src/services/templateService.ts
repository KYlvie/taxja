import api from './api';
import { RecurringTemplate, CreateFromTemplateRequest } from '../types/template';
import { RecurringTransaction } from '../types/recurring';

export const templateService = {
  async getAllTemplates(): Promise<RecurringTemplate[]> {
    const response = await api.get('/recurring-transactions/templates/all');
    return response.data;
  },

  async createFromTemplate(data: CreateFromTemplateRequest): Promise<RecurringTransaction> {
    const response = await api.post('/recurring-transactions/from-template', data);
    return response.data;
  },
};
