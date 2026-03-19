/* @vitest-environment jsdom */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import SubpageBackLink from '../components/common/SubpageBackLink';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => (typeof fallback === 'string' ? fallback : 'Back'),
  }),
}));

describe('SubpageBackLink', () => {
  it('renders a consistent back link with the target route', () => {
    render(
      <MemoryRouter>
        <SubpageBackLink to="/advanced" />
      </MemoryRouter>,
    );

    const link = screen.getByRole('link', { name: /Back/i });
    expect(link).toHaveAttribute('href', '/advanced');
    expect(link.textContent).toContain('←');
  });
});
