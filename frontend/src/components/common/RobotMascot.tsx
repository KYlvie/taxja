import { useEffect, useRef } from 'react';
import './RobotMascot.css';

interface RobotMascotProps {
  size?: number;
  className?: string;
  /** When true, robot faces forward with no rotation or mouse tracking */
  static?: boolean;
}

const RobotMascot = ({ size = 500, className, static: isStatic }: RobotMascotProps) => {
  const sceneRef = useRef<HTMLDivElement>(null);
  const discRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const tilt = useRef({ rx: 8, ry: 0, targetRx: 8, targetRy: 0, autoAngle: 0, hovering: false });

  const scale = size / 500;

  /* ── 3D tilt loop (skipped when static) ── */
  useEffect(() => {
    if (isStatic) return;
    let id: number;
    const scene = sceneRef.current;

    const onMove = (e: MouseEvent) => {
      if (!scene) return;
      const r = scene.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5;
      const y = (e.clientY - r.top) / r.height - 0.5;
      tilt.current.targetRx = -y * 70;
      tilt.current.targetRy = x * 70;
      tilt.current.hovering = true;
    };
    const onLeave = () => { tilt.current.hovering = false; };

    const tick = () => {
      const t = tilt.current;
      const d = discRef.current;
      if (d) {
        if (!t.hovering) {
          t.autoAngle += 0.003;
          t.targetRx = Math.sin(t.autoAngle * 0.7) * 15 + 8;
          t.targetRy = Math.cos(t.autoAngle) * 15;
        }
        t.rx += (t.targetRx - t.rx) * 0.18;
        t.ry += (t.targetRy - t.ry) * 0.18;
        d.style.transform = `rotateX(${t.rx}deg) rotateY(${t.ry}deg)`;
      }
      id = requestAnimationFrame(tick);
    };

    scene?.addEventListener('mousemove', onMove);
    scene?.addEventListener('mouseleave', onLeave);
    tick();
    return () => { cancelAnimationFrame(id); scene?.removeEventListener('mousemove', onMove); scene?.removeEventListener('mouseleave', onLeave); };
  }, [isStatic]);

  /* ── Canvas particle / arc animation ── */
  useEffect(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    const ctx = cvs.getContext('2d');
    if (!ctx) return;

    const s = size;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    cvs.width = s * dpr; cvs.height = s * dpr;
    ctx.scale(dpr, dpr);
    const cx = s / 2, cy = s / 2, maxR = s * 0.46;

    const parts = Array.from({ length: 12 }, (_, i) => ({
      a: (Math.PI * 2 * i) / 12 + Math.random() * 0.4,
      r: maxR * (0.55 + Math.random() * 0.4),
      sp: (0.3 + Math.random() * 0.7) * (i % 2 ? -1 : 1),
      sz: (1.5 + Math.random() * 2.5) * scale,
      h: 185 + Math.random() * 45,
    }));
    const arcs = [
      { r: maxR * 0.85, sp: 0.35, len: 1.3, h: 195 },
      { r: maxR * 0.65, sp: -0.25, len: 0.9, h: 215 },
    ];
    let time = 0, animId: number;

    const draw = () => {
      time += 0.016;
      ctx.clearRect(0, 0, s, s);
      for (const arc of arcs) {
        const sa = time * arc.sp;
        ctx.beginPath(); ctx.arc(cx, cy, arc.r, sa, sa + arc.len);
        ctx.strokeStyle = `hsla(${arc.h},55%,65%,0.3)`; ctx.lineWidth = 2 * scale;
        ctx.shadowBlur = 10 * scale; ctx.shadowColor = `hsla(${arc.h},50%,60%,0.2)`;
        ctx.stroke(); ctx.shadowBlur = 0;
      }
      for (const p of parts) {
        p.a += p.sp * 0.016;
        const px = cx + Math.cos(p.a) * p.r, py = cy + Math.sin(p.a) * p.r;
        const pulse = 1 + Math.sin(time * 2.5 + p.a) * 0.35;
        ctx.beginPath(); ctx.arc(px, py, p.sz * pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.h},55%,70%,0.5)`;
        ctx.shadowBlur = 6 * scale; ctx.shadowColor = `hsla(${p.h},50%,60%,0.3)`;
        ctx.fill(); ctx.shadowBlur = 0;
      }
      const pr = (22 + Math.sin(time * 1.2) * 5) * scale;
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, pr);
      g.addColorStop(0, 'hsla(190,55%,75%,0.15)');
      g.addColorStop(0.6, 'hsla(190,50%,65%,0.04)');
      g.addColorStop(1, 'hsla(190,45%,55%,0)');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, pr, 0, Math.PI * 2); ctx.fill();
      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animId);
  }, [size, scale]);

  const sizeClass = size <= 200 ? 'robot-mascot--sm' : '';

  return (
    <div
      ref={sceneRef}
      className={`obg-robot ${sizeClass} ${className || ''}`.trim()}
      style={{ width: size, height: size }}
    >
      <canvas ref={canvasRef} className="obg-robot-canvas" />
      <div ref={discRef} className="obg-robot-disc">
        <div className="obg-robot-ring obg-robot-ring-1" style={{ width: 340 * scale, height: 340 * scale }} />
        <div className="obg-robot-ring obg-robot-ring-2" style={{ width: 440 * scale, height: 440 * scale }} />
        <div className="obg-bot" style={{ transform: `translateZ(2px) scale(${scale})` }}>
          <div className="obg-bot-antenna"><div className="obg-bot-antenna-tip" /><div className="obg-bot-antenna-stem" /></div>
          <div className="obg-bot-head"><div className="obg-bot-eye obg-bot-eye-l" /><div className="obg-bot-eye obg-bot-eye-r" /><div className="obg-bot-mouth" /></div>
          <div className="obg-bot-neck" />
          <div className="obg-bot-body"><div className="obg-bot-chest-light" /><div className="obg-bot-arm obg-bot-arm-l" /><div className="obg-bot-arm obg-bot-arm-r" /></div>
        </div>
      </div>
    </div>
  );
};

export default RobotMascot;
