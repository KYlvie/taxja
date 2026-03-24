import { useState, useRef, useCallback, useEffect } from 'react';
import RobotMascot from './RobotMascot';
import { useCyberTilt } from '../../hooks/useCyberTilt';
import './DraggableRobot.css';

const STORAGE_KEY = 'taxja_robot_pos';
const ROBOT_SIZE = 110;

const loadPos = (): { x: number; y: number } => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { x: window.innerWidth - ROBOT_SIZE - 24, y: window.innerHeight - ROBOT_SIZE - 100 };
};

const savePos = (x: number, y: number) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ x, y })); } catch { /* */ }
};

interface Props {
  onClick: () => void;
}

const DraggableRobot = ({ onClick }: Props) => {
  const [pos, setPos] = useState(loadPos);
  const dragging = useRef(false);
  const wasDragged = useRef(false);
  const offset = useRef({ x: 0, y: 0 });
  const tilt = useCyberTilt<HTMLDivElement>(14);

  const clamp = useCallback((x: number, y: number) => ({
    x: Math.max(0, Math.min(x, window.innerWidth - ROBOT_SIZE)),
    y: Math.max(0, Math.min(y, window.innerHeight - ROBOT_SIZE)),
  }), []);

  /* ── Mouse drag ── */
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    wasDragged.current = false;
    offset.current = { x: e.clientX - pos.x, y: e.clientY - pos.y };

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      wasDragged.current = true;
      const next = clamp(ev.clientX - offset.current.x, ev.clientY - offset.current.y);
      setPos(next);
    };

    const onUp = (ev: MouseEvent) => {
      dragging.current = false;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      const final = clamp(ev.clientX - offset.current.x, ev.clientY - offset.current.y);
      setPos(final);
      savePos(final.x, final.y);
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [pos, clamp]);

  /* ── Touch drag ── */
  const onTouchStart = useCallback((e: React.TouchEvent) => {
    const touch = e.touches[0];
    dragging.current = true;
    wasDragged.current = false;
    offset.current = { x: touch.clientX - pos.x, y: touch.clientY - pos.y };

    const onMove = (ev: TouchEvent) => {
      if (!dragging.current) return;
      ev.preventDefault();
      wasDragged.current = true;
      const t = ev.touches[0];
      const next = clamp(t.clientX - offset.current.x, t.clientY - offset.current.y);
      setPos(next);
    };

    const onEnd = (ev: TouchEvent) => {
      dragging.current = false;
      document.removeEventListener('touchmove', onMove);
      document.removeEventListener('touchend', onEnd);
      const t = ev.changedTouches[0];
      const final = clamp(t.clientX - offset.current.x, t.clientY - offset.current.y);
      setPos(final);
      savePos(final.x, final.y);
    };

    document.addEventListener('touchmove', onMove, { passive: false });
    document.addEventListener('touchend', onEnd);
  }, [pos, clamp]);

  const handleClick = useCallback(() => {
    if (!wasDragged.current) onClick();
  }, [onClick]);

  /* Keep in bounds on resize */
  useEffect(() => {
    const onResize = () => setPos(p => clamp(p.x, p.y));
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [clamp]);

  return (
    <div
      className="draggable-robot"
      style={{ left: pos.x, top: pos.y }}
      onMouseDown={onMouseDown}
      onMouseMove={tilt.onMove}
      onMouseLeave={tilt.onLeave}
      onTouchStart={onTouchStart}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      aria-label="AI Assistant – click to start tour"
    >
      <div className="draggable-robot-glow" />
      <div ref={tilt.ref} className="draggable-robot-inner">
        <RobotMascot size={ROBOT_SIZE} />
      </div>
      <div className="draggable-robot-label">
        <span className="draggable-robot-pulse" />
        Taxja
      </div>
    </div>
  );
};

export default DraggableRobot;
