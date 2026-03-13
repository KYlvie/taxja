import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../stores/authStore';
import { userService } from '../services/userService';
import DataExport from '../components/reports/DataExport';
import './ProfilePage.css';

interface ProfileFormData {
  name: string;
  address: string;
  tax_number: string;
  vat_number: string;
  user_type: string;
  user_roles: string[];
  commuting_distance_km: number;
  public_transport_available: boolean;
  num_children: number;
  is_single_parent: boolean;
}

const ProfilePage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, updateUser } = useAuthStore();
  
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const [formData, setFormData] = useState<ProfileFormData>({
    name: user?.name || '',
    address: '',
    tax_number: '',
    vat_number: '',
    user_type: user?.user_type || 'employee',
    user_roles: user?.user_type === 'mixed' ? ['employee', 'landlord', 'self_employed'] : [user?.user_type || 'employee'],
    commuting_distance_km: 0,
    public_transport_available: true,
    num_children: 0,
    is_single_parent: false,
  });

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
        setFormData({
          name: profile.name || '',
          address: profile.address || '',
          tax_number: profile.tax_number || '',
          vat_number: profile.vat_number || '',
          user_type: profile.user_type || 'employee',
          user_roles: deriveRoles(profile.user_type || 'employee', (profile as any).user_roles),
          commuting_distance_km: profile.commuting_distance_km || 0,
          public_transport_available: profile.public_transport_available ?? true,
          num_children: profile.num_children || 0,
          is_single_parent: profile.is_single_parent || false,
        });
      } catch (err) {
        console.error('Failed to fetch profile:', err);
      }
    };

    fetchProfile();
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    
    if (type === 'checkbox') {
      const checked = (e.target as HTMLInputElement).checked;
      setFormData({ ...formData, [name]: checked });
    } else if (type === 'number') {
      setFormData({ ...formData, [name]: parseInt(value) || 0 });
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
  const personalRoles = [
    { value: 'employee', label: t('profile.employee') },
    { value: 'landlord', label: t('profile.landlord') },
    { value: 'self_employed', label: t('profile.selfEmployed') },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const updatedProfile = await userService.updateProfile(formData);
      updateUser(updatedProfile);
      setSuccess(t('profile.updateSuccess'));
      setIsEditing(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.error'));
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
            <div style={{ borderTop: '1px solid var(--border-color, #e5e7eb)', margin: '0.5rem 0', paddingTop: '0.5rem' }}>
              <label className="role-checkbox-label">
                <input
                  type="checkbox"
                  checked={isGmbHSelected}
                  onChange={() => handleRoleToggle('gmbh')}
                  disabled={!isEditing || loading}
                />
                {t('profile.gmbh')}
              </label>
              <small style={{ display: 'block', color: 'var(--text-secondary, #6b7280)', marginTop: '0.25rem', fontSize: '0.8rem' }}>
                {t('auth.gmbhExclusive', 'GmbH ist eine juristische Person und kann nicht mit anderen Rollen kombiniert werden')}
              </small>
            </div>
          </div>

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
    </div>
  );
};

export default ProfilePage;
