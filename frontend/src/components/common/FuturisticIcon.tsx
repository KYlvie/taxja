import type { LucideIcon } from 'lucide-react';
import './FuturisticIcon.css';

export type FuturisticIconTone =
  | 'violet'
  | 'cyan'
  | 'emerald'
  | 'amber'
  | 'rose'
  | 'slate';

export type FuturisticIconSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

interface FuturisticIconProps {
  icon: LucideIcon;
  tone?: FuturisticIconTone;
  size?: FuturisticIconSize;
  className?: string;
  title?: string;
}

const FuturisticIcon = ({
  icon: Icon,
  tone = 'violet',
  size = 'md',
  className = '',
  title,
}: FuturisticIconProps) => {
  const labelProps = title ? { role: 'img', 'aria-label': title } : { 'aria-hidden': true };

  return (
    <span
      className={`f-icon f-icon--${tone} f-icon--${size} ${className}`.trim()}
      title={title}
      {...labelProps}
    >
      <span className="f-icon__core" />
      <span className="f-icon__scan" />
      <span className="f-icon__node f-icon__node--tl" />
      <span className="f-icon__node f-icon__node--br" />
      <Icon className="f-icon__glyph" strokeWidth={1.75} />
    </span>
  );
};

export default FuturisticIcon;
