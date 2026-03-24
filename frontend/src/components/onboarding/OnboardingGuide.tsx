import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import { FileUp, LayoutDashboard, MessageCircle, UserCog, Sparkles, BarChart3, ArrowLeftRight } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import RobotMascot from '../common/RobotMascot';
import type { TourStep } from './tourConfigs';
import './OnboardingGuide.css';

/* ═══════════════════════════════════════════════════════════ */
interface Step {
  icon: LucideIcon;
  titleKey: string;
  messageKey: string;
  target: string | null;
  placement: 'center' | 'right' | 'top' | 'bottom' | 'left';
}

const STEPS: Step[] = [
  { icon: Sparkles,        titleKey: 'onboarding.welcome.title',      messageKey: 'onboarding.welcome.message',      target: null, placement: 'center' },
  { icon: FileUp,          titleKey: 'onboarding.documents.title',     messageKey: 'onboarding.documents.message',    target: '.sidebar-item[href="/documents"]', placement: 'right' },
  { icon: ArrowLeftRight,  titleKey: 'onboarding.transactions.title',  messageKey: 'onboarding.transactions.message', target: '.sidebar-item[href="/transactions"]', placement: 'right' },
  { icon: LayoutDashboard, titleKey: 'onboarding.dashboard.title',     messageKey: 'onboarding.dashboard.message',    target: '.sidebar-item[href="/dashboard"]', placement: 'right' },
  { icon: BarChart3,       titleKey: 'onboarding.reports.title',       messageKey: 'onboarding.reports.message',      target: '.sidebar-item[href="/reports"]', placement: 'right' },
  { icon: MessageCircle,   titleKey: 'onboarding.ai.title',            messageKey: 'onboarding.ai.message',           target: '.ai-dock-header', placement: 'top' },
  { icon: UserCog,         titleKey: 'onboarding.profile.title',       messageKey: 'onboarding.profile.message',      target: '.user-badge', placement: 'bottom' },
];

const GAP = 14;
const ROBOT_SIZE = 500;

/* ── helpers ── */
const isSidebarTarget = (sel: string | null) =>
  !!sel && sel.startsWith('.sidebar-item');

/* Force sidebar open/close via data attribute — avoids click-toggle race conditions */
const forceSidebarOpen = () => {
  const sidebar = document.querySelector<HTMLElement>('.sidebar');
  if (sidebar) sidebar.setAttribute('data-obg-open', 'true');
};

const forceSidebarClose = () => {
  const sidebar = document.querySelector<HTMLElement>('.sidebar');
  if (sidebar) sidebar.removeAttribute('data-obg-open');
};

/* ═══════════════════════════════════════════════════════════
   Floating text (no box)
   ═══════════════════════════════════════════════════════════ */
const GuideText = ({
  icon: Icon, title, message, step, total,
  onNext, onPrev, onSkip,
}: {
  icon: LucideIcon; title: string; message: string;
  step: number; total: number;
  onNext: () => void; onPrev: () => void; onSkip: () => void;
}) => {
  const { t } = useTranslation();
  const [typed, setTyped] = useState('');
  const [typing, setTyping] = useState(true);
  const [btns, setBtns] = useState(false);

  useEffect(() => {
    setTyped(''); setTyping(true); setBtns(false);
    const td = setTimeout(() => {
      setTyping(false);
      let i = 0;
      const sp = Math.max(6, Math.min(20, 700 / message.length));
      const iv = setInterval(() => {
        i++; setTyped(message.slice(0, i));
        if (i >= message.length) { clearInterval(iv); setTimeout(() => setBtns(true), 200); }
      }, sp);
      return () => clearInterval(iv);
    }, 400);
    return () => clearTimeout(td);
  }, [message]);

  return (
    <div className="obg-text" onClick={(e) => e.stopPropagation()}>
      <div className="obg-text-header" key={`h-${step}`}>
        <Icon size={20} strokeWidth={2} className="obg-text-icon" />
        <h3 className="obg-text-title">{title}</h3>
      </div>
      <div className="obg-text-body" key={`b-${step}`}>
        {typing ? (
          <div className="obg-typing-dots"><span /><span /><span /></div>
        ) : (
          <p className="obg-text-msg">{typed}<span className="obg-cursor" /></p>
        )}
      </div>
      <div className="obg-dots">
        {Array.from({ length: total }, (_, i) => (
          <span key={i} className={`obg-dot${i === step ? ' obg-dot--active' : ''}${i < step ? ' obg-dot--done' : ''}`} />
        ))}
      </div>
      <div className={`obg-actions${btns ? ' obg-actions--visible' : ''}`}>
        <button className="obg-btn obg-btn--skip" onClick={onSkip}>{t('onboarding.skip', 'Skip')}</button>
        <div className="obg-actions-main">
          {step > 0 && <button className="obg-btn obg-btn--prev" onClick={onPrev}>{t('onboarding.prev', 'Back')}</button>}
          <button className="obg-btn obg-btn--next" onClick={onNext}>
            {step === total - 1 ? t('onboarding.finish', "Let's go!") : t('onboarding.next', 'Next')}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════════════ */
interface OnboardingGuideProps {
  onClose?: () => void;
  steps?: TourStep[];
  isPageTour?: boolean;
}

const OnboardingGuide = ({ onClose, steps, isPageTour }: OnboardingGuideProps = {}) => {
  const { t } = useTranslation();
  const completeOnboarding = useAuthStore((s) => s.completeOnboarding);

  const activeSteps = steps ?? STEPS;

  const [step, setStep] = useState(0);
  const [exiting, setExiting] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const prevElRef = useRef<HTMLElement | null>(null);
  const sidebarRef = useRef<HTMLElement | null>(null);
  const sidebarOpenedByUs = useRef(false);

  const cfg = activeSteps[step];

  const fallback = (cfg as TourStep).fallbackTarget;
  const resolveTarget = useCallback((): string | null => {
    if (!cfg.target) return null;
    if (cfg.target === '.ai-dock-header') {
      const el = document.querySelector<HTMLElement>('.ai-dock-header');
      if (el && el.offsetWidth > 0) return '.ai-dock-header';
      return '.ai-fab';
    }
    // Primary target visible?
    const primary = document.querySelector<HTMLElement>(cfg.target);
    if (primary && primary.offsetWidth > 0) return cfg.target;
    // Try fallback
    if (fallback) {
      const fb = document.querySelector<HTMLElement>(fallback);
      if (fb && fb.offsetWidth > 0) return fallback;
    }
    return cfg.target; // let sync() handle missing element gracefully
  }, [cfg.target, fallback]);

  /* ── Open sidebar once, keep open for all sidebar steps, close when leaving ── */
  useEffect(() => {
    const needSidebar = isSidebarTarget(cfg.target);

    if (needSidebar) {
      if (!sidebarOpenedByUs.current) {
        // First sidebar step — open it once
        forceSidebarOpen();
        sidebarOpenedByUs.current = true;
      }
      // Boost sidebar z-index (re-apply each step in case it was reset)
      const timer = setTimeout(() => {
        const sb = document.querySelector<HTMLElement>('.sidebar');
        if (sb) {
          sb.style.zIndex = '10001';
          sidebarRef.current = sb;
        }
      }, sidebarOpenedByUs.current ? 50 : 350);
      return () => clearTimeout(timer);
    } else {
      // Leaving sidebar steps — restore and close
      if (sidebarOpenedByUs.current) {
        if (sidebarRef.current) {
          sidebarRef.current.style.removeProperty('z-index');
          sidebarRef.current = null;
        }
        forceSidebarClose();
        sidebarOpenedByUs.current = false;
      }
    }
  }, [cfg.target]);

  /* ── Sync spotlight position ── */
  const scrolledRef = useRef(false);

  const sync = useCallback(() => {
    if (prevElRef.current) {
      prevElRef.current.style.removeProperty('z-index');
      prevElRef.current.style.removeProperty('position');
      prevElRef.current.style.removeProperty('background');
      prevElRef.current = null;
    }
    const sel = resolveTarget();
    if (!sel) { setRect(null); return; }
    const el = document.querySelector<HTMLElement>(sel);
    if (!el || el.offsetWidth === 0) { setRect(null); return; }

    // Auto-scroll target into view if it's outside the viewport
    if (!scrolledRef.current) {
      const elRect = el.getBoundingClientRect();
      const inView = elRect.top >= 0 && elRect.bottom <= window.innerHeight;
      if (!inView) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        scrolledRef.current = true;
        // Re-sync after scroll animation completes
        setTimeout(() => {
          el.style.zIndex = '10001';
          el.style.position = 'relative';
          el.style.background = 'transparent';
          prevElRef.current = el;
          setRect(el.getBoundingClientRect());
        }, 500);
        return;
      }
    }

    el.style.zIndex = '10001';
    el.style.position = 'relative';
    el.style.background = 'transparent';
    prevElRef.current = el;
    setRect(el.getBoundingClientRect());
  }, [resolveTarget]);

  useEffect(() => {
    // Delay longer for sidebar steps to allow open animation
    const delay = isSidebarTarget(cfg.target) ? 400 : 100;
    const timer = setTimeout(sync, delay);
    window.addEventListener('scroll', sync, true);
    window.addEventListener('resize', sync);
    let ro: ResizeObserver | undefined;
    const sel = resolveTarget();
    if (sel) { const el = document.querySelector(sel); if (el) { ro = new ResizeObserver(sync); ro.observe(el); } }
    return () => { clearTimeout(timer); window.removeEventListener('scroll', sync, true); window.removeEventListener('resize', sync); ro?.disconnect(); };
  }, [sync, resolveTarget, cfg.target]);

  /* ── Cleanup on unmount ── */
  useEffect(() => () => {
    if (prevElRef.current) {
      prevElRef.current.style.removeProperty('z-index');
      prevElRef.current.style.removeProperty('position');
      prevElRef.current.style.removeProperty('background');
    }
    if (sidebarRef.current) {
      sidebarRef.current.style.removeProperty('z-index');
    }
    if (sidebarOpenedByUs.current) {
      forceSidebarClose();
      sidebarOpenedByUs.current = false;
    }
  }, []);

  const finish = useCallback(() => {
    setExiting(true);
    if (prevElRef.current) {
      prevElRef.current.style.removeProperty('z-index');
      prevElRef.current.style.removeProperty('position');
      prevElRef.current.style.removeProperty('background');
    }
    if (sidebarRef.current) {
      sidebarRef.current.style.removeProperty('z-index');
    }
    if (sidebarOpenedByUs.current) {
      forceSidebarClose();
      sidebarOpenedByUs.current = false;
    }
    setTimeout(() => { if (!isPageTour) completeOnboarding(); onClose?.(); }, 300);
  }, [completeOnboarding, onClose, isPageTour]);

  const next = () => { scrolledRef.current = false; step < activeSteps.length - 1 ? setStep(s => s + 1) : finish(); };
  const prev = () => { scrolledRef.current = false; if (step > 0) setStep(s => s - 1); };

  /* ── Positioning: robot moves to each target ── */
  const vw = typeof window !== 'undefined' ? window.innerWidth : 1200;
  const vh = typeof window !== 'undefined' ? window.innerHeight : 800;
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, hi));
  const textW = 420;

  let robotTop: number, robotLeft: number, textTop: number, textLeft: number;

  if (!rect || cfg.placement === 'center') {
    // Welcome — robot centered, text below
    robotTop = clamp((vh - ROBOT_SIZE) / 2 - 60, GAP, vh - ROBOT_SIZE - 100);
    robotLeft = clamp((vw - ROBOT_SIZE) / 2, GAP, vw - ROBOT_SIZE - GAP);
    textTop = clamp(robotTop + ROBOT_SIZE + GAP, GAP, vh - 160);
    textLeft = clamp(vw / 2 - textW / 2, GAP, vw - textW - GAP);
  } else if (cfg.placement === 'right') {
    // Sidebar items — robot to the right of sidebar, text below robot
    robotLeft = rect.right + GAP;
    robotTop = clamp(rect.top + rect.height / 2 - ROBOT_SIZE / 2, GAP, vh - ROBOT_SIZE - GAP);
    textLeft = clamp(robotLeft, GAP, vw - textW - GAP);
    textTop = clamp(robotTop + ROBOT_SIZE + 4, GAP, vh - 200);
    if (robotLeft + ROBOT_SIZE > vw - GAP) {
      robotLeft = clamp((vw - ROBOT_SIZE) / 2, GAP, vw - ROBOT_SIZE - GAP);
      robotTop = clamp((vh - ROBOT_SIZE) / 2 - 60, GAP, vh - ROBOT_SIZE - 100);
      textTop = clamp(robotTop + ROBOT_SIZE + 4, GAP, vh - 160);
      textLeft = clamp(vw / 2 - textW / 2, GAP, vw - textW - GAP);
    }
  } else {
    // top & bottom — robot on one side, text on the other side (no overlap)
    // Determine available space
    const spaceRight = vw - (rect.right + GAP);

    if (cfg.placement === 'bottom') {
      // Content goes below the target
      if (spaceRight >= ROBOT_SIZE + textW + GAP * 2) {
        // Plenty of room: robot right of target, text right of robot
        robotLeft = clamp(rect.right + GAP, GAP, vw - ROBOT_SIZE - GAP);
        robotTop = clamp(rect.bottom + GAP, GAP, vh - ROBOT_SIZE - GAP);
        textLeft = clamp(robotLeft + ROBOT_SIZE / 2 - textW / 2, GAP, vw - textW - GAP);
        textTop = clamp(robotTop + ROBOT_SIZE + 4, GAP, vh - 160);
      } else {
        // Limited space: robot to the left, text to the right
        robotLeft = clamp(GAP, GAP, vw - ROBOT_SIZE - GAP);
        robotTop = clamp(rect.bottom + GAP, GAP, vh - ROBOT_SIZE - GAP);
        textLeft = clamp(robotLeft + ROBOT_SIZE + GAP, GAP, vw - textW - GAP);
        textTop = clamp(robotTop + ROBOT_SIZE / 2 - 60, GAP, vh - 200);
      }
    } else {
      // placement === 'top': content goes above the target
      // Robot to the left half, text to the right half — both above the target
      const contentTop = clamp(rect.top - ROBOT_SIZE - GAP, GAP, vh - ROBOT_SIZE - GAP);

      if (vw >= ROBOT_SIZE + textW + GAP * 3) {
        // Wide screen: robot left, text right, both above target
        robotLeft = clamp(vw / 2 - ROBOT_SIZE - GAP / 2, GAP, vw - ROBOT_SIZE - GAP);
        robotTop = contentTop;
        textLeft = clamp(vw / 2 + GAP / 2, GAP, vw - textW - GAP);
        textTop = clamp(robotTop + ROBOT_SIZE / 2 - 40, GAP, vh - 200);
      } else {
        // Narrow screen: robot centered above, text below robot but above target
        robotLeft = clamp((vw - ROBOT_SIZE) / 2, GAP, vw - ROBOT_SIZE - GAP);
        robotTop = contentTop;
        textLeft = clamp(vw / 2 - textW / 2, GAP, vw - textW - GAP);
        textTop = clamp(robotTop + ROBOT_SIZE + 4, GAP, rect.top - 40);
      }
    }
  }

  /* ── Spotlight: glow border around the target ── */
  const spotStyle = (): React.CSSProperties | undefined => {
    if (!rect) return undefined;
    return { top: rect.top - 4, left: rect.left - 4, width: rect.width + 8, height: rect.height + 8 };
  };

  return createPortal(
    <div className={`obg-overlay${exiting ? ' obg-overlay--exit' : ''}`}>
      {/* Spotlight glow ring around target */}
      {rect && <div className="obg-spotlight" style={spotStyle()} />}

      <div className={`obg-robot-wrap${step === 0 ? ' obg-robot-wave' : ''}`} style={{ position: 'fixed', top: robotTop, left: robotLeft, zIndex: 10002 }}>
        <RobotMascot size={ROBOT_SIZE} />
      </div>

      <div className="obg-text-wrap" style={{ position: 'fixed', top: textTop, left: textLeft, zIndex: 10002 }}>
        <GuideText
          icon={cfg.icon} title={t(cfg.titleKey)} message={t(cfg.messageKey)}
          step={step} total={activeSteps.length}
          onNext={next} onPrev={prev} onSkip={finish}
        />
      </div>
    </div>,
    document.body,
  );
};

export default OnboardingGuide;
