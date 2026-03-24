/* @vitest-environment jsdom */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import AdvancedManagementPage from '../pages/AdvancedManagementPage';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: { language: 'en', resolvedLanguage: 'en' },
  }),
}));

describe('AdvancedManagementPage', () => {
  it('exposes asset and liability management as separate actions inside one card', () => {
    render(
      <MemoryRouter>
        <AdvancedManagementPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Asset & Liability Management' })).toBeInTheDocument();
    expect(
      screen.getByText('Assets, loans, borrowings, and clear module boundaries'),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Manage Assets' })).toHaveAttribute('href', '/properties');
    expect(screen.getByRole('link', { name: 'Manage Liabilities' })).toHaveAttribute(
      'href',
      '/liabilities',
    );
    expect(screen.queryByRole('link', { name: 'Overview & Compare' })).not.toBeInTheDocument();

    expect(screen.getByRole('heading', { name: 'Tax Workspace' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open Workspace' })).toHaveAttribute(
      'href',
      '/tax-tools',
    );
  });
});
