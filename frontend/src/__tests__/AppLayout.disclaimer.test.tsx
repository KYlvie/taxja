/* @vitest-environment jsdom */

import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AppLayout from '../components/layout/AppLayout';
import { useAuthStore } from '../stores/authStore';

vi.mock('../components/layout/Header', () => ({
  default: () => <div data-testid="header" />,
}));

vi.mock('../components/layout/Sidebar', () => ({
  default: () => <div data-testid="sidebar" />,
}));

vi.mock('../components/layout/MobileBottomNav', () => ({
  default: () => <div data-testid="mobile-nav" />,
}));

vi.mock('../components/ai/FloatingAIChat', () => ({
  default: () => <div data-testid="floating-chat" />,
}));

vi.mock('../components/common/DisclaimerModal', () => ({
  default: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="disclaimer-modal">Disclaimer</div> : null,
}));

vi.mock('../components/common/DraggableRobot', () => ({
  default: () => <button type="button">robot</button>,
}));

vi.mock('../components/onboarding/OnboardingGuide', () => ({
  default: () => <div data-testid="onboarding-guide" />,
}));

vi.mock('../components/onboarding/tourConfigs', () => ({
  getPageTourSteps: vi.fn(() => undefined),
}));

vi.mock('../hooks/useCyberTilt', () => ({
  useCyberTilt: () => ({
    ref: { current: null },
    onMove: vi.fn(),
    onLeave: vi.fn(),
  }),
}));

const renderLayout = () =>
  render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route path="dashboard" element={<div>dashboard</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );

describe('AppLayout disclaimer gating', () => {
  beforeEach(() => {
    sessionStorage.clear();
    useAuthStore.setState({
      user: {
        id: 1,
        email: 'user@example.com',
        name: 'Test User',
        user_type: 'self_employed',
        onboarding_completed: false,
        two_factor_enabled: false,
      },
      token: 'token',
      isAuthenticated: true,
    });
  });

  it('shows the disclaimer immediately after login even when onboarding is unfinished', () => {
    renderLayout();

    expect(screen.getByTestId('disclaimer-modal')).toBeInTheDocument();
  });

  it('keeps the disclaimer hidden after acceptance within the same login session', () => {
    sessionStorage.setItem('taxja_disclaimer_accepted', '1');

    renderLayout();

    expect(screen.queryByTestId('disclaimer-modal')).not.toBeInTheDocument();
  });
});
