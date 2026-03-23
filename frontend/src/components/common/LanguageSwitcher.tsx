import { useTranslation } from 'react-i18next';
import { normalizeLanguage } from '../../utils/locale';
import Select from './Select';
import 'flag-icons/css/flag-icons.min.css';
import './LanguageSwitcher.css';

const Flag = ({ code }: { code: string }) => (
  <span className={`fi fi-${code}`} style={{ fontSize: '1.1em' }} />
);

const LanguageSwitcher = () => {
  const { i18n, t } = useTranslation();
  const currentLanguage = normalizeLanguage(i18n.resolvedLanguage || i18n.language);

  const languages = [
    { value: 'de', label: 'Deutsch', title: 'Deutsch (\u00D6sterreich)', icon: <Flag code="at" /> },
    { value: 'en', label: 'English', title: 'English', icon: <Flag code="gb" /> },
    { value: 'zh', label: '\u4e2d\u6587', title: '\u4e2d\u6587 (Chinese)', icon: <Flag code="cn" /> },
    { value: 'fr', label: 'Fran\u00e7ais', title: 'Fran\u00e7ais (France)', icon: <Flag code="fr" /> },
    { value: 'ru', label: '\u0420\u0443\u0441\u0441\u043a\u0438\u0439', title: '\u0420\u0443\u0441\u0441\u043a\u0438\u0439 (Russian)', icon: <Flag code="ru" /> },
    { value: 'hu', label: 'Magyar', title: 'Magyar (Hungarian)', icon: <Flag code="hu" /> },
    { value: 'pl', label: 'Polski', title: 'Polski (Polish)', icon: <Flag code="pl" /> },
    { value: 'tr', label: 'T\u00fcrk\u00e7e', title: 'T\u00fcrk\u00e7e (Turkish)', icon: <Flag code="tr" /> },
    { value: 'bs', label: 'BS / HR / SR', title: 'Bosanski / Hrvatski / Srpski', icon: <Flag code="ba" /> },
  ];

  const changeLanguage = (langCode: string) => {
    void i18n.changeLanguage(langCode);
  };

  return (
    <div className="language-switcher">
      <Select
        value={currentLanguage}
        onChange={changeLanguage}
        options={languages}
        size="sm"
        aria-label={t('common.language', 'Language')}
      />
    </div>
  );
};

export default LanguageSwitcher;
