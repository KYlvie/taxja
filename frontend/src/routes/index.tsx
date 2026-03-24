import { createBrowserRouter, Navigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import AppLayout from '../components/layout/AppLayout';
import HomePage from '../pages/HomePage';
import LoginPage from '../pages/auth/LoginPage';
import RegisterPage from '../pages/auth/RegisterPage';
import ForgotPasswordPage from '../pages/auth/ForgotPasswordPage';
import ResetPasswordPage from '../pages/auth/ResetPasswordPage';
import VerifyEmailPage from '../pages/auth/VerifyEmailPage';
import TwoFactorSetupPage from '../pages/auth/TwoFactorSetupPage';
import DashboardPage from '../pages/DashboardPage';
import TransactionsPage from '../pages/TransactionsPage';
import DocumentsPage from '../pages/DocumentsPage';
import ReportsPage from '../pages/ReportsPage';
import ProfilePage from '../pages/ProfilePage';
import PropertiesPage from '../pages/PropertiesPage';
import AssetInsightsPage from '../pages/AssetInsightsPage';
import LiabilitiesPage from '../pages/LiabilitiesPage';
import LiabilityOverviewPage from '../pages/LiabilityOverviewPage';
import PricingPage from '../pages/PricingPage';
import CheckoutSuccess from '../pages/CheckoutSuccess';
import AdvancedManagementPage from '../pages/AdvancedManagementPage';
import TaxToolsPage from '../pages/TaxToolsPage';
import TaxConfigAdmin from '../pages/admin/TaxConfigAdmin';
import AdminDashboard from '../pages/admin/AdminDashboard';
import RecurringTransactionsPage from '../pages/RecurringTransactionsPage';
import AIAssistantPage from '../pages/AIAssistantPage';
import SubscriptionManagement from '../pages/SubscriptionManagement';
import DeleteAccountWizard from '../components/account/DeleteAccountWizard';
import LegalPage from '../pages/LegalPage';
import CompanyPage from '../pages/CompanyPage';
import ClassificationRulesPage from '../pages/ClassificationRulesPage';
import CreditHistoryPage from '../pages/CreditHistoryPage';

// Protected route wrapper
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
};

// Admin route wrapper — redirects non-admin users to dashboard
const AdminRoute = ({ children }: { children: React.ReactNode }) => {
  const user = useAuthStore((state) => state.user);
  
  if (!user?.is_admin) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return <>{children}</>;
};

const CatchAllRoute = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return <Navigate to={isAuthenticated ? '/dashboard' : '/'} replace />;
};

export const router = createBrowserRouter([
  {
    path: '/',
    element: <HomePage />,
  },
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/register',
    element: <RegisterPage />,
  },
  {
    path: '/forgot-password',
    element: <ForgotPasswordPage />,
  },
  {
    path: '/reset-password',
    element: <ResetPasswordPage />,
  },
  {
    path: '/verify-email',
    element: <VerifyEmailPage />,
  },
  {
    path: '/legal/:type',
    element: <LegalPage />,
  },
  {
    path: '/company',
    element: <CompanyPage />,
  },
  {
    path: '/pricing',
    element: <PricingPage />,
  },
  {
    path: '/checkout/success',
    element: <CheckoutSuccess />,
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
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
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
        element: <AssetInsightsPage />,
      },
      {
        path: 'properties/comparison',
        element: <Navigate to="/properties/portfolio#comparison" replace />,
      },
      {
        path: 'liabilities',
        element: <LiabilitiesPage />,
      },
      {
        path: 'liabilities/overview',
        element: <LiabilityOverviewPage />,
      },
      {
        path: 'liabilities/new',
        element: <LiabilitiesPage />,
      },
      {
        path: 'liabilities/:id',
        element: <LiabilitiesPage />,
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
        path: 'advanced',
        element: <AdvancedManagementPage />,
      },
      {
        path: 'tax-tools',
        element: <TaxToolsPage />,
      },
      {
        path: 'profile',
        element: <ProfilePage />,
      },
      {
        path: 'admin/tax-configs',
        element: <AdminRoute><TaxConfigAdmin /></AdminRoute>,
      },
      {
        path: 'admin',
        element: <AdminRoute><AdminDashboard /></AdminRoute>,
      },
      {
        path: 'ai-assistant',
        element: <AIAssistantPage />,
      },
      {
        path: 'subscription/manage',
        element: <SubscriptionManagement />,
      },
      {
        path: 'credits/history',
        element: <CreditHistoryPage />,
      },
      {
        path: 'documents/upload',
        element: <DocumentsPage />,
      },
      {
        path: 'transactions/new',
        element: <TransactionsPage />,
      },
      {
        path: 'classification-rules',
        element: <ClassificationRulesPage />,
      },
      {
        path: 'account/delete',
        element: <DeleteAccountWizard />,
      },
    ],
  },
  {
    path: '*',
    element: <CatchAllRoute />,
  },
]);
