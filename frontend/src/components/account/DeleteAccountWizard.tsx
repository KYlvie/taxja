import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { useAccountStore } from '../../stores/accountStore';
import { getApiErrorMessage } from '../../utils/apiError';
import SubpageBackLink from '../common/SubpageBackLink';
import './AccountManagement.css';

type WizardStep = 1 | 2 | 3;

const DeleteAccountWizard: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);
  const {
    cancellationImpact,
    exportStatus,
    isLoading,
    error,
    fetchCancellationImpact,
    requestDataExport,
    pollExportStatus,
    deactivateAccount,
    clearError,
  } = useAccountStore();

  const [step, setStep] = useState<WizardStep>(1);
  const [wantExport, setWantExport] = useState(false);
  const [exportPassword, setExportPassword] = useState('');
  const [exportTaskId, setExportTaskId] = useState<string | null>(null);
  const [password, setPassword] = useState('');
  const [confirmationWord, setConfirmationWord] = useState('');
  const [twoFactorCode, setTwoFactorCode] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchCancellationImpact();
  }, [fetchCancellationImpact]);

  // Poll export status when a task is in progress
  useEffect(() => {
    if (!exportTaskId) return;
    if (exportStatus?.status === 'ready' || exportStatus?.status === 'failed') return;

    const interval = setInterval(() => {
      pollExportStatus(exportTaskId);
    }, 3000);

    return () => clearInterval(interval);
  }, [exportTaskId, exportStatus?.status, pollExportStatus]);

  const handleExport = async () => {
    if (!exportPassword.trim()) return;
    try {
      const taskId = await requestDataExport(exportPassword);
      setExportTaskId(taskId);
    } catch {
      // error is set in the store
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');

    if (confirmationWord !== 'DELETE') {
      setSubmitError(t('account.deleteWizard.confirmationMismatch', 'Please type DELETE to confirm.'));
      return;
    }

    setSubmitting(true);
    try {
      await deactivateAccount({
        password,
        confirmation_word: confirmationWord,
        two_factor_code: twoFactorCode || undefined,
      });
      logout();
      navigate('/login?account_deactivated=1', { replace: true });
    } catch (err: any) {
      setSubmitError(getApiErrorMessage(err, t('common.error', 'An error occurred')));
    } finally {
      setSubmitting(false);
    }
  };

  const goNext = () => {
    clearError();
    setStep((s) => Math.min(s + 1, 3) as WizardStep);
  };

  const goBack = () => {
    clearError();
    setStep((s) => Math.max(s - 1, 1) as WizardStep);
  };

  const handleCancel = () => navigate(-1);

  return (
    <div className="wizard-container">
      <SubpageBackLink to="/profile" />
      <h2>{t('account.deleteWizard.title', 'Delete Account')}</h2>

      <div className="wizard-steps-indicator" role="navigation" aria-label="Wizard steps">
        {[1, 2, 3].map((s) => (
          <div
            key={s}
            className={`wizard-step-dot ${step === s ? 'active' : ''} ${step > s ? 'completed' : ''}`}
            aria-current={step === s ? 'step' : undefined}
          >
            {s}
          </div>
        ))}
      </div>

      {/* Step 1: Cancellation Impact Summary */}
      {step === 1 && (
        <div className="wizard-step">
          <h3>{t('account.deleteWizard.step1Title', 'Cancellation Impact')}</h3>
          <p className="wizard-step-desc">
            {t('account.deleteWizard.step1Desc', 'Review the data that will be permanently deleted.')}
          </p>

          {isLoading && <p>{t('common.loading', 'Loading...')}</p>}
          {error && <div className="error-message">{error}</div>}

          {cancellationImpact && (
            <div className="impact-summary">
              <div className="impact-row">
                <span className="impact-label">{t('account.deleteWizard.transactions', 'Transactions')}</span>
                <span className="impact-value">{cancellationImpact.transaction_count}</span>
              </div>
              <div className="impact-row">
                <span className="impact-label">{t('account.deleteWizard.documents', 'Documents')}</span>
                <span className="impact-value">{cancellationImpact.document_count}</span>
              </div>
              <div className="impact-row">
                <span className="impact-label">{t('account.deleteWizard.taxReports', 'Tax Reports')}</span>
                <span className="impact-value">{cancellationImpact.tax_report_count}</span>
              </div>
              <div className="impact-row">
                <span className="impact-label">{t('account.deleteWizard.properties', 'Properties')}</span>
                <span className="impact-value">{cancellationImpact.property_count}</span>
              </div>

              {cancellationImpact.has_active_subscription && (
                <div className="impact-row subscription-info">
                  <span className="impact-label">{t('account.deleteWizard.subscription', 'Active Subscription')}</span>
                  <span className="impact-value">
                    {cancellationImpact.subscription_days_remaining != null
                      ? t('account.deleteWizard.daysRemaining', '{{days}} days remaining', {
                          days: cancellationImpact.subscription_days_remaining,
                        })
                      : t('account.deleteWizard.willBeCancelled', 'Will be cancelled')}
                  </span>
                </div>
              )}

              <div className="impact-row cooling-off-info">
                <span className="impact-label">{t('account.deleteWizard.coolingOff', 'Cooling-off Period')}</span>
                <span className="impact-value">
                  {t('account.deleteWizard.coolingOffDays', '{{days}} days', {
                    days: cancellationImpact.cooling_off_days,
                  })}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Data Export Option */}
      {step === 2 && (
        <div className="wizard-step">
          <h3>{t('account.deleteWizard.step2Title', 'Export Your Data')}</h3>
          <p className="wizard-step-desc">
            {t('account.deleteWizard.step2Desc', 'Optionally export all your data before account deletion.')}
          </p>

          <div className="export-section">
            <label className="export-toggle">
              <input
                type="checkbox"
                checked={wantExport}
                onChange={(e) => setWantExport(e.target.checked)}
              />
              {t('account.deleteWizard.wantExport', 'I want to export my data before deletion')}
            </label>

            {wantExport && (
              <div className="export-form">
                <div className="form-group">
                  <label htmlFor="export-password">
                    {t('account.deleteWizard.exportPassword', 'Encryption Password')}
                  </label>
                  <input
                    id="export-password"
                    type="password"
                    value={exportPassword}
                    onChange={(e) => setExportPassword(e.target.value)}
                    placeholder={t('account.deleteWizard.exportPasswordPlaceholder', 'Enter a password to encrypt your data')}
                    disabled={!!exportTaskId}
                  />
                </div>

                {!exportTaskId && (
                  <button
                    className="btn-primary"
                    onClick={handleExport}
                    disabled={isLoading || !exportPassword.trim()}
                  >
                    {isLoading
                      ? t('common.loading', 'Loading...')
                      : t('account.deleteWizard.startExport', 'Start Export')}
                  </button>
                )}

                {exportTaskId && exportStatus && (
                  <div className="export-status">
                    <p>
                      {t('account.deleteWizard.exportStatus', 'Status')}: {' '}
                      <strong>{exportStatus.status}</strong>
                    </p>
                    {exportStatus.status === 'ready' && exportStatus.download_url && (
                      <a
                        href={exportStatus.download_url}
                        className="btn-primary export-download-link"
                        download
                      >
                        {t('account.deleteWizard.downloadExport', 'Download Export')}
                      </a>
                    )}
                    {exportStatus.status === 'failed' && (
                      <p className="error-message">
                        {t('account.deleteWizard.exportFailed', 'Export failed. Please try again.')}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {error && <div className="error-message">{error}</div>}
        </div>
      )}

      {/* Step 3: Password Verification + Confirmation */}
      {step === 3 && (
        <div className="wizard-step">
          <h3>{t('account.deleteWizard.step3Title', 'Confirm Deletion')}</h3>
          <p className="wizard-step-desc">
            {t('account.deleteWizard.step3Desc', 'Verify your identity and confirm account deletion.')}
          </p>

          <form onSubmit={handleSubmit} className="confirmation-form">
            <div className="form-group">
              <label htmlFor="delete-password">{t('account.deleteWizard.password', 'Password')}</label>
              <input
                id="delete-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={submitting}
              />
            </div>

            <div className="form-group">
              <label htmlFor="confirmation-word">
                {t('account.deleteWizard.typeDelete', 'Type DELETE to confirm')}
              </label>
              <input
                id="confirmation-word"
                type="text"
                value={confirmationWord}
                onChange={(e) => setConfirmationWord(e.target.value)}
                placeholder="DELETE"
                required
                disabled={submitting}
                autoComplete="off"
              />
            </div>

            <div className="form-group">
              <label htmlFor="two-factor-code">
                {t('account.deleteWizard.twoFactorCode', '2FA Code (if enabled)')}
              </label>
              <input
                id="two-factor-code"
                type="text"
                value={twoFactorCode}
                onChange={(e) => setTwoFactorCode(e.target.value)}
                maxLength={6}
                disabled={submitting}
                placeholder={t('account.deleteWizard.twoFactorPlaceholder', 'Optional')}
              />
            </div>

            {submitError && <div className="error-message">{submitError}</div>}

            <button
              type="submit"
              className="btn-danger"
              disabled={submitting || !password || confirmationWord !== 'DELETE'}
            >
              {submitting
                ? t('common.loading', 'Loading...')
                : t('account.deleteWizard.confirmDelete', 'Permanently Delete Account')}
            </button>
          </form>
        </div>
      )}

      {/* Navigation */}
      <div className="wizard-nav">
        <button className="btn-secondary" onClick={handleCancel}>
          {t('common.cancel', 'Cancel')}
        </button>
        <div className="wizard-nav-right">
          {step > 1 && (
            <button className="btn-secondary" onClick={goBack}>
              {t('account.deleteWizard.back', 'Back')}
            </button>
          )}
          {step < 3 && (
            <button
              className="btn-primary"
              onClick={goNext}
              disabled={step === 1 && !cancellationImpact}
            >
              {t('account.deleteWizard.next', 'Next')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default DeleteAccountWizard;
