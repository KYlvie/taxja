import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import FuturisticIcon from './FuturisticIcon';
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
      <FuturisticIcon icon={ArrowLeft} tone="slate" size="xs" className="subpage-back-link__icon" />
      <span className="subpage-back-link__text">{text}</span>
    </Link>
  );
};

export default SubpageBackLink;
