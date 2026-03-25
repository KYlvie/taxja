import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ReportsPage from '../pages/ReportsPage';
import { transactionService } from '../services/transactionService';
import { useFeatureAccess } from '../components/subscription/withFeatureGate';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const copy: Record<string, string> = {
        'nav.reports': 'Reports',
        'reports.tabs.ea': 'EA',
        'reports.tabs.bilanz': 'Bilanz',
        'reports.tabs.taxForm': 'Tax form',
        'reports.tabs.saldenliste': 'Saldenliste',
        'reports.tabs.periodensaldenliste': 'Periodensaldenliste',
        'reports.reviewTransactions': 'Review transactions',
      };
      return copy[key] ?? key;
    },
  }),
}));

vi.mock('../services/transactionService', () => ({
  transactionService: {
    getAll: vi.fn(),
  },
}));

vi.mock('../stores/authStore', () => ({
  useAuthStore: () => ({
    user: {
      user_type: 'self_employed',
    },
  }),
}));

vi.mock('../components/subscription/withFeatureGate', () => ({
  useFeatureAccess: vi.fn(),
}));

vi.mock('../components/common/FuturisticIcon', () => ({
  default: () => <span data-testid="futuristic-icon" />,
}));

vi.mock('../components/reports/EAReport', () => ({
  default: () => <div>EA Report</div>,
}));

vi.mock('../components/reports/BilanzReport', () => ({
  default: () => <div>Bilanz Report</div>,
}));

vi.mock('../components/reports/SaldenlisteReport', () => ({
  default: () => <div>Saldenliste Report</div>,
}));

vi.mock('../components/reports/PeriodensaldenlisteReport', () => ({
  default: () => <div>Periodensaldenliste Report</div>,
}));

vi.mock('../components/reports/TaxFormPreview', () => ({
  default: () => <div>Tax Form Preview</div>,
}));

describe('ReportsPage feature gating', () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.mocked(transactionService.getAll).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 1,
      total_pages: 0,
    } as any);
  });

  it('shows a locked tax form tab and still lets users open the tax form area', async () => {
    vi.mocked(useFeatureAccess).mockReturnValue(false);

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(transactionService.getAll).toHaveBeenCalled();
    });

    expect(screen.getByText('Tax form')).toBeInTheDocument();
    expect(screen.getByText('PRO')).toBeInTheDocument();

    screen.getByRole('button', { name: /tax form/i }).click();

    expect(await screen.findByText('Tax Form Preview')).toBeInTheDocument();
  });

  it('shows tax form tab for users with e1_generation access', async () => {
    vi.mocked(useFeatureAccess).mockReturnValue(true);

    render(
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(transactionService.getAll).toHaveBeenCalled();
    });

    expect(screen.getAllByText('Tax form').length).toBeGreaterThan(0);
    expect(screen.queryByText('PRO')).not.toBeInTheDocument();
  });
});
