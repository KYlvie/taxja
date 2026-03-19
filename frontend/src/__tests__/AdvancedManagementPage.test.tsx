/* @vitest-environment jsdom */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import AdvancedManagementPage from '../pages/AdvancedManagementPage';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : key),
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

describe('AdvancedManagementPage', () => {
  it('shows four standard cards and routes payroll-related work through tax tools', () => {
    render(
      <MemoryRouter>
        <AdvancedManagementPage />
      </MemoryRouter>,
    );

    expect(screen.getByText('Asset Management')).toBeInTheDocument();
    expect(screen.getByText('Automatic Rules')).toBeInTheDocument();
    expect(screen.getByText('AI Classification Rules')).toBeInTheDocument();
    expect(screen.getByText('Tax Tools')).toBeInTheDocument();
    expect(screen.queryByText('Payroll Files')).not.toBeInTheDocument();

    const taxToolsLink = screen.getByRole('link', { name: 'Open' });
    expect(taxToolsLink).toHaveAttribute('href', '/tax-tools');
    expect(screen.getByText('Tax position, AI guidance, payroll files and asset reports')).toBeInTheDocument();
  });
});
