export interface RecurringTemplate {
  id: string;
  name_de: string;
  name_en: string;
  name_zh: string;
  description_de: string;
  description_en: string;
  description_zh: string;
  transaction_type: 'income' | 'expense';
  category: string;
  frequency: string;
  default_day_of_month: number;
  icon: string;
  priority: number;
}

export interface CreateFromTemplateRequest {
  template_id: string;
  amount: number;
  start_date: string;
  end_date?: string;
  day_of_month?: number;
  notes?: string;
}
