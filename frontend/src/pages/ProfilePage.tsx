import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../stores/authStore';
import { useSubscriptionStore } from '../stores/subscriptionStore';
import { userService, type UserProfile } from '../services/userService';
import { aiToast } from '../stores/aiToastStore';
import DataExport from '../components/reports/DataExport';
import ClassificationRules from '../components/transactions/ClassificationRules';
import AccountManagementSection from '../components/account/AccountManagementSection';
import './ProfilePage.css';

interface IndustryOption {
  value: string;
  label_de: string;
  label_en: string;
  label_zh: string;
}

interface ProfileFormData {
  name: string;
  address: string;
  tax_number: string;
  vat_number: string;
  vat_status: string;
  gewinnermittlungsart: string;
  user_type: string;
  user_roles: string[];
  business_type: string;
  business_name: string;
  business_industry: string;
  employer_mode: 'none' | 'occasional' | 'regular';
  employer_region: string;
  commuting_distance_km: number;
  public_transport_available: boolean;
  telearbeit_days: number;
  employer_telearbeit_pauschale: number;
  num_children: number;
  is_single_parent: boolean;
}

const ProfilePage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { user, updateUser } = useAuthStore();
  const { fetchSubscription } = useSubscriptionStore();
  
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [industries, setIndustries] = useState<IndustryOption[]>([]);
  const [taxProfileCompleteness, setTaxProfileCompleteness] = useState<UserProfile['tax_profile_completeness'] | null>(null);
  
  const [formData, setFormData] = useState<ProfileFormData>({
    name: user?.name || '',
    address: '',
    tax_number: '',
    vat_number: '',
    vat_status: '',
    gewinnermittlungsart: '',
    user_type: user?.user_type || 'employee',
    user_roles: user?.user_type === 'mixed' ? ['employee', 'landlord', 'self_employed'] : [user?.user_type || 'employee'],
    business_type: '',
    business_name: '',
    business_industry: '',
    employer_mode: (user?.employer_mode as 'none' | 'occasional' | 'regular') || 'none',
    employer_region: user?.employer_region || '',
    commuting_distance_km: 0,
    public_transport_available: true,
    telearbeit_days: 0,
    employer_telearbeit_pauschale: 0,
    num_children: 0,
    is_single_parent: false,
  });

  const buildFormDataFromProfile = (profile: UserProfile): ProfileFormData => {
    const userType = profile.user_type || 'employee';
    const businessType = profile.business_type || '';

    return {
      name: profile.name || '',
      address: profile.address || '',
      tax_number: profile.tax_number || '',
      vat_number: profile.vat_number || '',
      vat_status: profile.vat_status || '',
      gewinnermittlungsart: profile.gewinnermittlungsart || '',
      user_type: userType,
      user_roles: deriveRoles(userType, (profile as any).user_roles),
      business_type: businessType,
      business_name: profile.business_name || '',
      business_industry: profile.business_industry || '',
      employer_mode: profile.employer_mode || 'none',
      employer_region: profile.employer_region || '',
      commuting_distance_km: profile.commuting_distance_km || 0,
      public_transport_available: profile.public_transport_available ?? true,
      telearbeit_days: (profile as any).telearbeit_days || 0,
      employer_telearbeit_pauschale: (profile as any).employer_telearbeit_pauschale || 0,
      num_children: profile.num_children || 0,
      is_single_parent: profile.is_single_parent || false,
    };
  };

  const applyProfile = async (profile: UserProfile) => {
    const nextFormData = buildFormDataFromProfile(profile);
    setFormData(nextFormData);
    setTaxProfileCompleteness(profile.tax_profile_completeness ?? null);
    updateUser(profile);

    if (nextFormData.business_type) {
      try {
        const nextIndustries = await userService.getIndustries(nextFormData.business_type);
        setIndustries(nextIndustries);
      } catch (err) {
        console.error('Failed to fetch industries for', nextFormData.business_type, err);
        setIndustries([]);
      }
    } else {
      setIndustries([]);
    }
  };

  // Helper: derive user_type from selected roles
  const deriveUserType = (roles: string[]): string => {
    if (roles.length === 0) return 'employee';
    if (roles.length === 1) return roles[0];
    return 'mixed';
  };

  // Helper: derive roles from user_type
  const deriveRoles = (userType: string, storedRoles?: string[]): string[] => {
    if (storedRoles && storedRoles.length > 0) return storedRoles;
    if (userType === 'mixed') return ['employee', 'landlord', 'self_employed'];
    return [userType || 'employee'];
  };

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const profile = await userService.getProfile();
        await applyProfile(profile);
      } catch (err) {
        console.error('Failed to fetch profile:', err);
      }
    };

    fetchProfile();
  }, []);

  // Also fetch industries when user changes business_type in the form
  useEffect(() => {
    // Skip the initial render (profile fetch handles that)
    if (formData.business_type) {
      userService.getIndustries(formData.business_type).then(setIndustries).catch((err) => {
        console.error('Failed to fetch industries:', err);
        setIndustries([]);
      });
    } else {
      setIndustries([]);
    }
  }, [formData.business_type]);

  // Get localized industry label
  const getIndustryLabel = (ind: IndustryOption) => {
    const lang = i18n.resolvedLanguage || i18n.language || 'de';
    if (lang.startsWith('zh')) return ind.label_zh;
    if (lang.startsWith('en')) return ind.label_en;
    return ind.label_de;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    
    if (type === 'checkbox') {
      const checked = (e.target as HTMLInputElement).checked;
      setFormData({ ...formData, [name]: checked });
    } else if (name === 'employer_telearbeit_pauschale') {
      setFormData({ ...formData, [name]: parseFloat(value) || 0 });
    } else if (type === 'number') {
      setFormData({ ...formData, [name]: parseInt(value) || 0 });
    } else if (name === 'business_type') {
      // Clear industry when business type changes
      setFormData({ ...formData, business_type: value, business_industry: '' });
    } else {
      setFormData({ ...formData, [name]: value });
    }
  };

  const handleRoleToggle = (role: string) => {
    // GmbH is mutually exclusive with all other roles
    if (role === 'gmbh') {
      if (formData.user_roles.includes('gmbh')) {
        setFormData({ ...formData, user_roles: ['employee'], user_type: 'employee' });
      } else {
        setFormData({ ...formData, user_roles: ['gmbh'], user_type: 'gmbh' });
      }
      return;
    }
    // If currently GmbH, switching to a personal role replaces it
    if (formData.user_roles.includes('gmbh')) {
      setFormData({ ...formData, user_roles: [role], user_type: role });
      return;
    }
    // Normal multi-select for personal roles
    const newRoles = formData.user_roles.includes(role)
      ? formData.user_roles.filter(r => r !== role)
      : [...formData.user_roles, role];
    if (newRoles.length === 0) return;
    setFormData({
      ...formData,
      user_roles: newRoles,
      user_type: deriveUserType(newRoles),
    });
  };

  const isGmbHSelected = formData.user_roles.includes('gmbh');
  const isSelfEmployed = formData.user_roles.includes('self_employed');
  const personalRoles = [
    { value: 'employee', label: t('profile.employee') },
    { value: 'landlord', label: t('profile.landlord') },
    { value: 'self_employed', label: t('profile.selfEmployed') },
  ];

  // Industries that have deductibility examples
  const industriesWithExamples = [
    'gastronomie', 'hotel', 'kosmetik', 'handel', 'ecommerce', 'handwerk',
    'it_dienstleistung', 'transport', 'reinigung', 'arzt', 'rechtsanwalt',
    'steuerberater', 'trainer', 'content_creator', 'weinbau', 'architekt', 'kuenstler',
  ];
  const businessTypes = [
    { value: 'freiberufler', label: t('profile.businessTypes.freiberufler') },
    { value: 'gewerbetreibende', label: t('profile.businessTypes.gewerbetreibende') },
    { value: 'neue_selbstaendige', label: t('profile.businessTypes.neueSelbstaendige') },
    { value: 'land_forstwirtschaft', label: t('profile.businessTypes.landForstwirtschaft') },
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
  const taxProfileMissingLabels: Record<'vat_status' | 'gewinnermittlungsart', string> = {
    vat_status: t('profile.vatStatusLabel', 'VAT status'),
    gewinnermittlungsart: t('profile.gewinnermittlungsartLabel', 'Profit determination method'),
  };
  const needsAssetTaxProfile = formData.user_roles.includes('self_employed') || formData.user_type === 'gmbh';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      await userService.updateProfile(formData);
      const confirmedProfile = await userService.getProfile();
      await applyProfile(confirmedProfile);
      setSuccess(t('profile.updateSuccess'));
      setIsEditing(false);
      aiToast(t('profile.updateSuccess'), 'success');
    } catch (err: any) {
      const msg = err.response?.data?.detail || t('common.error');
      setError(msg);
      aiToast(msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setError('');
    setSuccess('');
  };

  const handleSetup2FA = () => {
    navigate('/2fa-setup');
  };

  useEffect(() => {
    fetchSubscription();
  }, [fetchSubscription]);

  return (
    <div className="profile-page">
      <div className="profile-header">
        <h1>{t('nav.profile')}</h1>
        {!isEditing && (
          <button onClick={() => setIsEditing(true)} className="btn-primary">
            {t('common.edit')}
          </button>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}
      {success && <div className="success-message">{success}</div>}

      <form onSubmit={handleSubmit} className="profile-form">
        <section className="profile-section">
          <h2>{t('profile.basicInfo')}</h2>
          
          <div className="form-group">
            <label>{t('profile.name')}</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              disabled={!isEditing || loading}
              required
            />
          </div>

          <div className="form-group">
            <label>{t('auth.email')}</label>
            <input
              type="email"
              value={user?.email || ''}
              disabled
            />
            <small>{t('profile.emailCannotChange')}</small>
          </div>

          <div className="form-group">
            <label>{t('profile.userType')}</label>
            <div className="role-checkboxes">
              {personalRoles.map(role => (
                <label key={role.value} className="role-checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.user_roles.includes(role.value)}
                    onChange={() => handleRoleToggle(role.value)}
                    disabled={!isEditing || loading || isGmbHSelected}
                  />
                  <span style={isGmbHSelected ? { opacity: 0.5 } : undefined}>{role.label}</span>
                </label>
              ))}
            </div>
            <div style={{ borderTop: '1px solid var(--border-color, #e5e7eb)', margin: '0.5rem 0', paddingTop: '0.5rem', opacity: 0.5 }}>
              <label className="role-checkbox-label" style={{ cursor: 'not-allowed' }}>
                <input
                  type="checkbox"
                  checked={false}
                  disabled
                />
                {t('profile.gmbh')} <span style={{ fontSize: '0.75rem', color: '#8b5cf6', fontWeight: 600, marginLeft: '0.5rem' }}>{t('common.comingSoon')}</span>
              </label>
              <small style={{ display: 'block', color: 'var(--text-secondary, #6b7280)', marginTop: '0.25rem', fontSize: '0.8rem' }}>
                {t('auth.gmbhComingSoon', 'GmbH（有限责任公司）申报功能即将上线')}
              </small>
            </div>
          </div>

          {isSelfEmployed && (
            <>
              <div className="form-group">
                <label>{t('profile.businessType')}</label>
                <select
                  name="business_type"
                  value={formData.business_type}
                  onChange={handleChange}
                  disabled={!isEditing || loading}
                >
                  <option value="">{t('profile.selectBusinessType')}</option>
                  {businessTypes.map(bt => (
                    <option key={bt.value} value={bt.value}>{bt.label}</option>
                  ))}
                </select>
                {formData.business_type && (
                  <small style={{ display: 'block', color: 'var(--text-secondary, #6b7280)', marginTop: '0.25rem' }}>
                    {t(`profile.businessTypeHints.${formData.business_type}`)}
                  </small>
                )}
              </div>

              {industries.length > 0 && (
                <div className="form-group">
                  <label>{t('profile.businessIndustry')}</label>
                  <select
                    name="business_industry"
                    value={formData.business_industry}
                    onChange={handleChange}
                    disabled={!isEditing || loading}
                  >
                    <option value="">{t('profile.selectIndustry')}</option>
                    {industries.map(ind => (
                      <option key={ind.value} value={ind.value}>{getIndustryLabel(ind)}</option>
                    ))}
                  </select>
                  <small>{t('profile.businessIndustryHelp')}</small>

                  {/* Industry-specific deductibility guidance */}
                  {formData.business_industry && industriesWithExamples.includes(formData.business_industry) && (
                    <div style={{
                      marginTop: '0.75rem',
                      padding: '0.75rem 1rem',
                      borderRadius: '8px',
                      background: 'var(--bg-secondary, #f8f9fa)',
                      border: '1px solid var(--border-color, #e5e7eb)',
                      fontSize: '0.85rem',
                      lineHeight: '1.5',
                    }}>
                      <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-primary, #1f2937)' }}>
                        {t('profile.industryDeductibilityTitle')}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                        <div>
                          <span style={{ color: '#16a34a', fontWeight: 500 }}>
                            {t('profile.deductibleLabel')}:
                          </span>{' '}
                          <span style={{ color: 'var(--text-secondary, #4b5563)' }}>
                            {t(`profile.industryExamples.${formData.business_industry}.deductible`)}
                          </span>
                        </div>
                        <div>
                          <span style={{ color: '#dc2626', fontWeight: 500 }}>
                            {t('profile.notDeductibleLabel')}:
                          </span>{' '}
                          <span style={{ color: 'var(--text-secondary, #4b5563)' }}>
                            {t(`profile.industryExamples.${formData.business_industry}.notDeductible`)}
                          </span>
                        </div>
                        {(() => {
                          const needsAI = t(`profile.industryExamples.${formData.business_industry}.needsAI`, '');
                          return needsAI && !needsAI.startsWith('profile.industryExamples.') ? (
                          <div>
                            <span style={{ color: '#d97706', fontWeight: 500 }}>
                              {t('profile.needsAILabel')}:
                            </span>{' '}
                            <span style={{ color: 'var(--text-secondary, #4b5563)' }}>
                              {needsAI}
                            </span>
                          </div>
                          ) : null;
                        })()}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="form-group">
                <label>{t('profile.businessName')}</label>
                <input
                  type="text"
                  name="business_name"
                  value={formData.business_name}
                  onChange={handleChange}
                  disabled={!isEditing || loading}
                  placeholder={t('profile.businessNamePlaceholder')}
                />
                <small>{t('profile.businessNameHelp')}</small>
              </div>
            </>
          )}

          {isSelfEmployed && (
            <>
              <div className="form-group">
                <label>{t('profile.employerMode', 'Employee-related payroll documents')}</label>
                <select
                  name="employer_mode"
                  value={formData.employer_mode}
                  onChange={handleChange}
                  disabled={!isEditing || loading}
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

              {formData.employer_mode !== 'none' && (
                <div className="form-group">
                  <label>{t('profile.employerRegion', 'State / region (optional)')}</label>
                  <input
                    type="text"
                    name="employer_region"
                    value={formData.employer_region}
                    onChange={handleChange}
                    disabled={!isEditing || loading}
                    placeholder={t('profile.employerRegionPlaceholder', 'e.g. Wien')}
                  />
                </div>
              )}
            </>
          )}

          <div className="form-group">
            <label>{t('profile.address')}</label>
            <input
              type="text"
              name="address"
              value={formData.address}
              onChange={handleChange}
              disabled={!isEditing || loading}
            />
          </div>
        </section>

        <section className="profile-section">
          <h2>{t('profile.taxInfo')}</h2>

          {needsAssetTaxProfile && taxProfileCompleteness && !taxProfileCompleteness.is_complete_for_asset_automation && (
            <div className="warning-message">
              {t(
                'profile.assetAutomationIncomplete',
                'Asset automation is currently limited because your tax profile is incomplete.'
              )}{' '}
              {taxProfileCompleteness.missing_fields.map((field) => taxProfileMissingLabels[field]).join(', ')}
            </div>
          )}
          
          <div className="form-group">
            <label>{t('profile.taxNumber')}</label>
            <input
              type="text"
              name="tax_number"
              value={formData.tax_number}
              onChange={handleChange}
              disabled={!isEditing || loading}
            />
          </div>

          {(formData.user_roles.includes('self_employed') || formData.user_roles.includes('small_business') || formData.user_roles.includes('gmbh')) && (
            <div className="form-group">
              <label>{t('profile.vatNumber')}</label>
              <input
                type="text"
                name="vat_number"
                value={formData.vat_number}
                onChange={handleChange}
                disabled={!isEditing || loading}
              />
            </div>
          )}

          {needsAssetTaxProfile && (
            <>
              <div className="form-group">
                <label>{t('profile.vatStatusLabel', 'VAT status')}</label>
                <select
                  name="vat_status"
                  value={formData.vat_status}
                  onChange={handleChange}
                  disabled={!isEditing || loading}
                >
                  <option value="">{t('profile.selectVatStatus', 'Select VAT status')}</option>
                  {vatStatusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <small>
                  {t(
                    'profile.vatStatusHelp',
                    'This is the persisted VAT source of truth used for OCR asset and tax automation.'
                  )}
                </small>
              </div>

              <div className="form-group">
                <label>{t('profile.gewinnermittlungsartLabel', 'Profit determination method')}</label>
                <select
                  name="gewinnermittlungsart"
                  value={formData.gewinnermittlungsart}
                  onChange={handleChange}
                  disabled={!isEditing || loading}
                >
                  <option value="">{t('profile.selectGewinnermittlungsart', 'Select profit determination method')}</option>
                  {gewinnermittlungsartOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <small>
                  {t(
                    'profile.gewinnermittlungsartHelp',
                    'Asset automation will only auto-create when this field is saved on your profile.'
                  )}
                </small>
              </div>
            </>
          )}
        </section>

        <section className="profile-section">
          <h2>{t('profile.commutingInfo')}</h2>
          
          <div className="form-group">
            <label>{t('profile.commutingDistance')}</label>
            <input
              type="number"
              name="commuting_distance_km"
              value={formData.commuting_distance_km}
              onChange={handleChange}
              disabled={!isEditing || loading}
              min="0"
            />
            <small>{t('profile.commutingDistanceHelp')}</small>
          </div>

          <div className="form-group checkbox-group">
            <label>
              <input
                type="checkbox"
                name="public_transport_available"
                checked={formData.public_transport_available}
                onChange={handleChange}
                disabled={!isEditing || loading}
              />
              {t('profile.publicTransportAvailable')}
            </label>
          </div>
        </section>

        {formData.user_roles.includes('employee') && (
          <section className="profile-section">
            <h2>{t('profile.homeOfficeInfo')}</h2>

            <div className="form-group">
              <label>{t('profile.telearbeitDays')}</label>
              <input
                type="number"
                name="telearbeit_days"
                value={formData.telearbeit_days}
                onChange={handleChange}
                disabled={!isEditing || loading}
                min="0"
                max="366"
              />
              <small>{t('profile.telearbeitDaysHelp')}</small>
            </div>

            <div className="form-group">
              <label>{t('profile.employerTelearbeitPauschale')}</label>
              <input
                type="number"
                name="employer_telearbeit_pauschale"
                value={formData.employer_telearbeit_pauschale}
                onChange={handleChange}
                disabled={!isEditing || loading}
                min="0"
                step="0.01"
              />
              <small>{t('profile.employerTelearbeitPauschaleHelp')}</small>
            </div>

            {formData.telearbeit_days > 0 && (
              <div style={{
                marginTop: '0.5rem',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                background: 'var(--bg-secondary, #f0fdf4)',
                border: '1px solid var(--border-color, #bbf7d0)',
                fontSize: '0.85rem',
              }}>
                <strong>{t('profile.telearbeitEstimate')}:</strong>{' '}
                {(() => {
                  const days = Math.min(formData.telearbeit_days, 100);
                  const maxAllowed = days * 3;
                  const deductible = Math.max(0, maxAllowed - formData.employer_telearbeit_pauschale);
                  return `${days} ${t('profile.telearbeitDaysLabel')} × €3.00 = €${maxAllowed.toFixed(2)} − €${formData.employer_telearbeit_pauschale.toFixed(2)} = €${deductible.toFixed(2)}`;
                })()}
              </div>
            )}
          </section>
        )}

        <section className="profile-section">
          <h2>{t('profile.familyInfo')}</h2>
          
          <div className="form-group">
            <label>{t('profile.numChildren')}</label>
            <input
              type="number"
              name="num_children"
              value={formData.num_children}
              onChange={handleChange}
              disabled={!isEditing || loading}
              min="0"
            />
          </div>

          <div className="form-group checkbox-group">
            <label>
              <input
                type="checkbox"
                name="is_single_parent"
                checked={formData.is_single_parent}
                onChange={handleChange}
                disabled={!isEditing || loading}
              />
              {t('profile.singleParent')}
            </label>
          </div>
        </section>

        <section className="profile-section">
          <h2>{t('profile.security')}</h2>
          
          <div className="security-info">
            <p>
              <strong>{t('auth.twoFactorAuth')}:</strong>{' '}
              {user?.two_factor_enabled ? (
                <span className="status-enabled">{t('common.enabled')}</span>
              ) : (
                <span className="status-disabled">{t('common.disabled')}</span>
              )}
            </p>
            {!user?.two_factor_enabled && (
              <button
                type="button"
                onClick={handleSetup2FA}
                className="btn-secondary"
              >
                {t('auth.enable2FA')}
              </button>
            )}
          </div>
        </section>

        {isEditing && (
          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? t('common.loading') : t('common.save')}
            </button>
            <button
              type="button"
              onClick={handleCancel}
              className="btn-secondary"
              disabled={loading}
            >
              {t('common.cancel')}
            </button>
          </div>
        )}
      </form>

      <section className="profile-section privacy-section">
        <h2>{t('profile.privacyAndData')}</h2>
        <DataExport />
      </section>

      <section className="profile-section">
        <h2>{t('classificationRules.pageTitle', 'Classification Rules')}</h2>
        <p style={{ margin: '0 0 16px', color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>
          {t('classificationRules.pageSubtitle', 'Rules are auto-created when you correct a transaction category. They ensure future similar transactions are classified the same way.')}
        </p>
        <ClassificationRules />
      </section>

      {/* Account Management (Cancel Subscription + Delete Account) */}
      <AccountManagementSection />
    </div>
  );
};

export default ProfilePage;
