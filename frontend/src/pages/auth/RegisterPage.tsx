import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import Select from '../../components/common/Select';
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
    businessName: '' as string,
    businessIndustry: '' as string,
    vatStatus: '' as string,
    gewinnermittlungsart: '' as string,
    employerMode: 'none' as 'none' | 'occasional' | 'regular',
    employerRegion: '' as string,
    numChildren: '' as string,
    isSingleParent: false,
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState('');
  const [resending, setResending] = useState(false);
  const [resendMsg, setResendMsg] = useState('');
  const [industries, setIndustries] = useState<IndustryOption[]>([]);
  const [industriesLoading, setIndustriesLoading] = useState(false);

  const getIndustryLabel = (ind: IndustryOption) => {
    const lang = i18n.resolvedLanguage || i18n.language || 'de';
    if (lang.startsWith('zh')) return ind.label_zh;
    if (lang.startsWith('en')) return ind.label_en;
    return ind.label_de;
  };

  // Fetch industries when businessType changes
  useEffect(() => {
    if (formData.businessType) {
      let isActive = true;
      setIndustriesLoading(true);
      userService
        .getIndustries(formData.businessType)
        .then((nextIndustries) => {
          if (isActive) {
            setIndustries(nextIndustries);
          }
        })
        .catch(() => {
          if (isActive) {
            setIndustries([]);
          }
        })
        .finally(() => {
          if (isActive) {
            setIndustriesLoading(false);
          }
        });

      return () => {
        isActive = false;
      };
    } else {
      setIndustries([]);
      setIndustriesLoading(false);
    }
  }, [formData.businessType]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    if (type === 'checkbox') {
      const checked = (e.target as HTMLInputElement).checked;
      setFormData({ ...formData, [name]: checked });
      return;
    }
    if (name === 'businessType') {
      setFormData({ ...formData, businessType: value, businessIndustry: '' });
    } else {
      setFormData({ ...formData, [name]: value });
    }
  };

  const handleSelectChange = useCallback((field: string) => (value: string) => {
    if (field === 'businessType') {
      setFormData(prev => ({ ...prev, businessType: value, businessIndustry: '' }));
    } else {
      setFormData(prev => ({ ...prev, [field]: value }));
    }
  }, []);

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
  const needsAssetTaxProfile = isSelfEmployed;
  const needsBusinessIndustry = isSelfEmployed && Boolean(formData.businessType) && industries.length > 0;
  const businessIndustryPlaceholder = !formData.businessType
    ? t('profile.selectBusinessTypeFirst', 'Please select a business type above first.')
    : industriesLoading
      ? t('profile.loadingIndustryOptions', 'Loading industry subcategories...')
      : industries.length > 0
        ? t('profile.selectIndustry')
        : t('profile.noIndustryOptions', 'No subcategories available for this business type.');
  const businessIndustryHelpText = !formData.businessType
    ? t('profile.businessIndustryStepHelp', 'First select the business type, then choose a more specific industry subcategory.')
    : industriesLoading
      ? t('profile.businessIndustryLoadingHelp', 'The system is loading industry options for this business type.')
      : industries.length > 0
        ? t('profile.businessIndustryHelp')
        : t('profile.businessIndustryUnavailableHelp', 'This business type currently has no available subcategories. You can add this later.');
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
  const vatStatusOptions = [
    { value: 'regelbesteuert', label: t('profile.vatStatus.regelbesteuert', 'Regular VAT') },
    { value: 'kleinunternehmer', label: t('profile.vatStatus.kleinunternehmer', 'Small business exemption') },
    { value: 'pauschaliert', label: t('profile.vatStatus.pauschaliert', 'Flat-rate VAT') },
    { value: 'unknown', label: t('profile.vatStatus.unknown', 'Unknown / not sure yet') },
  ];
  const gewinnermittlungsartOptions = [
    { value: 'ea_rechnung', label: t('profile.gewinnermittlungsart.ea_rechnung', 'Einnahmen-Ausgaben-Rechnung') },
    { value: 'bilanzierung', label: t('profile.gewinnermittlungsart.bilanzierung', 'Bilanzierung') },
    { value: 'pauschal', label: t('profile.gewinnermittlungsart.pauschal', 'Pauschalierung') },
    { value: 'unknown', label: t('profile.gewinnermittlungsart.unknown', 'Unknown / not sure yet') },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError(t('auth.passwordsDoNotMatch', 'Passwords do not match'));
      return;
    }

    if (needsBusinessIndustry && !formData.businessIndustry) {
      setError(t('profile.businessIndustryRequired', 'Please select a specific industry/business subcategory.'));
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
        user_roles: formData.userRoles,
        business_type: isSelfEmployed ? formData.businessType || null : null,
        business_name: isSelfEmployed ? formData.businessName.trim() || null : null,
        business_industry: isSelfEmployed ? formData.businessIndustry || null : null,
        vat_status: needsAssetTaxProfile ? formData.vatStatus || null : null,
        gewinnermittlungsart: needsAssetTaxProfile ? formData.gewinnermittlungsart || null : null,
        employer_mode: isSelfEmployed ? formData.employerMode : 'none',
        employer_region: isSelfEmployed ? formData.employerRegion || null : null,
        num_children: formData.numChildren === '' ? null : Number(formData.numChildren),
        is_single_parent: formData.numChildren === '' ? null : formData.isSingleParent,
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
                {t('profile.gmbh', 'GmbH')} <span style={{ fontSize: '0.75rem', color: '#8b5cf6', fontWeight: 600, marginLeft: '0.5rem' }}>{t('common.comingSoon')}</span>
              </label>
            </div>
          </div>

          {isSelfEmployed && (
            <>
              <div className="form-group">
                <label>{t('auth.businessType')}</label>
                <Select name="businessType" value={formData.businessType}
                  onChange={handleSelectChange('businessType')} disabled={loading}
                  placeholder={t('auth.selectBusinessType')}
                  options={businessTypes} />
                {formData.businessType && (
                  <small className="business-type-hint">
                    {t(`auth.businessTypeHints.${formData.businessType}`)}
                  </small>
                )}
              </div>

              <div className="form-group business-subtype-group">
                <label>
                  {t('profile.businessIndustry')}
                  {needsBusinessIndustry && <span className="field-required-marker"> *</span>}
                </label>
                <Select name="businessIndustry" value={formData.businessIndustry}
                  onChange={handleSelectChange('businessIndustry')}
                  disabled={loading || !formData.businessType || industriesLoading || industries.length === 0}
                  placeholder={businessIndustryPlaceholder}
                  options={industries.map(ind => ({ value: ind.value, label: getIndustryLabel(ind) }))} />
                <small>{businessIndustryHelpText}</small>
              </div>
            </>
          )}

          <section className="auth-optional-profile-section">
            <div className="auth-optional-profile-header">
              <h2>{t('auth.optionalProfileTitle', 'Complete your profile')}</h2>
              <span>{t('auth.optionalProfileBadge', 'Optional')}</span>
            </div>
            <p className="auth-optional-profile-copy">
              {t(
                'auth.optionalProfileCopy',
                'These fields can be left blank for now; filling them in first will help Taxja provide more accurate recognition, deductions, and tips later.'
              )}
            </p>

            {isSelfEmployed && (
              <div className="form-group">
                <label>{t('profile.businessName', 'Business name')}</label>
                <input
                  type="text"
                  name="businessName"
                  value={formData.businessName}
                  onChange={handleChange}
                  disabled={loading}
                  placeholder={t('profile.businessNamePlaceholder', 'Optional business name')}
                />
              </div>
            )}

            {needsAssetTaxProfile && (
              <>
                <div className="form-group">
                  <label>{t('profile.vatStatusLabel', 'VAT status')}</label>
                  <Select name="vatStatus" value={formData.vatStatus}
                    onChange={handleSelectChange('vatStatus')} disabled={loading}
                    placeholder={t('profile.selectVatStatus', 'Select VAT status')}
                    options={vatStatusOptions} />
                </div>

                <div className="form-group">
                  <label>{t('profile.gewinnermittlungsartLabel', 'Profit determination method')}</label>
                  <Select name="gewinnermittlungsart" value={formData.gewinnermittlungsart}
                    onChange={handleSelectChange('gewinnermittlungsart')} disabled={loading}
                    placeholder={t('profile.selectGewinnermittlungsart', 'Select profit determination method')}
                    options={gewinnermittlungsartOptions} />
                </div>
              </>
            )}

            <div className="form-group">
              <label>{t('profile.numChildren', 'Number of children')}</label>
              <input
                type="number"
                name="numChildren"
                value={formData.numChildren}
                onChange={handleChange}
                disabled={loading}
                min="0"
                placeholder="0"
              />
            </div>

            <div className="form-group checkbox-inline-group">
              <label className="checkbox-inline-label">
                <input
                  type="checkbox"
                  name="isSingleParent"
                  checked={formData.isSingleParent}
                  onChange={handleChange}
                  disabled={loading}
                />
                <span className="checkbox-inline-text">
                  {t('profile.singleParent', 'I am a single parent')}
                </span>
              </label>
            </div>
          </section>

          {isSelfEmployed && (
            <>
              <div className="form-group">
                <label>{t('profile.employerMode', 'Employee-related payroll documents')}</label>
                <Select name="employerMode" value={formData.employerMode}
                  onChange={handleSelectChange('employerMode')} disabled={loading}
                  options={[
                    { value: 'none', label: t('profile.employerModes.none', 'No') },
                    { value: 'occasional', label: t('profile.employerModes.occasional', 'Occasionally') },
                    { value: 'regular', label: t('profile.employerModes.regular', 'Regularly') },
                  ]} />
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
