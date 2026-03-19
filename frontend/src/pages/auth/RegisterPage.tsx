import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import { authService } from '../../services/authService';
import { userService, IndustryOption } from '../../services/userService';
import LanguageSwitcher from '../../components/common/LanguageSwitcher';
import './AuthPages.css';

const RegisterPage = () => {
  const { t, i18n } = useTranslation();

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    name: '',
    userType: 'employee',
    userRoles: ['employee'] as string[],
    businessType: '' as string,
    businessIndustry: '' as string,
    employerMode: 'none' as 'none' | 'occasional' | 'regular',
    employerRegion: '' as string,
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState('');
  const [resending, setResending] = useState(false);
  const [resendMsg, setResendMsg] = useState('');
  const [industries, setIndustries] = useState<IndustryOption[]>([]);

  const getIndustryLabel = (ind: IndustryOption) => {
    const lang = i18n.resolvedLanguage || i18n.language || 'de';
    if (lang.startsWith('zh')) return ind.label_zh;
    if (lang.startsWith('en')) return ind.label_en;
    return ind.label_de;
  };

  // Fetch industries when businessType changes
  useEffect(() => {
    if (formData.businessType) {
      userService.getIndustries(formData.businessType).then(setIndustries).catch(() => setIndustries([]));
    } else {
      setIndustries([]);
    }
  }, [formData.businessType]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    if (name === 'businessType') {
      setFormData({ ...formData, businessType: value, businessIndustry: '' });
    } else {
      setFormData({ ...formData, [name]: value });
    }
  };

  const handleRoleToggle = (role: string) => {
    if (role === 'gmbh') {
      if (formData.userRoles.includes('gmbh')) {
        setFormData({ ...formData, userRoles: ['employee'], userType: 'employee' });
      } else {
        setFormData({ ...formData, userRoles: ['gmbh'], userType: 'gmbh' });
      }
      return;
    }
    if (formData.userRoles.includes('gmbh')) {
      setFormData({ ...formData, userRoles: [role], userType: role });
      return;
    }
    const newRoles = formData.userRoles.includes(role)
      ? formData.userRoles.filter(r => r !== role)
      : [...formData.userRoles, role];
    if (newRoles.length === 0) return;
    setFormData({
      ...formData,
      userRoles: newRoles,
      userType: newRoles.length === 1 ? newRoles[0] : 'mixed',
    });
  };

  const isGmbHSelected = formData.userRoles.includes('gmbh');
  const isSelfEmployed = formData.userRoles.includes('self_employed');
  const personalRoles = [
    { value: 'employee', label: t('auth.userTypes.employee') },
    { value: 'landlord', label: t('auth.userTypes.landlord') },
    { value: 'self_employed', label: t('auth.userTypes.selfEmployed') },
  ];
  const businessTypes = [
    { value: 'freiberufler', label: t('auth.businessTypes.freiberufler') },
    { value: 'gewerbetreibende', label: t('auth.businessTypes.gewerbetreibende') },
    { value: 'neue_selbstaendige', label: t('auth.businessTypes.neueSelbstaendige') },
    { value: 'land_forstwirtschaft', label: t('auth.businessTypes.landForstwirtschaft') },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError(t('auth.passwordsDoNotMatch', 'Passwords do not match'));
      return;
    }

    if (!acceptedTerms) {
      setError(t('auth.mustAcceptTerms', 'You must accept the Terms of Service and Privacy Policy to register.'));
      return;
    }

    setLoading(true);
    try {
      const lang = i18n.resolvedLanguage || i18n.language || 'de';
      await authService.register({
        email: formData.email,
        password: formData.password,
        name: formData.name,
        user_type: formData.userType,
        business_type: isSelfEmployed ? formData.businessType || null : null,
        business_industry: isSelfEmployed ? formData.businessIndustry || null : null,
        employer_mode: isSelfEmployed ? formData.employerMode : 'none',
        employer_region: isSelfEmployed ? formData.employerRegion || null : null,
        language: lang,
      });
      setRegisteredEmail(formData.email);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.error'));
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResending(true);
    setResendMsg('');
    try {
      await authService.resendVerification(registeredEmail);
      setResendMsg(t('auth.verificationResent', 'Verification email resent.'));
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (detail === 'please_wait_before_resending') {
        setResendMsg(t('auth.resendWait', 'Please wait 60 seconds before resending.'));
      } else {
        setResendMsg(t('common.error'));
      }
    } finally {
      setResending(false);
    }
  };

  // After successful registration: show "check your email" screen
  if (registeredEmail) {
    return (
      <div className="auth-page">
        <div className="language-switcher-top-right">
          <LanguageSwitcher />
        </div>
        <div className="auth-container auth-verify-email">
          <div className="auth-verify-icon">📧</div>
          <h1>{t('auth.checkYourEmail', 'Check your email')}</h1>
          <p className="auth-verify-hint">
            {t('auth.verificationSent', 'We sent a verification link to')}
          </p>
          <p className="auth-verify-address">{registeredEmail}</p>
          <p className="auth-verify-hint">
            {t('auth.verificationInstructions', 'Click the link in the email to activate your account.')}
          </p>
          <div className="auth-verify-actions">
            <button
              className="btn-secondary"
              onClick={handleResend}
              disabled={resending}
            >
              {resending ? t('common.loading') : t('auth.resendEmail', 'Resend email')}
            </button>
            <Link to="/login" className="btn-primary auth-verify-login-btn">
              {t('auth.backToLogin', 'Back to login')}
            </Link>
          </div>
          {resendMsg && (
            <p className="auth-verify-msg">{resendMsg}</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="language-switcher-top-right">
        <LanguageSwitcher />
      </div>
      <div className="auth-container">
        <h1>{t('auth.register')}</h1>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label>{t('auth.email')}</label>
            <input type="email" name="email" value={formData.email} onChange={handleChange} required disabled={loading} />
          </div>
          <div className="form-group">
            <label>{t('auth.name')}</label>
            <input type="text" name="name" value={formData.name} onChange={handleChange} required disabled={loading} />
          </div>
          <div className="form-group">
            <label>{t('auth.password')}</label>
            <input type="password" name="password" value={formData.password} onChange={handleChange} required disabled={loading} />
          </div>
          <div className="form-group">
            <label>{t('auth.confirmPassword')}</label>
            <input type="password" name="confirmPassword" value={formData.confirmPassword} onChange={handleChange} required disabled={loading} />
          </div>

          <div className="form-group">
            <label>{t('auth.userType')}</label>
            <div className="role-checkboxes">
              {personalRoles.map(role => (
                <label key={role.value} className="role-checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.userRoles.includes(role.value)}
                    onChange={() => handleRoleToggle(role.value)}
                    disabled={loading || isGmbHSelected}
                  />
                  <span style={isGmbHSelected ? { opacity: 0.5 } : undefined}>{role.label}</span>
                </label>
              ))}
            </div>
            <div style={{ borderTop: '1px solid var(--border-color, #e5e7eb)', margin: '0.5rem 0', paddingTop: '0.5rem', opacity: 0.5 }}>
              <label className="role-checkbox-label" style={{ cursor: 'not-allowed' }}>
                <input type="checkbox" checked={false} disabled />
                {t('profile.gmbh', 'GmbH（有限责任公司）')} <span style={{ fontSize: '0.75rem', color: '#8b5cf6', fontWeight: 600, marginLeft: '0.5rem' }}>{t('common.comingSoon')}</span>
              </label>
            </div>
          </div>

          {isSelfEmployed && (
            <div className="form-group">
              <label>{t('auth.businessType')}</label>
              <select
                name="businessType"
                value={formData.businessType}
                onChange={handleChange}
                disabled={loading}
              >
                <option value="">{t('auth.selectBusinessType')}</option>
                {businessTypes.map(bt => (
                  <option key={bt.value} value={bt.value}>{bt.label}</option>
                ))}
              </select>
              {formData.businessType && (
                <small className="business-type-hint">
                  {t(`auth.businessTypeHints.${formData.businessType}`)}
                </small>
              )}
            </div>
          )}

          {isSelfEmployed && industries.length > 0 && (
            <div className="form-group">
              <label>{t('profile.businessIndustry')}</label>
              <select
                name="businessIndustry"
                value={formData.businessIndustry}
                onChange={handleChange}
                disabled={loading}
              >
                <option value="">{t('profile.selectIndustry')}</option>
                {industries.map(ind => (
                  <option key={ind.value} value={ind.value}>{getIndustryLabel(ind)}</option>
                ))}
              </select>
              <small>{t('profile.businessIndustryHelp')}</small>
            </div>
          )}

          {isSelfEmployed && (
            <>
              <div className="form-group">
                <label>{t('profile.employerMode', 'Employee-related payroll documents')}</label>
                <select
                  name="employerMode"
                  value={formData.employerMode}
                  onChange={handleChange}
                  disabled={loading}
                >
                  <option value="none">{t('profile.employerModes.none', 'No')}</option>
                  <option value="occasional">{t('profile.employerModes.occasional', 'Occasionally')}</option>
                  <option value="regular">{t('profile.employerModes.regular', 'Regularly')}</option>
                </select>
                <small>
                  {t(
                    'profile.employerModeHelp',
                    'This only controls reminders and payroll document detection. It does not create monthly payroll obligations by itself.'
                  )}
                </small>
              </div>

              {formData.employerMode !== 'none' && (
                <div className="form-group">
                  <label>{t('profile.employerRegion', 'State / region (optional)')}</label>
                  <input
                    type="text"
                    name="employerRegion"
                    value={formData.employerRegion}
                    onChange={handleChange}
                    disabled={loading}
                    placeholder={t('profile.employerRegionPlaceholder', 'e.g. Wien')}
                  />
                </div>
              )}
            </>
          )}

          <label className="legal-consent-label">
            <input
              type="checkbox"
              checked={acceptedTerms}
              onChange={(e) => setAcceptedTerms(e.target.checked)}
              disabled={loading}
            />
            <span className="legal-consent-text">
              <Trans
                i18nKey="auth.agreeToTerms"
                components={{
                  terms: <Link to="/legal/terms" target="_blank" />,
                  privacy: <Link to="/legal/privacy" target="_blank" />,
                }}
              />
            </span>
          </label>

          <p className="legal-consent-disclaimer">
            {t('auth.taxDisclaimer', 'This service provides automated tax calculation tools and is not a substitute for professional tax advice.')}
          </p>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? t('common.loading') : t('auth.register')}
          </button>
        </form>

        <div className="auth-links">
          <Link to="/login">{t('auth.login')}</Link>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
