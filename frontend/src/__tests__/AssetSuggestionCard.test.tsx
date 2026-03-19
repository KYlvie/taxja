/* @vitest-environment jsdom */

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import AssetSuggestionCard from '../components/documents/suggestion-cards/AssetSuggestionCard';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: any) => (typeof fallback === 'string' ? fallback : key),
  }),
}));

describe('AssetSuggestionCard', () => {
  it('submits the enriched asset confirmation payload', () => {
    const onConfirm = vi.fn();

    render(
      <AssetSuggestionCard
        suggestion={{
          type: 'create_asset',
          status: 'pending',
          data: {
            asset_type: 'computer',
            name: 'Business Laptop',
            purchase_price: 900,
            purchase_date: '2026-03-18',
            supplier: 'Dell',
            decision: 'gwg_suggestion',
            business_use_percentage: 100,
            useful_life_years: 3,
            gwg_eligible: true,
            gwg_default_selected: true,
            gwg_election_required: true,
            allowed_depreciation_methods: ['linear', 'degressive'],
            suggested_depreciation_method: 'linear',
            degressive_max_rate: 0.3,
            missing_fields: ['put_into_use_date'],
            review_reasons: [],
          },
        }}
        confirmResult={null}
        confirmingAction={null}
        onConfirm={onConfirm}
        onDismiss={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText('投入使用日期'), { target: { value: '2026-03-20' } });
    fireEvent.change(screen.getByLabelText('业务使用比例'), { target: { value: '80' } });
    fireEvent.change(screen.getByLabelText('税务处理方式'), { target: { value: 'asset' } });
    fireEvent.change(screen.getByLabelText('折旧方法'), { target: { value: 'degressive' } });
    fireEvent.change(screen.getByLabelText('递减折旧比例'), { target: { value: '0.25' } });
    fireEvent.change(screen.getByLabelText('使用年限'), { target: { value: '4' } });

    fireEvent.click(screen.getByRole('button', { name: /确认并创建资产/ }));

    expect(onConfirm).toHaveBeenCalledWith({
      put_into_use_date: '2026-03-20',
      business_use_percentage: 80,
      gwg_elected: false,
      depreciation_method: 'degressive',
      degressive_afa_rate: 0.25,
      useful_life_years: 4,
    });
  });

  it('requires used vehicle history before confirming a used vehicle', () => {
    const onConfirm = vi.fn();

    render(
      <AssetSuggestionCard
        suggestion={{
          type: 'create_asset',
          status: 'pending',
          data: {
            asset_type: 'vehicle',
            sub_category: 'pkw',
            name: 'Used Car',
            purchase_price: 18000,
            purchase_date: '2026-03-18',
            business_use_percentage: 100,
            allowed_depreciation_methods: ['linear'],
            suggested_depreciation_method: 'linear',
            missing_fields: ['put_into_use_date'],
            review_reasons: ['used_vehicle_history_missing'],
          },
        }}
        confirmResult={null}
        confirmingAction={null}
        onConfirm={onConfirm}
        onDismiss={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText('投入使用日期'), { target: { value: '2026-03-20' } });
    fireEvent.click(screen.getByRole('button', { name: /确认并创建资产/ }));

    expect(onConfirm).not.toHaveBeenCalled();
    expect(
      screen.getByText('二手车辆需要首次登记日期或前任使用年限，才能正确计算折旧。')
    ).toBeInTheDocument();
  });
});
