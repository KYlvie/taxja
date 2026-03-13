import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../stores/authStore';
import { authService } from '../../services/authService';
import LanguageSwitcher from '../../components/common/LanguageSwitcher';
import './AuthPages.css';

const RegisterPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    name: '',
    userType: 'employee',
    userRoles: ['employee'] as string[],
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleRoleToggle = (role: string) => {
    // GmbH is mutually exclusive with all other roles
    if (role === 'gmbh') {
      // Toggle GmbH: if already selected, switch to employee; if not, switch to gmbh only
      if (formData.userRoles.includes('gmbh')) {
        setFormData({ ...formData, userRoles: ['employee'], userType: 'employee' });
      } else {
        setFormData({ ...formData, userRoles: ['gmbh'], userType: 'gmbh' });
      }
      return;
    }
    // If currently GmbH, switching to a personal role replaces it
    if (formData.userRoles.includes('gmbh')) {
      setFormData({ ...formData, userRoles: [role], userType: role });
      return;
    }
    // Normal multi-select for personal roles
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
  const personalRoles = [
    { value: 'employee', label: t('auth.userTypes.employee') },
    { value: 'landlord', label: t('auth.userTypes.landlord') },
    { value: 'self_employed', label: t('auth.userTypes.selfEmployed') },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      const response = await authService.register({
        email: formData.email,
        password: formData.password,
        name: formData.name,
        user_type: formData.userType,
      });

      login(response.user, response.access_token);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.error'));
    } finally {
      setLoading(false);
    }
  };

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
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>{t('auth.name')}</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>{t('auth.password')}</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>{t('auth.confirmPassword')}</label>
            <input
              type="password"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
              disabled={loading}
            />
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
            <div style={{ borderTop: '1px solid var(--border-color, #e5e7eb)', margin: '0.5rem 0', paddingTop: '0.5rem' }}>
              <label className="role-checkbox-label" style={{ opacity: 0.6, cursor: 'not-allowed' }}>
                <input
                  type="checkbox"
                  checked={isGmbHSelected}
                  onChange={() => handleRoleToggle('gmbh')}
                  disabled={true}
                />
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {t('auth.userTypes.gmbh')}
                  <span style={{ 
                    fontSize: '0.75rem', 
                    padding: '0.125rem 0.5rem', 
                    borderRadius: '4px', 
                    background: 'var(--warning-bg, #fef3c7)', 
                    color: 'var(--warning-text, #92400e)',
                    fontWeight: 500
                  }}>
                    {t('common.comingSoon', 'Demnächst')}
                  </span>
                </span>
              </label>
              <small style={{ display: 'block', color: 'var(--text-secondary, #6b7280)', marginTop: '0.25rem', fontSize: '0.8rem' }}>
                {t('auth.gmbhComingSoon', 'GmbH-Unterstützung (K1-Formular) wird in einer zukünftigen Version verfügbar sein')}
              </small>
            </div>
          </div>

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
