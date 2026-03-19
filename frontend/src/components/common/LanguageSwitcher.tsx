import { useTranslation } from 'react-i18next';
import { normalizeLanguage } from '../../utils/locale';
import './LanguageSwitcher.css';

const LanguageSwitcher = () => {
  const { i18n, t } = useTranslation();
  const currentLanguage = normalizeLanguage(i18n.resolvedLanguage || i18n.language);

  const languages = [
    { code: 'de', label: 'Deutsch' },
    { code: 'en', label: 'English' },
    { code: 'zh', label: '\u4e2d\u6587' },
  ];

  const changeLanguage = (langCode: string) => {
    void i18n.changeLanguage(langCode);
  };

  return (
    <div className="language-switcher">
      <select
        value={currentLanguage}
        onChange={(e) => changeLanguage(e.target.value)}
        className="language-select"
        aria-label={t('common.language', 'Language')}
      >
        {languages.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.label}
          </option>
        ))}
      </select>
    </div>
  );
};

export default LanguageSwitcher;
