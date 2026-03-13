import { createBrowserRouter, Navigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import AppLayout from '../components/layout/AppLayout';
import LoginPage from '../pages/auth/LoginPage';
import RegisterPage from '../pages/auth/RegisterPage';
import TwoFactorSetupPage from '../pages/auth/TwoFactorSetupPage';
import DashboardPage from '../pages/DashboardPage';
import TransactionsPage from '../pages/TransactionsPage';
import DocumentsPage from '../pages/DocumentsPage';
import ReportsPage from '../pages/ReportsPage';
import ProfilePage from '../pages/ProfilePage';
import PropertiesPage from '../pages/PropertiesPage';
import PricingPage from '../pages/PricingPage';
import CheckoutSuccess from '../pages/CheckoutSuccess';
import { PropertyPortfolioDashboard } from '../components/properties/PropertyPortfolioDashboard';
import { PropertyComparison } from '../components/properties/PropertyComparison';
import TaxConfigAdmin from '../pages/admin/TaxConfigAdmin';
import RecurringTransactionsPage from '../pages/RecurringTransactionsPage';
import AIAssistantPage from '../pages/AIAssistantPage';

// Protected route wrapper
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
};

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/register',
    element: <RegisterPage />,
  },
  {
    path: '/2fa-setup',
    element: (
      <ProtectedRoute>
        <TwoFactorSetupPage />
      </ProtectedRoute>
    ),
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: 'dashboard',
        element: <DashboardPage />,
      },
      {
        path: 'transactions',
        element: <TransactionsPage />,
      },
      {
        path: 'properties',
        element: <PropertiesPage />,
      },
      {
        path: 'properties/portfolio',
        element: <PropertyPortfolioDashboard />,
      },
      {
        path: 'properties/comparison',
        element: <PropertyComparison />,
      },
      {
        path: 'properties/:propertyId',
        element: <PropertiesPage />,
      },
      {
        path: 'recurring',
        element: <RecurringTransactionsPage />,
      },
      {
        path: 'documents',
        element: <DocumentsPage />,
      },
      {
        path: 'documents/:documentId',
        element: <DocumentsPage />,
      },
      {
        path: 'reports',
        element: <ReportsPage />,
      },
      {
        path: 'profile',
        element: <ProfilePage />,
      },
      {
        path: 'pricing',
        element: <PricingPage />,
      },
      {
        path: 'checkout/success',
        element: <CheckoutSuccess />,
      },
      {
        path: 'admin/tax-configs',
        element: <TaxConfigAdmin />,
      },
      {
        path: 'ai-assistant',
        element: <AIAssistantPage />,
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);
