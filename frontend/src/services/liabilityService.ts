import api from './api';
import {
  LiabilityCreatePayload,
  LiabilityDetail,
  LiabilityListResponse,
  LiabilityRecord,
  LiabilitySummary,
  LiabilityUpdatePayload,
} from '../types/liability';

const toNumber = (value: unknown): number => Number(value ?? 0);

interface LiabilityRelatedTransactionRaw extends Record<string, unknown> {
  amount?: unknown;
}

interface LiabilityRaw extends Record<string, unknown> {
  source_type?: string;
  principal_amount?: unknown;
  outstanding_balance?: unknown;
  interest_rate?: unknown;
  monthly_payment?: unknown;
  can_edit_directly?: boolean;
  can_deactivate_directly?: boolean;
  edit_via_document?: boolean;
  requires_supporting_document?: boolean;
  recommended_document_type?: string;
  related_transactions?: LiabilityRelatedTransactionRaw[];
  related_recurring_transactions?: LiabilityRelatedTransactionRaw[];
}

const mapRelatedAmount = (item: LiabilityRelatedTransactionRaw) => ({
  ...item,
  amount: toNumber(item.amount),
});

const mapLiability = (raw: LiabilityRaw): LiabilityRecord => ({
  ...raw,
  source_type: raw.source_type || 'manual',
  principal_amount: toNumber(raw.principal_amount),
  outstanding_balance: toNumber(raw.outstanding_balance),
  interest_rate: raw.interest_rate == null ? null : toNumber(raw.interest_rate),
  monthly_payment: raw.monthly_payment == null ? null : toNumber(raw.monthly_payment),
  can_edit_directly: raw.can_edit_directly ?? true,
  can_deactivate_directly: raw.can_deactivate_directly ?? true,
  edit_via_document: raw.edit_via_document ?? false,
  requires_supporting_document: raw.requires_supporting_document ?? false,
  recommended_document_type: raw.recommended_document_type || 'loan_contract',
});

const mapLiabilityDetail = (raw: LiabilityRaw): LiabilityDetail => ({
  ...mapLiability(raw),
  related_transactions: (raw.related_transactions || []).map(mapRelatedAmount),
  related_recurring_transactions: (raw.related_recurring_transactions || []).map(mapRelatedAmount),
});

export const liabilityService = {
  async getSummary(): Promise<LiabilitySummary> {
    const response = await api.get('/liabilities/summary');
    return {
      total_assets: toNumber(response.data.total_assets),
      total_liabilities: toNumber(response.data.total_liabilities),
      net_worth: toNumber(response.data.net_worth),
      active_liability_count: Number(response.data.active_liability_count || 0),
      monthly_debt_service: toNumber(response.data.monthly_debt_service),
      annual_deductible_interest: toNumber(response.data.annual_deductible_interest),
    };
  },

  async list(includeInactive = false): Promise<LiabilityListResponse> {
    const response = await api.get('/liabilities', {
      params: { include_inactive: includeInactive },
    });
    return {
      total: Number(response.data.total || 0),
      active_count: Number(response.data.active_count || 0),
      items: (response.data.items || []).map(mapLiability),
    };
  },

  async get(id: number): Promise<LiabilityDetail> {
    const response = await api.get(`/liabilities/${id}`);
    return mapLiabilityDetail(response.data);
  },

  async create(payload: LiabilityCreatePayload): Promise<LiabilityRecord> {
    const response = await api.post('/liabilities', payload);
    return mapLiability(response.data);
  },

  async update(id: number, payload: LiabilityUpdatePayload): Promise<LiabilityRecord> {
    const response = await api.put(`/liabilities/${id}`, payload);
    return mapLiability(response.data);
  },

  async remove(id: number): Promise<LiabilityRecord> {
    const response = await api.delete(`/liabilities/${id}`);
    return mapLiability(response.data);
  },
};
