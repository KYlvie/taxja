import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import './SubpageBackLink.css';

type SubpageBackLinkProps = {
  to: string;
  label?: string;
  className?: string;
};

const SubpageBackLink = ({ to, label, className = '' }: SubpageBackLinkProps) => {
  const { t } = useTranslation();
  const text = label || t('common.back', 'Back');

  return (
    <Link to={to} className={`subpage-back-link ${className}`.trim()}>
      <span aria-hidden="true">←</span>
      <span>{text}</span>
    </Link>
  );
};

export default SubpageBackLink;
