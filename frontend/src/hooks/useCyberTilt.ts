import { useRef, useCallback } from 'react';
import { useThemeStore } from '../stores/themeStore';

const MAX_ANGLE = 10;
const PERSPECTIVE = 800;

/**
 * Lightweight per-element 3D tilt effect, active only in cyber theme.
 * Applies transform directly via style manipulation — no inline style needed.
 *
 * Usage:
 *   const tilt = useCyberTilt();
 *   <div ref={tilt.ref} onMouseMove={tilt.onMove} onMouseLeave={tilt.onLeave} />
 */
export const useCyberTilt = <T extends HTMLElement = HTMLElement>(maxAngle = MAX_ANGLE) => {
  const isCyber = useThemeStore((s) => s.theme === 'cyber');
  const ref = useRef<T>(null);

  const onMove = useCallback((e: React.MouseEvent) => {
    if (!isCyber || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    ref.current.style.transform =
      `perspective(${PERSPECTIVE}px) rotateX(${(-y * maxAngle).toFixed(2)}deg) rotateY(${(x * maxAngle).toFixed(2)}deg)`;
    ref.current.style.transition = 'transform 120ms ease-out';
  }, [isCyber, maxAngle]);

  const onLeave = useCallback(() => {
    if (!ref.current) return;
    ref.current.style.transform = '';
    ref.current.style.transition = 'transform 300ms ease-out';
    // Clean up after the reset animation
    const el = ref.current;
    const cleanup = () => { el.style.removeProperty('transform'); el.style.removeProperty('transition'); };
    el.addEventListener('transitionend', cleanup, { once: true });
    setTimeout(cleanup, 400);
  }, []);

  return { ref, onMove, onLeave };
};
