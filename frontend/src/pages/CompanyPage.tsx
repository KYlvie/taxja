import { useEffect, useRef, useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { normalizeLanguage } from '../utils/locale';
import LanguageSwitcher from '../components/common/LanguageSwitcher';
import './CompanyPage.css';

/* ═══ Hooks ═══ */

/* Scroll-reveal with IntersectionObserver */
const useReveal = () => {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { el.classList.add('ok-visible'); io.unobserve(el); } },
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return ref;
};

const Reveal = ({ children, className = '', delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) => {
  const ref = useReveal();
  return (
    <div ref={ref} className={`ok-reveal ${className}`} style={delay ? { transitionDelay: `${delay}ms` } : undefined}>
      {children}
    </div>
  );
};

/* Mouse-tracking aurora + parallax */
const usePageEffects = () => {
  const ref = useRef<HTMLDivElement>(null);

  /* Mouse tracking */
  const handleMove = useCallback((e: MouseEvent) => {
    if (!ref.current) return;
    const x = (e.clientX / window.innerWidth) * 100;
    const y = (e.clientY / window.innerHeight) * 100;
    ref.current.style.setProperty('--mx', `${x}%`);
    ref.current.style.setProperty('--my', `${y}%`);
  }, []);

  /* Parallax scroll */
  const handleScroll = useCallback(() => {
    if (!ref.current) return;
    const st = window.scrollY;
    ref.current.style.setProperty('--scroll', `${st}`);
    ref.current.style.setProperty('--scrollY', `${st * 0.3}px`);
  }, []);

  useEffect(() => {
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('scroll', handleScroll);
    };
  }, [handleMove, handleScroll]);
  return ref;
};

/* Matrix data rain canvas */
const DataRainCanvas = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;

    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&*<>{}[]=/\\|~^';
    const fontSize = 22;
    let columns = 0;
    let drops: number[] = [];
    let speeds: number[] = [];
    let hues: number[] = [];

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      columns = Math.floor(canvas.width / fontSize);
      drops = Array.from({ length: columns }, () => Math.random() * -100);
      speeds = Array.from({ length: columns }, () => 0.3 + Math.random() * 0.7);
      hues = Array.from({ length: columns }, () => 195 + Math.random() * 30);
    };
    resize();
    window.addEventListener('resize', resize);

    const draw = () => {
      ctx.fillStyle = 'rgba(3, 3, 8, 0.06)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      for (let i = 0; i < columns; i++) {
        const char = chars[Math.floor(Math.random() * chars.length)];
        const x = i * fontSize;
        const y = drops[i] * fontSize;

        // Head character — bright
        const alpha = 0.6;
        ctx.font = `${fontSize}px "JetBrains Mono", "Fira Code", monospace`;
        ctx.fillStyle = `hsla(${hues[i]}, 55%, 70%, ${alpha})`;
        ctx.shadowBlur = 6;
        ctx.shadowColor = `hsla(${hues[i]}, 50%, 60%, 0.4)`;
        ctx.fillText(char, x, y);
        ctx.shadowBlur = 0;

        // Trail characters — dimmer
        for (let t = 1; t < 6; t++) {
          const trailY = y - t * fontSize;
          if (trailY > 0) {
            const trailAlpha = 0.2 * (1 - t / 6);
            ctx.fillStyle = `hsla(${hues[i]}, 45%, 50%, ${trailAlpha})`;
            const tc = chars[Math.floor(Math.random() * chars.length)];
            ctx.fillText(tc, x, trailY);
          }
        }

        drops[i] += speeds[i];
        if (drops[i] * fontSize > canvas.height && Math.random() > 0.98) {
          drops[i] = Math.random() * -20;
          speeds[i] = 0.3 + Math.random() * 0.7;
        }
      }
      animId = requestAnimationFrame(draw);
    };
    draw();

    return () => { cancelAnimationFrame(animId); window.removeEventListener('resize', resize); };
  }, []);

  return <canvas ref={canvasRef} className="ok-datarain" />;
};

/* Mouse cursor glow follower */
const CursorGlow = () => {
  const glowRef = useRef<HTMLDivElement>(null);
  const trailRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mx = -200, my = -200;
    let gx = -200, gy = -200;
    let tx = -200, ty = -200;
    let animId: number;

    const onMove = (e: MouseEvent) => { mx = e.clientX; my = e.clientY; };
    window.addEventListener('mousemove', onMove);

    const animate = () => {
      // Main glow — smooth follow
      gx += (mx - gx) * 0.35;
      gy += (my - gy) * 0.35;
      if (glowRef.current) {
        glowRef.current.style.transform = `translate(${gx - 150}px, ${gy - 150}px)`;
      }
      // Trail — slower follow
      tx += (mx - tx) * 0.15;
      ty += (my - ty) * 0.15;
      if (trailRef.current) {
        trailRef.current.style.transform = `translate(${tx - 200}px, ${ty - 200}px)`;
      }
      animId = requestAnimationFrame(animate);
    };
    animate();

    return () => { cancelAnimationFrame(animId); window.removeEventListener('mousemove', onMove); };
  }, []);

  return (
    <>
      <div ref={glowRef} className="ok-cursor-glow" />
      <div ref={trailRef} className="ok-cursor-trail" />
    </>
  );
};

/* Typewriter effect hook */
const useTypewriter = (text: string, speed = 40, startDelay = 1500) => {
  const [displayed, setDisplayed] = useState('');
  const [showCursor, setShowCursor] = useState(true);

  useEffect(() => {
    let i = 0;
    let timeout: ReturnType<typeof setTimeout>;

    const startTyping = () => {
      const type = () => {
        if (i <= text.length) {
          setDisplayed(text.slice(0, i));
          i++;
          timeout = setTimeout(type, speed + Math.random() * 30);
        } else {
          // Blink cursor then hide
          setTimeout(() => setShowCursor(false), 2000);
        }
      };
      type();
    };

    timeout = setTimeout(startTyping, startDelay);
    return () => clearTimeout(timeout);
  }, [text, speed, startDelay]);

  return displayed + (showCursor ? '\u2588' : '');
};

/* 3D tilt card wrapper */
export const TiltCard = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => {
  const cardRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const el = cardRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    el.style.transform = `perspective(600px) rotateY(${x * 20}deg) rotateX(${-y * 20}deg) translateZ(20px) scale(1.05)`;
    // Move inner glow
    el.style.setProperty('--tilt-x', `${(x + 0.5) * 100}%`);
    el.style.setProperty('--tilt-y', `${(y + 0.5) * 100}%`);
  }, []);

  const handleMouseLeave = useCallback(() => {
    const el = cardRef.current;
    if (!el) return;
    el.style.transform = 'perspective(600px) rotateY(0deg) rotateX(0deg) translateZ(0px) scale(1)';
  }, []);

  return (
    <div
      ref={cardRef}
      className={`ok-tilt ${className}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <div className="ok-tilt-glare" />
      {children}
    </div>
  );
};

/* Canvas orbital disc — animated rings + orbiting particles + mouse interaction */
const OrbCanvas = ({ size = 160, hue = 170 }: { size?: number; hue?: number }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hover = useRef(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;
    let time = 0;
    const s = size * 2; // retina
    canvas.width = s; canvas.height = s;
    const cx = s / 2, cy = s / 2;

    // Orbiting particles
    const orbs: { angle: number; r: number; speed: number; size: number; hueOff: number }[] = [];
    for (let i = 0; i < 18; i++) {
      orbs.push({
        angle: Math.random() * Math.PI * 2,
        r: 24 + Math.random() * 28,
        speed: (0.3 + Math.random() * 0.6) * (Math.random() > 0.5 ? 1 : -1),
        size: 1 + Math.random() * 2,
        hueOff: Math.random() * 40 - 20,
      });
    }

    const draw = () => {
      time += 0.016;
      ctx.clearRect(0, 0, s, s);
      const speedMul = hover.current ? 2 : 1;
      const glowMul = hover.current ? 1.4 : 1;

      // Outer ring
      ctx.beginPath();
      ctx.arc(cx, cy, 56, 0, Math.PI * 2);
      ctx.strokeStyle = `hsla(${hue}, 50%, 60%, ${0.12 * glowMul})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      // Rotating arc segments
      for (let a = 0; a < 3; a++) {
        const startAngle = time * (0.5 + a * 0.2) * speedMul + a * 2.1;
        ctx.beginPath();
        ctx.arc(cx, cy, 56, startAngle, startAngle + 0.8);
        ctx.strokeStyle = `hsla(${hue + a * 20}, 55%, 65%, ${0.6 * glowMul})`;
        ctx.lineWidth = 1.5;
        ctx.shadowBlur = 6 * glowMul;
        ctx.shadowColor = `hsla(${hue + a * 20}, 50%, 60%, 0.4)`;
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // Inner ring
      ctx.beginPath();
      ctx.arc(cx, cy, 38, 0, Math.PI * 2);
      ctx.strokeStyle = `hsla(${hue + 40}, 45%, 60%, ${0.1 * glowMul})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      // Inner rotating arcs (reverse)
      for (let a = 0; a < 2; a++) {
        const startAngle = -time * (0.4 + a * 0.3) * speedMul + a * 3;
        ctx.beginPath();
        ctx.arc(cx, cy, 38, startAngle, startAngle + 1.2);
        ctx.strokeStyle = `hsla(${hue + 60 + a * 30}, 50%, 65%, ${0.45 * glowMul})`;
        ctx.lineWidth = 1.5;
        ctx.shadowBlur = 5 * glowMul;
        ctx.shadowColor = `hsla(${hue + 60}, 45%, 60%, 0.3)`;
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // Orbiting particles
      for (const o of orbs) {
        o.angle += o.speed * 0.016 * speedMul;
        const px = cx + Math.cos(o.angle) * o.r;
        const py = cy + Math.sin(o.angle) * o.r;
        const pulse = 1 + Math.sin(time * 3 + o.angle) * 0.3;
        ctx.beginPath();
        ctx.arc(px, py, o.size * pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${hue + o.hueOff}, 50%, 65%, ${0.55 * glowMul})`;
        ctx.shadowBlur = 4 * glowMul;
        ctx.shadowColor = `hsla(${hue + o.hueOff}, 45%, 60%, 0.35)`;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // Center pulse
      const pulseR = 8 + Math.sin(time * 2) * 3;
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, pulseR * glowMul);
      grad.addColorStop(0, `hsla(${hue}, 50%, 75%, ${0.35 * glowMul})`);
      grad.addColorStop(1, `hsla(${hue}, 45%, 60%, 0)`);
      ctx.beginPath();
      ctx.arc(cx, cy, pulseR * glowMul, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();

      // Pulse wave ring (expanding)
      const waveR = ((time * 30 * speedMul) % 60);
      ctx.beginPath();
      ctx.arc(cx, cy, waveR, 0, Math.PI * 2);
      ctx.strokeStyle = `hsla(${hue}, 45%, 65%, ${0.12 * (1 - waveR / 60) * glowMul})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animId);
  }, [size, hue]);

  return (
    <canvas
      ref={canvasRef}
      className="ok-orb-canvas"
      style={{ width: size, height: size }}
      onMouseEnter={() => { hover.current = true; }}
      onMouseLeave={() => { hover.current = false; }}
    />
  );
};

/* ═══ Large orbital disc canvas — background for the 3D solar system ═══ */
const BigOrbitCanvas = ({ size = 800 }: { size?: number }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;
    let time = 0;
    const s = size * 2;
    canvas.width = s; canvas.height = s;
    const cx = s / 2, cy = s / 2;

    const particles: { angle: number; r: number; speed: number; size: number; hue: number }[] = [];
    for (let i = 0; i < 150; i++) {
      particles.push({
        angle: Math.random() * Math.PI * 2,
        r: 40 + Math.random() * (s * 0.45),
        speed: (0.06 + Math.random() * 0.2) * (Math.random() > 0.5 ? 1 : -1),
        size: 0.5 + Math.random() * 2.5,
        hue: 190 + Math.random() * 50,
      });
    }

    const arcs: { r: number; speed: number; len: number; hue: number; w: number }[] = [];
    for (let i = 0; i < 12; i++) {
      arcs.push({
        r: 60 + Math.random() * (s * 0.42),
        speed: (0.08 + Math.random() * 0.35) * (Math.random() > 0.5 ? 1 : -1),
        len: 0.2 + Math.random() * 1.0,
        hue: 195 + Math.random() * 45,
        w: 1 + Math.random() * 2.5,
      });
    }

    const draw = () => {
      time += 0.016;
      ctx.clearRect(0, 0, s, s);

      // Concentric rings
      for (let i = 0; i < 7; i++) {
        const r = s * (0.06 + i * 0.065);
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(${200 + i * 6}, 50%, 60%, ${0.04 + i * 0.006})`;
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 14 + i * 3]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Energy arcs
      for (const a of arcs) {
        const sa = time * a.speed;
        ctx.beginPath();
        ctx.arc(cx, cy, a.r, sa, sa + a.len);
        ctx.strokeStyle = `hsla(${a.hue}, 50%, 60%, 0.3)`;
        ctx.lineWidth = a.w;
        ctx.shadowBlur = 6;
        ctx.shadowColor = `hsla(${a.hue}, 45%, 55%, 0.2)`;
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // Particles
      for (const p of particles) {
        p.angle += p.speed * 0.016;
        const px = cx + Math.cos(p.angle) * p.r;
        const py = cy + Math.sin(p.angle) * p.r;
        const pulse = 1 + Math.sin(time * 2.5 + p.angle) * 0.4;
        ctx.beginPath();
        ctx.arc(px, py, p.size * pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 50%, 65%, 0.4)`;
        ctx.fill();
      }

      // Center glow
      const pr = 60 + Math.sin(time * 1.2) * 18;
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, pr);
      g.addColorStop(0, 'hsla(200, 50%, 75%, 0.18)');
      g.addColorStop(0.4, 'hsla(200, 45%, 65%, 0.06)');
      g.addColorStop(1, 'hsla(200, 40%, 55%, 0)');
      ctx.beginPath();
      ctx.arc(cx, cy, pr, 0, Math.PI * 2);
      ctx.fillStyle = g;
      ctx.fill();

      // Pulse waves
      for (let w = 0; w < 3; w++) {
        const wr = ((time * 22 + w * 140) % 420);
        ctx.beginPath();
        ctx.arc(cx, cy, wr, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(200, 45%, 65%, ${0.06 * (1 - wr / 420)})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animId);
  }, [size]);

  return <canvas ref={canvasRef} className="ok-orb-canvas ok-solar-bg-canvas" style={{ width: size, height: size }} />;
};

/* ═══ Node mini canvas — each service node gets its own animated ring ═══ */
const NodeCanvas = ({ size = 160, hue = 170, active = false }: { size?: number; hue?: number; active?: boolean }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const activeRef = useRef(active);
  activeRef.current = active;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;
    let time = 0;
    const s = size * 2;
    canvas.width = s; canvas.height = s;
    const cx = s / 2, cy = s / 2;
    const maxR = s * 0.46;

    // 3 layers of orbiting particles at different radii
    const orbs: { angle: number; r: number; speed: number; sz: number; hOff: number; layer: number }[] = [];
    for (let i = 0; i < 30; i++) {
      const layer = i < 10 ? 0 : i < 20 ? 1 : 2;
      const rMin = layer === 0 ? 0.25 : layer === 1 ? 0.5 : 0.75;
      const rMax = layer === 0 ? 0.5 : layer === 1 ? 0.75 : 0.95;
      orbs.push({
        angle: Math.random() * Math.PI * 2,
        r: maxR * (rMin + Math.random() * (rMax - rMin)),
        speed: (0.3 + Math.random() * 0.9) * (Math.random() > 0.5 ? 1 : -1),
        sz: layer === 2 ? 0.8 + Math.random() * 1.5 : 1.2 + Math.random() * 2.5,
        hOff: Math.random() * 50 - 25,
        layer,
      });
    }

    const draw = () => {
      time += 0.016;
      ctx.clearRect(0, 0, s, s);
      const isActive = activeRef.current;
      const gm = isActive ? 1.3 : 1;
      const sm = isActive ? 1.3 : 1;

      // ── Layer 0: Deep background energy field ──
      const bgPulse = 1 + Math.sin(time * 0.8) * 0.15;
      const bgGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxR * bgPulse);
      bgGrad.addColorStop(0, `hsla(${hue}, 55%, 65%, ${0.06 * gm})`);
      bgGrad.addColorStop(0.4, `hsla(${hue + 30}, 45%, 50%, ${0.025 * gm})`);
      bgGrad.addColorStop(0.7, `hsla(${hue + 60}, 35%, 40%, ${0.01 * gm})`);
      bgGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, s, s);

      // ── Layer 1: Outermost dashed ring ──
      ctx.beginPath();
      ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
      ctx.setLineDash([4, 8]);
      ctx.strokeStyle = `hsla(${hue}, 40%, 55%, ${0.1 * gm})`;
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);

      // ── Layer 2: Outer solid ring with glow ──
      const outerR = maxR * 0.92;
      ctx.beginPath();
      ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
      ctx.strokeStyle = `hsla(${hue}, 50%, 60%, ${0.12 * gm})`;
      ctx.lineWidth = 1.5;
      ctx.shadowBlur = 8 * gm;
      ctx.shadowColor = `hsla(${hue}, 50%, 55%, ${0.15 * gm})`;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // ── Layer 3: 3 rotating bright arc segments on outer ring ──
      for (let a = 0; a < 3; a++) {
        const sa = time * (0.5 + a * 0.2) * sm + a * 2.1;
        ctx.beginPath();
        ctx.arc(cx, cy, outerR, sa, sa + 0.8);
        ctx.strokeStyle = `hsla(${hue + a * 20}, 60%, 68%, ${0.65 * gm})`;
        ctx.lineWidth = 2.5;
        ctx.shadowBlur = 10 * gm;
        ctx.shadowColor = `hsla(${hue + a * 20}, 55%, 60%, 0.5)`;
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // ── Layer 4: Middle ring ──
      const midR = maxR * 0.65;
      ctx.beginPath();
      ctx.arc(cx, cy, midR, 0, Math.PI * 2);
      ctx.strokeStyle = `hsla(${hue + 30}, 45%, 58%, ${0.08 * gm})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      // 2 counter-rotating arcs on middle ring
      for (let a = 0; a < 2; a++) {
        const sa = -time * (0.4 + a * 0.3) * sm + a * 3;
        ctx.beginPath();
        ctx.arc(cx, cy, midR, sa, sa + 1.1);
        ctx.strokeStyle = `hsla(${hue + 50 + a * 25}, 55%, 65%, ${0.5 * gm})`;
        ctx.lineWidth = 2;
        ctx.shadowBlur = 7 * gm;
        ctx.shadowColor = `hsla(${hue + 50}, 50%, 58%, 0.3)`;
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // ── Layer 5: Inner ring (dashed, reverse spin) ──
      const innerR = maxR * 0.4;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(time * 0.3 * sm);
      ctx.translate(-cx, -cy);
      ctx.beginPath();
      ctx.arc(cx, cy, innerR, 0, Math.PI * 2);
      ctx.setLineDash([3, 10]);
      ctx.strokeStyle = `hsla(${hue + 60}, 45%, 60%, ${0.12 * gm})`;
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();

      // 1 bright arc on inner ring
      const innerSa = time * 0.7 * sm;
      ctx.beginPath();
      ctx.arc(cx, cy, innerR, innerSa, innerSa + 1.5);
      ctx.strokeStyle = `hsla(${hue + 80}, 55%, 68%, ${0.4 * gm})`;
      ctx.lineWidth = 1.5;
      ctx.shadowBlur = 5 * gm;
      ctx.shadowColor = `hsla(${hue + 80}, 50%, 60%, 0.25)`;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // ── Layer 6: Orbiting particles with trails ──
      for (const o of orbs) {
        o.angle += o.speed * 0.016 * sm;
        const px = cx + Math.cos(o.angle) * o.r;
        const py = cy + Math.sin(o.angle) * o.r;
        const pulse = 1 + Math.sin(time * 3 + o.angle) * 0.4;
        const sz = o.sz * pulse;

        // Particle trail (faint line behind)
        const trailAngle = o.angle - o.speed * 0.016 * sm * 6;
        const tx = cx + Math.cos(trailAngle) * o.r;
        const ty = cy + Math.sin(trailAngle) * o.r;
        ctx.beginPath();
        ctx.moveTo(tx, ty);
        ctx.lineTo(px, py);
        ctx.strokeStyle = `hsla(${hue + o.hOff}, 45%, 60%, ${0.15 * gm})`;
        ctx.lineWidth = sz * 0.6;
        ctx.stroke();

        // Particle glow halo
        const haloGrad = ctx.createRadialGradient(px, py, 0, px, py, sz * 4);
        haloGrad.addColorStop(0, `hsla(${hue + o.hOff}, 55%, 70%, ${0.12 * gm})`);
        haloGrad.addColorStop(1, 'transparent');
        ctx.fillStyle = haloGrad;
        ctx.fillRect(px - sz * 4, py - sz * 4, sz * 8, sz * 8);

        // Particle core
        ctx.beginPath();
        ctx.arc(px, py, sz, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${hue + o.hOff}, 60%, 72%, ${0.7 * gm})`;
        ctx.shadowBlur = 6 * gm;
        ctx.shadowColor = `hsla(${hue + o.hOff}, 55%, 65%, 0.5)`;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // ── Layer 7: Center energy core — multi-layer radial gradient ──
      const coreR = (maxR * 0.2) + Math.sin(time * 2) * (maxR * 0.05);
      // Outer haze
      const g1 = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 2 * gm);
      g1.addColorStop(0, `hsla(${hue}, 50%, 75%, ${0.12 * gm})`);
      g1.addColorStop(0.5, `hsla(${hue + 20}, 45%, 60%, ${0.04 * gm})`);
      g1.addColorStop(1, 'transparent');
      ctx.fillStyle = g1;
      ctx.beginPath();
      ctx.arc(cx, cy, coreR * 2 * gm, 0, Math.PI * 2);
      ctx.fill();
      // Bright core
      const g2 = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * gm);
      g2.addColorStop(0, `hsla(${hue}, 60%, 82%, ${0.35 * gm})`);
      g2.addColorStop(0.6, `hsla(${hue}, 55%, 68%, ${0.15 * gm})`);
      g2.addColorStop(1, `hsla(${hue}, 45%, 55%, 0)`);
      ctx.fillStyle = g2;
      ctx.beginPath();
      ctx.arc(cx, cy, coreR * gm, 0, Math.PI * 2);
      ctx.fill();

      // ── Layer 8: Expanding pulse waves (2 staggered) ──
      for (let w = 0; w < 2; w++) {
        const wr = ((time * 20 * sm + w * (maxR * 0.45)) % (maxR * 0.9));
        const wAlpha = 0.08 * (1 - wr / (maxR * 0.9)) * gm;
        ctx.beginPath();
        ctx.arc(cx, cy, wr, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(${hue + w * 30}, 50%, 65%, ${wAlpha})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // ── Layer 9: Cross-hair lines (subtle, active only) ──
      if (isActive) {
        ctx.globalAlpha = 0.06 * gm;
        ctx.beginPath();
        ctx.moveTo(cx, cy - maxR * 0.95);
        ctx.lineTo(cx, cy + maxR * 0.95);
        ctx.moveTo(cx - maxR * 0.95, cy);
        ctx.lineTo(cx + maxR * 0.95, cy);
        ctx.strokeStyle = `hsla(${hue}, 50%, 65%, 1)`;
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 6]);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
      }

      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animId);
  }, [size, hue]);

  return <canvas ref={canvasRef} className="ok-orb-canvas" style={{ width: size, height: size }} />;
};

/* ═══ Service Solar System — 3D perspective rotating disc ═══ */
const ServiceOrbit = ({ services, renderIcon }: {
  services: { title: string; desc: string }[];
  renderIcon: (i: number) => React.ReactNode;
}) => {
  const [active, setActive] = useState<number | null>(null);
  const discRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<HTMLDivElement>(null);
  const tilt = useRef({ rx: 0, ry: 0, targetRx: 12, targetRy: 0, autoAngle: 0, hovering: false });

  // Mouse-interactive 3D tilt + auto gentle rotation
  useEffect(() => {
    let animId: number;

    const onMove = (e: MouseEvent) => {
      const scene = sceneRef.current;
      if (!scene) return;
      const rect = scene.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;  // -0.5 to 0.5
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      tilt.current.targetRx = -y * 70;  // up to ±35 degrees
      tilt.current.targetRy = x * 70;
      tilt.current.hovering = true;
    };

    const onLeave = () => {
      tilt.current.hovering = false;
    };

    const animate = () => {
      const t = tilt.current;
      const disc = discRef.current;
      if (!disc) { animId = requestAnimationFrame(animate); return; }

      if (!t.hovering) {
        // Auto gentle rotation when not hovering
        t.autoAngle += 0.003;
        t.targetRx = Math.sin(t.autoAngle * 0.7) * 15 + 8;
        t.targetRy = Math.cos(t.autoAngle) * 15;
      }

      // Smooth interpolation
      t.rx += (t.targetRx - t.rx) * 0.18;
      t.ry += (t.targetRy - t.ry) * 0.18;

      disc.style.transform = `rotateX(${t.rx}deg) rotateY(${t.ry}deg)`;

      animId = requestAnimationFrame(animate);
    };

    const scene = sceneRef.current;
    if (scene) {
      scene.addEventListener('mousemove', onMove);
      scene.addEventListener('mouseleave', onLeave);
    }
    animate();

    return () => {
      cancelAnimationFrame(animId);
      if (scene) {
        scene.removeEventListener('mousemove', onMove);
        scene.removeEventListener('mouseleave', onLeave);
      }
    };
  }, []);

  return (
    <div className="ok-solar">
      <div className="ok-solar-layout">
        <div className="ok-solar-scene" ref={sceneRef}>
          <div className="ok-solar-disc" ref={discRef}>
            {/* Background canvas */}
            <div className="ok-solar-canvas">
              <BigOrbitCanvas size={1400} />
            </div>

            {/* Center core — hidden when detail is visible */}
            <div className={`ok-solar-core ${active !== null ? 'ok-solar-core-hidden' : ''}`}>
              <div className="ok-solar-core-ring" />
              <div className="ok-solar-core-ring ok-solar-core-ring-2" />
              <span className="ok-solar-core-text">OOHK</span>
              <span className="ok-solar-core-sub">AI SYSTEMS</span>
            </div>

            {/* 6 nodes on the circumference */}
            {services.map((s, i) => (
              <div
                key={i}
                className={`ok-solar-node ${active === i ? 'ok-solar-node-active' : ''}`}
                style={{ '--node-angle': `${i * 60 - 90}deg`, '--node-hue': `${170 + i * 15}` } as React.CSSProperties}
                onMouseEnter={() => setActive(i)}
                onMouseLeave={() => setActive(null)}
              >
                <div className="ok-solar-node-canvas">
                  <NodeCanvas size={200} hue={200 + i * 15} active={active === i} />
                </div>
                <div className="ok-solar-node-content">
                  <div className="ok-solar-node-icon">{renderIcon(i)}</div>
                  <span className="ok-solar-node-title">{s.title}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Detail HUD panel — centered overlay */}
          <div className={`ok-solar-detail ${active !== null ? 'ok-solar-detail-visible' : ''}`}>
            <span className="ok-detail-corner ok-detail-corner-tl" />
            <span className="ok-detail-corner ok-detail-corner-tr" />
            <span className="ok-detail-corner ok-detail-corner-bl" />
            <span className="ok-detail-corner ok-detail-corner-br" />
            <div className="ok-detail-scanlines" />
            <div className="ok-detail-energy-bar" />
            {active !== null && (
              <>
                <div className="ok-detail-header">
                  <div className="ok-detail-orb">
                    <NodeCanvas size={90} hue={200 + active * 15} active />
                    <div className="ok-detail-orb-icon">{renderIcon(active)}</div>
                  </div>
                  <div className="ok-detail-meta">
                    <div className="ok-detail-tag">MODULE_{String(active + 1).padStart(2, '0')}</div>
                    <div className="ok-detail-index">
                      <span className="ok-detail-idx">{String(active + 1).padStart(2, '0')}</span>
                      <span className="ok-detail-slash">/</span>
                      <span className="ok-detail-total">{String(services.length).padStart(2, '0')}</span>
                    </div>
                  </div>
                </div>
                <h3 className="ok-detail-title">{services[active].title}</h3>
                <p className="ok-detail-desc">{services[active].desc}</p>
                <div className="ok-detail-status">
                  <span className="ok-detail-status-dot" />
                  <span>ONLINE</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

/* ═══ Product full-card animated canvas — plasma field + orbiting rings ═══ */
const ProductCardCanvas = ({ hue = 170 }: { hue?: number }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hover = useRef(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;
    let time = 0;

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (!rect) return;
      canvas.width = rect.width * 2;
      canvas.height = rect.height * 2;
    };
    resize();
    window.addEventListener('resize', resize);

    // Plasma blobs
    const blobs: { x: number; y: number; vx: number; vy: number; r: number; hOff: number }[] = [];
    for (let i = 0; i < 6; i++) {
      blobs.push({
        x: Math.random(), y: Math.random(),
        vx: (Math.random() - 0.5) * 0.003,
        vy: (Math.random() - 0.5) * 0.003,
        r: 0.15 + Math.random() * 0.15,
        hOff: Math.random() * 40 - 20,
      });
    }

    // Orbiting sparks
    const sparks: { angle: number; r: number; speed: number; sz: number; hOff: number }[] = [];
    for (let i = 0; i < 30; i++) {
      sparks.push({
        angle: Math.random() * Math.PI * 2,
        r: 0.2 + Math.random() * 0.35,
        speed: (0.3 + Math.random() * 0.8) * (Math.random() > 0.5 ? 1 : -1),
        sz: 1 + Math.random() * 2.5,
        hOff: Math.random() * 50 - 25,
      });
    }

    const draw = () => {
      time += 0.016;
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      const isHover = hover.current;
      const gm = isHover ? 1.6 : 1;
      const sm = isHover ? 1.5 : 1;
      const cx = w / 2, cy = h / 2;

      // Plasma blobs
      for (const b of blobs) {
        b.x += b.vx * sm; b.y += b.vy * sm;
        if (b.x < 0 || b.x > 1) b.vx *= -1;
        if (b.y < 0 || b.y > 1) b.vy *= -1;
        const bx = b.x * w, by = b.y * h;
        const br = b.r * Math.min(w, h);
        const pulse = 1 + Math.sin(time * 1.5 + b.hOff) * 0.3;
        const g = ctx.createRadialGradient(bx, by, 0, bx, by, br * pulse);
        g.addColorStop(0, `hsla(${hue + b.hOff}, 50%, 60%, ${0.08 * gm})`);
        g.addColorStop(0.5, `hsla(${hue + b.hOff}, 45%, 50%, ${0.03 * gm})`);
        g.addColorStop(1, 'transparent');
        ctx.fillStyle = g;
        ctx.fillRect(bx - br * pulse, by - br * pulse, br * pulse * 2, br * pulse * 2);
      }

      // Concentric rings
      for (let i = 0; i < 3; i++) {
        const rr = (0.15 + i * 0.12) * Math.min(w, h);
        const sa = time * (0.3 + i * 0.15) * sm;
        ctx.beginPath();
        ctx.arc(cx, cy, rr, sa, sa + 1.2 + i * 0.3);
        ctx.strokeStyle = `hsla(${hue + i * 25}, 50%, 60%, ${0.2 * gm})`;
        ctx.lineWidth = 1.5;
        ctx.shadowBlur = 5 * gm;
        ctx.shadowColor = `hsla(${hue + i * 25}, 45%, 58%, 0.25)`;
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // Orbiting sparks
      for (const s of sparks) {
        s.angle += s.speed * 0.016 * sm;
        const sr = s.r * Math.min(w, h) * 0.5;
        const sx = cx + Math.cos(s.angle) * sr;
        const sy = cy + Math.sin(s.angle) * sr;
        const pulse = 1 + Math.sin(time * 3 + s.angle) * 0.4;
        ctx.beginPath();
        ctx.arc(sx, sy, s.sz * pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${hue + s.hOff}, 50%, 63%, ${0.4 * gm})`;
        ctx.fill();
      }

      // Center glow pulse
      const pr = 0.08 * Math.min(w, h) + Math.sin(time * 1.8) * 0.02 * Math.min(w, h);
      const cg = ctx.createRadialGradient(cx, cy, 0, cx, cy, pr * gm);
      cg.addColorStop(0, `hsla(${hue}, 50%, 72%, ${0.14 * gm})`);
      cg.addColorStop(1, 'transparent');
      ctx.fillStyle = cg;
      ctx.beginPath();
      ctx.arc(cx, cy, pr * gm, 0, Math.PI * 2);
      ctx.fill();

      // Expanding wave
      const wr = ((time * 40 * sm) % (Math.min(w, h) * 0.5));
      ctx.beginPath();
      ctx.arc(cx, cy, wr, 0, Math.PI * 2);
      ctx.strokeStyle = `hsla(${hue}, 45%, 63%, ${0.07 * (1 - wr / (Math.min(w, h) * 0.5)) * gm})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(animId); window.removeEventListener('resize', resize); };
  }, [hue]);

  return (
    <canvas
      ref={canvasRef}
      className="ok-prod-bg-canvas"
      onMouseEnter={() => { hover.current = true; }}
      onMouseLeave={() => { hover.current = false; }}
    />
  );
};

/* ═══ Stat card mini canvas — pulsing energy field ═══ */
const StatCanvas = ({ hue = 170 }: { hue?: number }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;
    let time = 0;

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (!rect) return;
      canvas.width = rect.width * 2;
      canvas.height = rect.height * 2;
    };
    resize();
    window.addEventListener('resize', resize);

    // Orbiting dots
    const dots: { angle: number; r: number; speed: number; sz: number }[] = [];
    for (let i = 0; i < 16; i++) {
      dots.push({
        angle: Math.random() * Math.PI * 2,
        r: 0.25 + Math.random() * 0.3,
        speed: (0.5 + Math.random() * 1.0) * (Math.random() > 0.5 ? 1 : -1),
        sz: 0.8 + Math.random() * 1.5,
      });
    }

    const draw = () => {
      time += 0.016;
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);
      const cx = w / 2, cy = h / 2;
      const minD = Math.min(w, h);

      // Background radial pulse
      const pr = minD * (0.3 + Math.sin(time * 1.2) * 0.08);
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, pr);
      g.addColorStop(0, `hsla(${hue}, 50%, 63%, 0.07)`);
      g.addColorStop(0.6, `hsla(${hue}, 45%, 50%, 0.025)`);
      g.addColorStop(1, 'transparent');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);

      // Rotating arc
      for (let i = 0; i < 2; i++) {
        const sa = time * (0.5 + i * 0.3) + i * Math.PI;
        const rr = minD * (0.2 + i * 0.08);
        ctx.beginPath();
        ctx.arc(cx, cy, rr, sa, sa + 0.9);
        ctx.strokeStyle = `hsla(${hue + i * 30}, 50%, 60%, 0.25)`;
        ctx.lineWidth = 1.5;
        ctx.shadowBlur = 5;
        ctx.shadowColor = `hsla(${hue + i * 30}, 45%, 58%, 0.2)`;
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // Orbiting dots
      for (const d of dots) {
        d.angle += d.speed * 0.016;
        const dr = d.r * minD * 0.5;
        const dx = cx + Math.cos(d.angle) * dr;
        const dy = cy + Math.sin(d.angle) * dr;
        const pulse = 1 + Math.sin(time * 3 + d.angle) * 0.3;
        ctx.beginPath();
        ctx.arc(dx, dy, d.sz * pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${hue}, 50%, 63%, 0.35)`;
        ctx.fill();
      }

      // Expanding wave
      const wr = ((time * 25) % (minD * 0.4));
      ctx.beginPath();
      ctx.arc(cx, cy, wr, 0, Math.PI * 2);
      ctx.strokeStyle = `hsla(${hue}, 45%, 63%, ${0.05 * (1 - wr / (minD * 0.4))})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(animId); window.removeEventListener('resize', resize); };
  }, [hue]);

  return <canvas ref={canvasRef} className="ok-stat-bg-canvas" />;
};

/* ═══ Tech ticker card canvas — small energy pulse ═══ */
const TickerCardCanvas = ({ hue = 170 }: { hue?: number }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;
    let time = 0;

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (!rect) return;
      canvas.width = rect.width * 2;
      canvas.height = rect.height * 2;
    };
    resize();

    const sparks: { x: number; y: number; vx: number; vy: number; life: number; maxLife: number }[] = [];

    const draw = () => {
      time += 0.016;
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      // Flowing energy lines
      for (let i = 0; i < 3; i++) {
        const yy = h * (0.2 + i * 0.3);
        const offset = time * 60 + i * 100;
        ctx.beginPath();
        ctx.moveTo(0, yy);
        for (let x = 0; x < w; x += 4) {
          const wave = Math.sin((x + offset) * 0.015) * 8 + Math.sin((x + offset) * 0.008) * 4;
          ctx.lineTo(x, yy + wave);
        }
        ctx.strokeStyle = `hsla(${hue + i * 20}, 50%, 60%, 0.07)`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Random sparks
      if (Math.random() < 0.08) {
        sparks.push({
          x: Math.random() * w, y: Math.random() * h,
          vx: (Math.random() - 0.5) * 2, vy: (Math.random() - 0.5) * 2,
          life: 0, maxLife: 30 + Math.random() * 30,
        });
      }
      for (let i = sparks.length - 1; i >= 0; i--) {
        const s = sparks[i];
        s.x += s.vx; s.y += s.vy; s.life++;
        const alpha = 0.35 * (1 - s.life / s.maxLife);
        ctx.beginPath();
        ctx.arc(s.x, s.y, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${hue}, 50%, 63%, ${alpha})`;
        ctx.fill();
        if (s.life > s.maxLife) sparks.splice(i, 1);
      }

      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(animId); };
  }, [hue]);

  return <canvas ref={canvasRef} className="ok-ticker-bg-canvas" />;
};

/* Canvas particle network — enhanced with pulse waves, mouse attraction, shooting stars */
const ParticleCanvas = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouse = useRef({ x: -1000, y: -1000 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;
    let time = 0;

    interface Particle { x: number; y: number; vx: number; vy: number; r: number; baseR: number; hue: number; }
    const particles: Particle[] = [];
    const shootingStars: { x: number; y: number; vx: number; vy: number; life: number; maxLife: number; }[] = [];

    const resize = () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; };
    resize();
    window.addEventListener('resize', resize);

    const onMouse = (e: MouseEvent) => { mouse.current = { x: e.clientX, y: e.clientY }; };
    window.addEventListener('mousemove', onMouse);

    /* Create particles */
    const count = Math.min(120, Math.floor(window.innerWidth / 14));
    for (let i = 0; i < count; i++) {
      const r = Math.random() * 2 + 0.3;
      particles.push({
        x: Math.random() * canvas.width, y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.6, vy: (Math.random() - 0.5) * 0.6,
        r, baseR: r, hue: 200 + Math.random() * 40,
      });
    }

    const draw = () => {
      time += 0.016;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const mx = mouse.current.x;
      const my = mouse.current.y;

      /* Pulse wave from center */
      const pulseR = ((time * 80) % 600);
      const cx = canvas.width / 2;
      const cy = canvas.height / 2;

      /* Move & draw particles */
      for (const p of particles) {
        /* Mouse attraction */
        const dmx = mx - p.x;
        const dmy = my - p.y;
        const dMouse = Math.sqrt(dmx * dmx + dmy * dmy);
        if (dMouse < 200 && dMouse > 1) {
          p.vx += (dmx / dMouse) * 0.02;
          p.vy += (dmy / dMouse) * 0.02;
        }

        /* Pulse effect */
        const dCenter = Math.sqrt((p.x - cx) ** 2 + (p.y - cy) ** 2);
        const pulseDist = Math.abs(dCenter - pulseR);
        if (pulseDist < 30) {
          p.r = p.baseR * (1 + (1 - pulseDist / 30) * 2);
        } else {
          p.r += (p.baseR - p.r) * 0.05;
        }

        p.vx *= 0.99; p.vy *= 0.99;
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        const glow = dMouse < 200 ? 0.5 : 0.3;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 50%, 65%, ${glow})`;
        ctx.shadowBlur = p.r * 3;
        ctx.shadowColor = `hsla(${p.hue}, 45%, 60%, 0.3)`;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      /* Draw connections */
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 140) {
            const alpha = 0.08 * (1 - dist / 140);
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(160, 196, 208, ${alpha * 1.5})`;
            ctx.lineWidth = 0.6;
            ctx.stroke();
          }
        }
      }

      /* Shooting stars */
      if (Math.random() < 0.06) {
        shootingStars.push({
          x: Math.random() * canvas.width, y: 0,
          vx: (Math.random() - 0.5) * 12, vy: Math.random() * 10 + 6,
          life: 0, maxLife: 55 + Math.random() * 40,
        });
      }
      for (let i = shootingStars.length - 1; i >= 0; i--) {
        const s = shootingStars[i];
        s.x += s.vx; s.y += s.vy; s.life++;
        const alpha = 1 - s.life / s.maxLife;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(s.x - s.vx * 7, s.y - s.vy * 7);
        ctx.strokeStyle = `rgba(160, 196, 208, ${alpha * 0.5})`;
        ctx.lineWidth = 4;
        ctx.shadowBlur = 10;
        ctx.shadowColor = `rgba(160, 196, 208, ${alpha * 0.3})`;
        ctx.stroke();
        ctx.shadowBlur = 0;
        if (s.life > s.maxLife) shootingStars.splice(i, 1);
      }

      /* Pulse ring */
      ctx.beginPath();
      ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(160, 196, 208, ${0.02 * (1 - pulseR / 600)})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      animId = requestAnimationFrame(draw);
    };
    draw();

    return () => { cancelAnimationFrame(animId); window.removeEventListener('resize', resize); window.removeEventListener('mousemove', onMouse); };
  }, []);

  return <canvas ref={canvasRef} className="ok-particles" />;
};

/* Animated counter */
const AnimatedNum = ({ value }: { value: string }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [displayed, setDisplayed] = useState(value);
  const hasAnimated = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !hasAnimated.current) {
        hasAnimated.current = true;
        /* If it's a pure number, animate counting */
        const num = parseInt(value, 10);
        if (!isNaN(num) && num > 0 && num <= 9999) {
          const duration = 1200;
          const start = performance.now();
          const step = (now: number) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const ease = 1 - Math.pow(1 - progress, 3); /* easeOutCubic */
            setDisplayed(String(Math.round(num * ease)));
            if (progress < 1) requestAnimationFrame(step);
          };
          requestAnimationFrame(step);
        } else {
          /* For text values, do a character scramble */
          const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
          let iteration = 0;
          const interval = setInterval(() => {
            setDisplayed(
              value.split('').map((c, i) =>
                i < iteration ? c : chars[Math.floor(Math.random() * chars.length)]
              ).join('')
            );
            iteration += 0.5;
            if (iteration >= value.length) clearInterval(interval);
          }, 40);
        }
        io.unobserve(el);
      }
    }, { threshold: 0.5 });
    io.observe(el);
    return () => io.disconnect();
  }, [value]);

  return <div ref={ref} className="ok-num-val">{displayed}</div>;
};

/* ═══ HUD SVG Icons ═══ */
const HudIcon = ({ index }: { index: number }) => {
  const icons = [
    /* 0: Agent — neural node */
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><circle cx="24" cy="24" r="8" opacity="0.6"/><circle cx="24" cy="24" r="3"/><line x1="24" y1="16" x2="24" y2="6"/><line x1="24" y1="32" x2="24" y2="42"/><line x1="16" y1="24" x2="6" y2="24"/><line x1="32" y1="24" x2="42" y2="24"/><circle cx="24" cy="6" r="2"/><circle cx="24" cy="42" r="2"/><circle cx="6" cy="24" r="2"/><circle cx="42" cy="24" r="2"/><line x1="17.5" y1="17.5" x2="11" y2="11"/><line x1="30.5" y1="30.5" x2="37" y2="37"/><circle cx="10" cy="10" r="1.5" opacity="0.5"/><circle cx="38" cy="38" r="1.5" opacity="0.5"/></svg>,
    /* 1: Knowledge — hexagonal database */
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="24,4 42,14 42,34 24,44 6,34 6,14"/><line x1="6" y1="14" x2="42" y2="14" opacity="0.3"/><line x1="6" y1="24" x2="42" y2="24" opacity="0.3"/><line x1="6" y1="34" x2="42" y2="34" opacity="0.3"/><line x1="24" y1="4" x2="24" y2="44" opacity="0.2"/><circle cx="24" cy="14" r="2"/><circle cx="24" cy="24" r="2"/><circle cx="24" cy="34" r="2"/></svg>,
    /* 2: Automation — circuit flow */
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M8 24h8l4-8 4 16 4-12 4 4h8"/><circle cx="8" cy="24" r="3" opacity="0.5"/><circle cx="40" cy="24" r="3" opacity="0.5"/><line x1="24" y1="8" x2="24" y2="14" opacity="0.3"/><line x1="24" y1="34" x2="24" y2="40" opacity="0.3"/><rect x="20" y="4" width="8" height="4" rx="1" opacity="0.4"/><rect x="20" y="40" width="8" height="4" rx="1" opacity="0.4"/></svg>,
    /* 3: Integration — connected nodes */
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><rect x="4" y="18" width="12" height="12" rx="2" opacity="0.5"/><rect x="32" y="4" width="12" height="12" rx="2" opacity="0.5"/><rect x="32" y="32" width="12" height="12" rx="2" opacity="0.5"/><line x1="16" y1="22" x2="32" y2="12"/><line x1="16" y1="28" x2="32" y2="38"/><circle cx="24" cy="17" r="1.5"/><circle cx="24" cy="33" r="1.5"/></svg>,
    /* 4: Consulting — targeting reticle */
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><circle cx="24" cy="24" r="16" opacity="0.3"/><circle cx="24" cy="24" r="10" opacity="0.5"/><circle cx="24" cy="24" r="3"/><line x1="24" y1="2" x2="24" y2="12"/><line x1="24" y1="36" x2="24" y2="46"/><line x1="2" y1="24" x2="12" y2="24"/><line x1="36" y1="24" x2="46" y2="24"/></svg>,
    /* 5: Software — code terminal */
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="8" width="40" height="32" rx="3" opacity="0.4"/><line x1="4" y1="16" x2="44" y2="16" opacity="0.3"/><circle cx="10" cy="12" r="1.5" opacity="0.5"/><circle cx="16" cy="12" r="1.5" opacity="0.5"/><polyline points="12,24 18,28 12,32"/><line x1="22" y1="32" x2="32" y2="32" opacity="0.5"/></svg>,
  ];
  return <span className="ok-hud-icon">{icons[index % icons.length]}</span>;
};

/* Product HUD icons */
const ProdHudIcon = ({ index }: { index: number }) => {
  const icons = [
    /* 0: Taxja — receipt/document scan */
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 4h18l10 10v30a2 2 0 01-2 2H12a2 2 0 01-2-2V6a2 2 0 012-2z" opacity="0.4"/><path d="M30 4v10h10"/><line x1="16" y1="22" x2="32" y2="22" opacity="0.5"/><line x1="16" y1="28" x2="28" y2="28" opacity="0.5"/><line x1="16" y1="34" x2="24" y2="34" opacity="0.5"/><path d="M34 32l4 4-4 4" opacity="0.6"/><circle cx="38" cy="36" r="8" strokeDasharray="3 2" opacity="0.3"/></svg>,
    /* 1: Enterprise — holographic cube */
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"><path d="M24 4L42 14v20L24 44 6 34V14z" opacity="0.3"/><path d="M24 4L42 14 24 24 6 14z" opacity="0.5"/><line x1="24" y1="24" x2="24" y2="44" opacity="0.4"/><line x1="24" y1="24" x2="42" y2="14" opacity="0.2"/><line x1="24" y1="24" x2="6" y2="14" opacity="0.2"/><circle cx="24" cy="24" r="4" opacity="0.6"/></svg>,
    /* 2: Industry — vertical bars / spectrum */
    <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><line x1="8" y1="40" x2="8" y2="28"/><line x1="14" y1="40" x2="14" y2="20"/><line x1="20" y1="40" x2="20" y2="12"/><line x1="26" y1="40" x2="26" y2="8"/><line x1="32" y1="40" x2="32" y2="16"/><line x1="38" y1="40" x2="38" y2="24"/><path d="M4 28c4-4 8 0 12-8s8-4 12-12c4 8 8 4 12 8s8 4 12-4" opacity="0.25" strokeDasharray="2 2"/><circle cx="26" cy="8" r="2.5" opacity="0.5"/></svg>,
  ];
  return <span className="ok-hud-icon ok-hud-icon-lg">{icons[index % icons.length]}</span>;
};

/* ═══ Page Component ═══ */
const CompanyPage = () => {
  const { i18n } = useTranslation();
  const lang = normalizeLanguage(i18n.resolvedLanguage || i18n.language);
  const c = copy[lang] || copy.en;
  const pageRef = usePageEffects();
  const rollingAiTags = [...c.aiTags, ...c.aiTags];
  const rollingEngTags = [...c.engTags, ...c.engTags];
  const typedSub = useTypewriter(c.heroSub, 8, 300);

  /* Contact form state */
  const [formData, setFormData] = useState({ name: '', email: '', message: '' });
  const [formStatus, setFormStatus] = useState<'idle' | 'sending' | 'ok' | 'error'>('idle');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormStatus('sending');
    try {
      const res = await fetch('/api/v1/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...formData, language: lang }),
      });
      if (!res.ok) throw new Error();
      setFormStatus('ok');
      setFormData({ name: '', email: '', message: '' });
    } catch {
      setFormStatus('error');
    }
  };

  return (
    <div className="ok-page" ref={pageRef}>
      {/* ── Layered dynamic backgrounds ── */}
      <ParticleCanvas />
      <DataRainCanvas />
      <CursorGlow />
      <div className="ok-aurora">
        <div className="ok-aurora-a" />
        <div className="ok-aurora-b" />
        <div className="ok-aurora-c" />
      </div>
      <div className="ok-noise" />

      {/* Floating geometric shapes */}
      <div className="ok-geo ok-geo-1" />
      <div className="ok-geo ok-geo-2" />
      <div className="ok-geo ok-geo-3" />
      <div className="ok-geo ok-geo-4" />

      {/* Energy pulse rings */}
      <div className="ok-energy-ring ok-energy-ring-1" />
      <div className="ok-energy-ring ok-energy-ring-2" />
      <div className="ok-energy-ring ok-energy-ring-3" />

      {/* ── Nav ── */}
      <nav className="ok-nav">
        <div className="ok-logo" aria-label="OOHK">
          <span className="ok-logo-dot" />
          <span className="ok-logo-text">OOHK</span>
        </div>
        <div className="ok-nav-r">
          <LanguageSwitcher />
          <Link to="/" className="ok-nav-back">{c.backToTaxja}</Link>
        </div>
      </nav>

      {/* ═══ Hero ═══ */}
      <section className="ok-hero">
        <div className="ok-hero-inner">
          <span className="ok-hero-badge">
            <span className="ok-hero-badge-dot" />
            {c.badge}
          </span>
          <h1 className="ok-hero-h1">
            <span className="ok-word ok-word-1">{c.heroLine1}</span>{' '}
            <span className="ok-word ok-word-accent">{c.heroLine2}</span>
          </h1>
          <p className="ok-hero-sub ok-typewriter">{typedSub}</p>
          <div className="ok-hero-cta">
            <a href="#ok-contact-section" className="ok-btn-primary" onClick={(e) => { e.preventDefault(); document.getElementById('ok-contact-section')?.scrollIntoView({ behavior: 'smooth' }); }}>
              <span className="ok-btn-shine" />
              {c.ctaContact}
            </a>
            <Link to="/" className="ok-btn-outline">{c.ctaProduct}</Link>
          </div>
        </div>

        {/* Animated scroll indicator */}
        <div className="ok-scroll-hint">
          <div className="ok-scroll-line">
            <div className="ok-scroll-dot" />
          </div>
        </div>
      </section>

      {/* ═══ Wave divider ═══ */}
      <div className="ok-wave">
        <svg viewBox="0 0 1440 120" preserveAspectRatio="none">
          <path className="ok-wave-1" d="M0,60 C240,120 480,0 720,60 C960,120 1200,0 1440,60 L1440,120 L0,120Z" />
          <path className="ok-wave-2" d="M0,80 C360,20 600,100 900,40 C1100,0 1300,80 1440,50 L1440,120 L0,120Z" />
        </svg>
      </div>

      {/* ═══ Services — Solar System ═══ */}
      <section className="ok-sec ok-sec-dark">
        <Reveal className="ok-sec-head">
          <span className="ok-label">{c.servicesKicker}</span>
          <h2>{c.servicesTitle}</h2>
          <p>{c.servicesDesc}</p>
        </Reveal>
        <Reveal>
          <ServiceOrbit
            services={c.services}
            renderIcon={(i: number) => <HudIcon index={i} />}
          />
        </Reveal>
      </section>

      {/* ═══ Products ═══ */}
      <section className="ok-sec">
        <Reveal className="ok-sec-head">
          <span className="ok-label">{c.productsKicker}</span>
          <h2>{c.productsTitle}</h2>
          <p>{c.productsDesc}</p>
        </Reveal>
        <div className="ok-prod-discs">
          {c.products.map((p, i) => (
            <Reveal key={i} className="ok-prod-card" delay={i * 150}>
              <TiltCard className="ok-prod-tilt">
                <div className="ok-prod-card-inner">
                  {/* Full-card animated canvas background */}
                  <ProductCardCanvas hue={200 + i * 30} />
                  {/* HUD corners */}
                  <span className="ok-hud-corner ok-hud-corner-tl" />
                  <span className="ok-hud-corner ok-hud-corner-tr" />
                  <span className="ok-hud-corner ok-hud-corner-bl" />
                  <span className="ok-hud-corner ok-hud-corner-br" />
                  <div className="ok-prod-scanlines" />
                  <div className="ok-prod-energy-top" />
                  <div className="ok-prod-orb-area">
                    <div className="ok-disc-wrap">
                      <OrbCanvas size={200} hue={200 + i * 30} />
                      <div className="ok-disc-core">
                        <ProdHudIcon index={i} />
                        <span className={`ok-disc-status ${p.status}`}>
                          <span className="ok-disc-dot" />
                          {p.statusLabel}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="ok-prod-text">
                    <div className="ok-prod-tag">PRODUCT_{String(i + 1).padStart(2, '0')}</div>
                    <h3>{p.name}</h3>
                    <p>{p.desc}</p>
                  </div>
                </div>
              </TiltCard>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ═══ About / Stats ═══ */}
      <section className="ok-sec ok-sec-dark">
        <Reveal className="ok-sec-head">
          <span className="ok-label">{c.aboutKicker}</span>
          <h2>{c.aboutTitle}</h2>
          <p>{c.aboutDesc}</p>
        </Reveal>
        <div className="ok-num-strip">
          {c.stats.map((s, i) => (
            <Reveal key={i} className="ok-num" delay={i * 100}>
              <TiltCard className="ok-stat-tilt">
                <div className="ok-stat-inner">
                  <StatCanvas hue={200 + i * 20} />
                  <div className="ok-num-idx">{String(i + 1).padStart(2, '0')}</div>
                  <AnimatedNum value={s.value} />
                  <div className="ok-num-lbl">{s.label}</div>
                  <div className="ok-num-pulse" />
                </div>
              </TiltCard>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ═══ Tech — marquee tickers ═══ */}
      <section className="ok-sec ok-sec-tech">
        <Reveal className="ok-sec-head">
          <span className="ok-label">{c.techKicker}</span>
          <h2>{c.techTitle}</h2>
          <p>{c.techDesc}</p>
        </Reveal>

        <div className="ok-ticker-label">{c.aiLabel}</div>
        <div className="ok-ticker ok-ticker-ai">
          <div className="ok-ticker-track ok-ticker-left">
            {rollingAiTags.map((t, i) => (
              <div key={`${t.name}-${i}`} className="ok-ticker-card">
                <TickerCardCanvas hue={200 + (i % 6) * 15} />
                <div className="ok-ticker-card-glow" />
                <strong>{t.name}</strong>
                <span>{t.desc}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="ok-ticker-label ok-ticker-label-dim">{c.engLabel}</div>
        <div className="ok-ticker ok-ticker-eng">
          <div className="ok-ticker-track ok-ticker-right">
            {rollingEngTags.map((tag, i) => (
              <span key={`${tag}-${i}`} className="ok-ticker-tag">{tag}</span>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ Contact ═══ */}
      <section className="ok-contact" id="ok-contact-section">
        <Reveal>
          <div className="ok-contact-hud">
            <span className="ok-hud-corner ok-hud-corner-tl" />
            <span className="ok-hud-corner ok-hud-corner-tr" />
            <span className="ok-hud-corner ok-hud-corner-bl" />
            <span className="ok-hud-corner ok-hud-corner-br" />
            <div className="ok-contact-scanlines" />
            <div className="ok-contact-energy-top" />
            <div className="ok-contact-tag">COMM_TERMINAL</div>
            <h2>{c.contactTitle}</h2>
            <p className="ok-contact-desc">{c.contactDesc}</p>

            {formStatus === 'ok' ? (
              <div className="ok-form-success">{c.formSuccess}</div>
            ) : (
              <form className="ok-contact-form" onSubmit={handleSubmit}>
                <div className="ok-form-row">
                  <input
                    type="text"
                    required
                    placeholder={c.formName}
                    value={formData.name}
                    onChange={e => setFormData(p => ({ ...p, name: e.target.value }))}
                    className="ok-input"
                    aria-label={c.formName}
                  />
                  <input
                    type="email"
                    required
                    placeholder={c.formEmail}
                    value={formData.email}
                    onChange={e => setFormData(p => ({ ...p, email: e.target.value }))}
                    className="ok-input"
                    aria-label={c.formEmail}
                  />
                </div>
                <textarea
                  required
                  minLength={10}
                  rows={4}
                  placeholder={c.formMessage}
                  value={formData.message}
                  onChange={e => setFormData(p => ({ ...p, message: e.target.value }))}
                  className="ok-input ok-textarea"
                  aria-label={c.formMessage}
                />
                {formStatus === 'error' && (
                  <p className="ok-form-error">{c.formError}</p>
                )}
                <button type="submit" className="ok-btn-primary ok-form-btn" disabled={formStatus === 'sending'}>
                  <span className="ok-btn-shine" />
                  {formStatus === 'sending' ? c.formSending : c.formSubmit}
                </button>
              </form>
            )}

            <div className="ok-contact-links">
              <a href="mailto:office@oohk.com">office@oohk.com</a>
              <a href="tel:+436644601118">+43 664 460 1118</a>
            </div>
            <p className="ok-contact-addr">Thenneberg 51, 2571 Thenneberg, Austria</p>
          </div>
        </Reveal>
      </section>

      {/* Footer */}
      <footer className="ok-footer">
        <p>
          &copy; {new Date().getFullYear()} OOHK &middot;{' '}
          <Link to="/legal/impressum">{c.legalLink}</Link>
          {' '}&middot;{' '}
          <Link to="/legal/datenschutz">{c.privacyLink}</Link>
        </p>
      </footer>
    </div>
  );
};

/* ═══════════ i18n Copy ═══════════ */
interface CompanyCopy {
  badge: string;
  heroLine1: string;
  heroLine2: string;
  heroSub: string;
  ctaContact: string;
  ctaProduct: string;
  backToTaxja: string;
  servicesKicker: string;
  servicesTitle: string;
  servicesDesc: string;
  services: { title: string; desc: string }[];
  productsKicker: string;
  productsTitle: string;
  productsDesc: string;
  products: { icon: string; name: string; desc: string; status: string; statusLabel: string }[];
  aboutKicker: string;
  aboutTitle: string;
  aboutDesc: string;
  stats: { value: string; label: string }[];
  techKicker: string;
  techTitle: string;
  techDesc: string;
  aiLabel: string;
  aiTags: { name: string; desc: string }[];
  engLabel: string;
  engTags: string[];
  contactTitle: string;
  contactDesc: string;
  formName: string;
  formEmail: string;
  formMessage: string;
  formSubmit: string;
  formSending: string;
  formSuccess: string;
  formError: string;
  legalLink: string;
  privacyLink: string;
}

const copy: Record<string, CompanyCopy> = {
  zh: {
    badge: 'AI Agent \u00B7 \u667A\u80FD\u81EA\u52A8\u5316 \u00B7 \u5B9A\u5236\u5F00\u53D1',
    heroLine1: '\u4E3A\u60A8\u6253\u9020',
    heroLine2: '\u4E13\u5C5E AI \u5DE5\u4F5C\u7CFB\u7EDF',
    heroSub: 'OOHK \u4E13\u6CE8\u4E8E AI Agent \u5B9A\u5236\u3001\u77E5\u8BC6\u5E93\u6784\u5EFA\u3001\u4E1A\u52A1\u6D41\u7A0B\u81EA\u52A8\u5316\u4E0E\u7CFB\u7EDF\u96C6\u6210\u670D\u52A1\u3002\u7B80\u5355\u8BF4\uff0C\u5C31\u662F\u5E2E\u60A8\u505A\u4E00\u5957\u4F1A\u56DE\u7B54\u3001\u4F1A\u6574\u7406\u8D44\u6599\u3001\u4F1A\u81EA\u52A8\u5E72\u6D3B\u7684 AI \u5DE5\u4F5C\u7CFB\u7EDF\u3002',
    ctaContact: '\u8054\u7CFB\u6211\u4EEC',
    ctaProduct: '\u67E5\u770B Taxja \u2192',
    backToTaxja: '\u2190 Taxja',
    servicesKicker: '\u6838\u5FC3\u80FD\u529B',
    servicesTitle: '\u9762\u5411\u771F\u5B9E\u4E1A\u52A1\u7684 AI \u89E3\u51B3\u65B9\u6848',
    servicesDesc: '\u6211\u4EEC\u4EE5\u4E1A\u52A1\u76EE\u6807\u4E3A\u5BFC\u5411\uff0c\u5C06\u6A21\u578B\u80FD\u529B\u3001\u77E5\u8BC6\u8D44\u4EA7\u4E0E\u73B0\u6709\u7CFB\u7EDF\u6574\u5408\u4E3A\u53EF\u4EA4\u4ED8\u3001\u53EF\u8FD0\u8425\u3001\u53EF\u6301\u7EED\u8FED\u4EE3\u7684 AI \u5DE5\u4F5C\u7CFB\u7EDF\u3002',
    services: [
      { title: '\u5B9A\u5236 AI Agent \u7CFB\u7EDF', desc: '\u56F4\u7ED5\u5BA2\u6237\u670D\u52A1\u3001\u8FD0\u8425\u534F\u540C\u3001\u8D22\u7A0E\u5904\u7406\u4E0E\u5185\u90E8\u6D41\u7A0B\u7B49\u573A\u666F\uff0c\u8BBE\u8BA1\u53EF\u6267\u884C\u3001\u53EF\u7BA1\u7406\u7684 AI Agent \u89E3\u51B3\u65B9\u6848\u3002' },
      { title: '\u4F01\u4E1A\u77E5\u8BC6\u5E93\u4E0E RAG \u4F53\u7CFB', desc: '\u5C06\u6587\u6863\u3001\u5236\u5EA6\u3001FAQ\u3001\u4E1A\u52A1\u8D44\u6599\u4E0E\u5386\u53F2\u8BB0\u5F55\u7ED3\u6784\u5316\u6574\u7406\uff0c\u6784\u5EFA\u53EF\u68C0\u7D22\u3001\u53EF\u8FFD\u6EAF\u3001\u53EF\u6301\u7EED\u66F4\u65B0\u7684\u77E5\u8BC6\u5E95\u5EA7\u3002' },
      { title: '\u6D41\u7A0B\u81EA\u52A8\u5316\u4E0E\u4EFB\u52A1\u7F16\u6392', desc: '\u5C06\u90AE\u4EF6\u3001\u8868\u5355\u3001\u5BA1\u6279\u3001\u5BA2\u6237\u8DDF\u8FDB\u4E0E\u6570\u636E\u5904\u7406\u4E32\u8054\u6210\u5B8C\u6574\u94FE\u8DEF\uff0c\u8BA9\u9AD8\u9891\u4E1A\u52A1\u6D41\u7A0B\u5B9E\u73B0\u81EA\u52A8\u89E6\u53D1\u4E0E\u7A33\u5B9A\u6267\u884C\u3002' },
      { title: '\u7CFB\u7EDF\u96C6\u6210\u4E0E\u8FDE\u63A5\u80FD\u529B', desc: '\u6253\u901A CRM\u3001ERP\u3001\u6570\u636E\u5E93\u3001\u8868\u683C\u3001\u5185\u90E8\u5E73\u53F0\u4E0E\u7B2C\u4E09\u65B9\u670D\u52A1\uff0c\u8BA9 AI \u771F\u6B63\u8FDB\u5165\u65E2\u6709\u4E1A\u52A1\u94FE\u8DEF\u3002' },
      { title: '\u65B9\u6848\u8BBE\u8BA1\u4E0E\u843D\u5730\u54A8\u8BE2', desc: '\u4ECE\u573A\u666F\u8BC6\u522B\u3001\u4F18\u5148\u7EA7\u6392\u5E8F\u5230\u5B9E\u65BD\u8DEF\u5F84\u8BBE\u8BA1\uff0c\u5E2E\u52A9\u60A8\u4EE5\u66F4\u53EF\u63A7\u7684\u6295\u5165\u63A8\u8FDB AI \u9879\u76EE\u843D\u5730\u3002' },
      { title: '\u5B9A\u5236\u5E94\u7528\u4E0E AI \u5DE5\u4F5C\u53F0', desc: '\u4EA4\u4ED8\u9762\u5411\u56E2\u961F\u4F7F\u7528\u7684 Web \u5E94\u7528\u3001\u5185\u90E8\u5DE5\u4F5C\u53F0\u4E0E\u8F7B\u91CF\u5316\u5DE5\u5177\uff0c\u786E\u4FDD\u65B9\u6848\u4E0D\u4EC5\u53EF\u5C55\u793A\uff0c\u66F4\u80FD\u957F\u671F\u8FD0\u884C\u3002' },
    ],
    productsKicker: '\u4EA7\u54C1\u77E9\u9635',
    productsTitle: '\u5DF2\u4E0A\u7EBF\u4E0E\u5F00\u53D1\u4E2D\u7684\u4EA7\u54C1',
    productsDesc: '\u57FA\u4E8E\u6211\u4EEC\u7684\u6280\u672F\u80FD\u529B\uFF0C\u6B63\u5728\u6784\u5EFA\u53EF\u590D\u5236\u7684\u884C\u4E1A\u89E3\u51B3\u65B9\u6848\u3002',
    products: [
      { icon: '\uD83E\uDDFE', name: 'Taxja', desc: '\u9762\u5411\u5965\u5730\u5229\u4E2A\u4EBA\u7EB3\u7A0E\u4EBA\u7684 AI \u7A0E\u52A1\u52A9\u624B\u3002\u81EA\u52A8\u8BC6\u522B\u7968\u636E\u3001\u667A\u80FD\u5206\u7C7B\u4EA4\u6613\u3001\u4E00\u952E\u751F\u6210\u7A0E\u52A1\u62A5\u544A\u3002', status: 'live', statusLabel: '\u5DF2\u4E0A\u7EBF' },
      { icon: '\uD83C\uDFE2', name: 'AI \u4F01\u4E1A\u5DE5\u4F5C\u53F0', desc: '\u4E3A\u4E2D\u5C0F\u4F01\u4E1A\u6253\u9020\u7684\u7EDF\u4E00 AI \u5DE5\u4F5C\u5165\u53E3\u2014\u2014\u96C6\u6210\u6587\u6863\u5904\u7406\u3001\u5BA2\u6237\u7BA1\u7406\u3001\u8D22\u52A1\u5206\u6790\u3001\u5185\u90E8\u77E5\u8BC6\u95EE\u7B54\u3002', status: 'dev', statusLabel: '\u5F00\u53D1\u4E2D' },
      { icon: '\uD83C\uDFAF', name: '\u884C\u4E1A AI \u89E3\u51B3\u65B9\u6848', desc: '\u57FA\u4E8E Taxja \u7B49\u4EA7\u54C1\u79EF\u7D2F\u7684\u7ECF\u9A8C\uFF0C\u62D3\u5C55\u9910\u996E\u3001\u7535\u5546\u3001\u81EA\u7531\u804C\u4E1A\u7B49\u5782\u76F4\u884C\u4E1A\u7684\u6807\u51C6\u5316 AI \u5DE5\u5177\u5305\u3002', status: 'dev', statusLabel: '\u89C4\u5212\u4E2D' },
    ],
    aboutKicker: '\u5173\u4E8E\u6211\u4EEC',
    aboutTitle: 'OOHK',
    aboutDesc: 'OOHK \u7ACB\u8DB3\u5965\u5730\u5229\uFF0C\u4EE5\u201C\u5B9A\u5236\u5207\u5165\u3001\u6A21\u5757\u6C89\u6DC0\u3001\u6301\u7EED\u8FED\u4EE3\u201D\u7684\u65B9\u5F0F\u6784\u5EFA\u5B9E\u7528\u3001\u53EF\u843D\u5730\u7684 AI \u89E3\u51B3\u65B9\u6848\u4E0E\u5DE5\u4F5C\u7CFB\u7EDF\u3002',
    stats: [
      { value: '2026', label: '\u6210\u7ACB\u5E74\u4EFD' },
      { value: '\u5965\u5730\u5229', label: '\u603B\u90E8\u6240\u5728\u5730' },
      { value: 'AI-First', label: '\u6280\u672F\u7406\u5FF5' },
      { value: 'GDPR', label: '\u6570\u636E\u5408\u89C4' },
    ],
    techKicker: '\u6280\u672F\u80FD\u529B',
    techTitle: 'AI \u80FD\u529B\u4E0E\u6280\u672F\u67B6\u6784',
    techDesc: '\u8FD9\u4E9B\u80FD\u529B\u4F1A\u88AB\u7EC4\u5408\u8FDB\u6211\u4EEC\u6B63\u5728\u505A\u7684\u4EA7\u54C1\u91CC\uff0c\u6BD4\u5982 Taxja\u3001AI \u5DE5\u4F5C\u53F0\u3001\u6587\u6863\u5904\u7406\u5DE5\u5177\u548C\u884C\u4E1A\u81EA\u52A8\u5316\u65B9\u6848\u3002',
    aiLabel: 'AI \u6838\u5FC3\u80FD\u529B',
    aiTags: [
      { name: 'Agentic Workflow (LangGraph)', desc: '\u57FA\u4E8E LangGraph \u7684\u591A\u6B65\u9AA4 Agent \u7F16\u6392\uff0C\u652F\u6301\u4EFB\u52A1\u62C6\u89E3\u3001\u5DE5\u5177\u8C03\u7528\u4E0E\u72B6\u6001\u7BA1\u7406' },
      { name: 'Multi-Agent \u8DEF\u7531 (Manus)', desc: 'Manus \u98CE\u683C\u591A Agent \u534F\u4F5C\uff0C\u6309\u4EFB\u52A1\u7C7B\u578B\u667A\u80FD\u5206\u53D1\u7ED9\u4E13\u5C5E Agent \u5904\u7406' },
      { name: 'RAG + Vector Search', desc: '\u57FA\u4E8E ChromaDB / pgvector \u7684\u5411\u91CF\u68C0\u7D22\u589E\u5F3A\u751F\u6210\uff0C\u6784\u5EFA\u53EF\u8FFD\u6EAF\u79C1\u6709\u77E5\u8BC6\u5E93' },
      { name: 'MCP Protocol', desc: '\u901A\u8FC7 Model Context Protocol \u8FDE\u63A5\u90AE\u7BB1\u3001CRM\u3001\u6570\u636E\u5E93\u3001\u65E5\u5386\u7B49\u5916\u90E8\u7CFB\u7EDF' },
      { name: 'Ollama \u672C\u5730\u90E8\u7F72', desc: '\u652F\u6301 Ollama \u672C\u5730\u8FD0\u884C\u5F00\u6E90\u6A21\u578B\uff0C\u6570\u636E\u4E0D\u51FA\u5883\uff0C\u6EE1\u8DB3 GDPR \u5408\u89C4\u8981\u6C42' },
      { name: 'Multimodal OCR', desc: '\u7ED3\u5408 Tesseract + OpenCV + LLM \u7684\u591A\u6A21\u6001\u6587\u6863\u7406\u89E3\uff0C\u652F\u6301\u53D1\u7968\u3001\u5408\u540C\u3001\u8868\u683C\u63D0\u53D6' },
      { name: 'Agent Skills \u6280\u80FD\u7CFB\u7EDF', desc: '\u53EF\u63D2\u62D4\u7684 Agent \u6280\u80FD\u6A21\u5757\uff0C\u652F\u6301\u70ED\u52A0\u8F7D\u4E0E\u7EC4\u5408\u7F16\u6392\uff0C\u5FEB\u901F\u6269\u5C55\u80FD\u529B\u8FB9\u754C' },
      { name: 'Fine-Tuning / Online Learning', desc: '\u57FA\u4E8E\u7528\u6237\u53CD\u9988\u7684\u5728\u7EBF\u5B66\u4E60\u4E0E\u6A21\u578B\u5FAE\u8C03\uff0C\u6301\u7EED\u63D0\u5347\u5206\u7C7B\u4E0E\u63A8\u8350\u7CBE\u5EA6' },
      { name: 'Prompt Engineering', desc: '\u7CFB\u7EDF\u5316\u7684 Prompt \u8BBE\u8BA1\u4E0E\u7BA1\u7406\uff0C\u5305\u542B Chain-of-Thought\u3001Few-Shot \u7B49\u9AD8\u7EA7\u7B56\u7565' },
      { name: 'Guardrails & Eval', desc: '\u5185\u7F6E\u8F93\u51FA\u62A4\u680F\u3001\u5E7B\u89C9\u68C0\u6D4B\u4E0E\u81EA\u52A8\u5316\u8BC4\u6D4B\u6846\u67B6\uff0C\u4FDD\u969C\u751F\u4EA7\u73AF\u5883\u7A33\u5B9A\u6027' },
      { name: 'Human-in-the-Loop', desc: '\u5173\u952E\u6B65\u9AA4\u4EBA\u5DE5\u590D\u6838\u673A\u5236\uff0C\u786E\u4FDD\u91CD\u8981\u64CD\u4F5C\u7ECF\u8FC7\u786E\u8BA4\u518D\u6267\u884C' },
      { name: 'Voice Agent', desc: '\u652F\u6301\u8BED\u97F3\u5BF9\u8BDD\u3001\u7535\u8BDD\u63A5\u5F85\u4E0E\u8BED\u97F3\u6570\u636E\u5F55\u5165\uff0C\u6253\u901A\u591A\u6A21\u6001\u4EA4\u4E92' },
    ],
    engLabel: '\u5DE5\u7A0B\u6280\u672F\u6808',
    engTags: ['LangGraph', 'LangChain', 'Ollama', 'OpenAI', 'Groq', 'ChromaDB', 'pgvector', 'Tesseract', 'scikit-learn', 'Python', 'FastAPI', 'React', 'TypeScript', 'PostgreSQL', 'Redis', 'Docker', 'Kubernetes', 'Celery', 'MCP', 'Stripe'],
    contactTitle: '\u8BA9\u6211\u4EEC\u4E00\u8D77\u6784\u5EFA\u60A8\u7684 AI \u7CFB\u7EDF',
    contactDesc: '\u65E0\u8BBA\u662F\u4E2A\u4EBA AI \u52A9\u624B\u3001\u4F01\u4E1A\u667A\u80FD\u5DE5\u4F5C\u53F0\uFF0C\u8FD8\u662F\u884C\u4E1A\u89E3\u51B3\u65B9\u6848\uFF0C\u6211\u4EEC\u90FD\u53EF\u4EE5\u5E2E\u60A8\u5B9E\u73B0\u3002',
    formName: '\u60A8\u7684\u59D3\u540D',
    formEmail: '\u60A8\u7684\u90AE\u7BB1',
    formMessage: '\u8BF7\u63CF\u8FF0\u60A8\u7684\u9700\u6C42\u2026',
    formSubmit: '\u53D1\u9001\u6D88\u606F',
    formSending: '\u53D1\u9001\u4E2D\u2026',
    formSuccess: '\u6D88\u606F\u5DF2\u53D1\u9001\uFF0C\u6211\u4EEC\u4F1A\u5C3D\u5FEB\u56DE\u590D\u60A8\uFF01',
    formError: '\u53D1\u9001\u5931\u8D25\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5\u6216\u76F4\u63A5\u53D1\u90AE\u4EF6\u3002',
    legalLink: '\u6CD5\u5F8B\u58F0\u660E',
    privacyLink: '\u9690\u79C1\u653F\u7B56',
  },
  de: {
    badge: 'AI Agent \u00B7 Intelligente Automatisierung \u00B7 Individuelle Entwicklung',
    heroLine1: 'Wir entwickeln Ihr',
    heroLine2: 'massgeschneidertes AI-Arbeitssystem',
    heroSub: 'OOHK ist spezialisiert auf massgeschneiderte AI-Agenten, Wissensdatenbanken, Geschaeftsprozessautomatisierung und Systemintegration. Kurz gesagt: Wir bauen Ihnen ein AI-Arbeitssystem, das Fragen beantwortet, Daten organisiert und Aufgaben automatisch erledigt.',
    ctaContact: 'Kontakt aufnehmen',
    ctaProduct: 'Taxja ansehen \u2192',
    backToTaxja: '\u2190 Taxja',
    servicesKicker: 'Kernkompetenzen',
    servicesTitle: 'AI-L\u00F6sungen f\u00FCr reale Gesch\u00E4ftsprozesse',
    servicesDesc: 'Wir orientieren uns an Ihren Gesch\u00E4ftszielen und verbinden Modellf\u00E4higkeiten, Wissensbest\u00E4nde und bestehende Systeme zu einem lieferbaren, betreibbaren und iterativ verbesserbaren AI-Arbeitssystem.',
    services: [
      { title: 'Massgeschneiderte AI-Agent-Systeme', desc: 'Rund um Kundenservice, operative Zusammenarbeit, Steuerverarbeitung und interne Abl\u00E4ufe entwerfen wir ausf\u00FChrbare, verwaltbare AI-Agent-L\u00F6sungen.' },
      { title: 'Unternehmens-Wissensdatenbank & RAG', desc: 'Dokumente, Richtlinien, FAQs, Gesch\u00E4ftsmaterialien und historische Aufzeichnungen werden strukturiert aufbereitet \u2014 f\u00FCr eine durchsuchbare, nachvollziehbare und kontinuierlich aktualisierbare Wissensbasis.' },
      { title: 'Prozessautomatisierung & Aufgabenorchestrierung', desc: 'E-Mail, Formulare, Genehmigungen, Kundennachverfolgung und Datenverarbeitung werden zu vollst\u00E4ndigen Prozessketten verbunden \u2014 mit automatischer Ausl\u00F6sung und stabiler Ausf\u00FChrung.' },
      { title: 'Systemintegration & Anbindung', desc: 'CRM, ERP, Datenbanken, Tabellen, interne Plattformen und Drittanbieter-Services werden verbunden, damit AI wirklich in bestehende Gesch\u00E4ftsprozesse eingebettet wird.' },
      { title: 'L\u00F6sungsdesign & Umsetzungsberatung', desc: 'Von der Szenarioerkennung \u00FCber die Priorisierung bis zum Implementierungspfad \u2014 wir helfen Ihnen, AI-Projekte mit kontrollierbarem Aufwand zur Umsetzung zu bringen.' },
      { title: 'Massgeschneiderte Apps & AI-Arbeitspl\u00E4tze', desc: 'Wir liefern teamorientierte Web-Apps, interne Arbeitspl\u00E4tze und schlanke Tools \u2014 damit L\u00F6sungen nicht nur pr\u00E4sentierbar, sondern langfristig betreibbar sind.' },
    ],
    productsKicker: 'Produktportfolio',
    productsTitle: 'Live und in Entwicklung',
    productsDesc: 'Auf Basis unserer Technologie bauen wir replizierbare Branchenl\u00F6sungen.',
    products: [
      { icon: '\uD83E\uDDFE', name: 'Taxja', desc: 'AI-Steuerassistent f\u00FCr \u00F6sterreichische Steuerzahler. Automatische Belegerkennung, intelligente Transaktionsklassifizierung und Steuerberichte auf Knopfdruck.', status: 'live', statusLabel: 'Live' },
      { icon: '\uD83C\uDFE2', name: 'AI Enterprise Workspace', desc: 'Einheitlicher AI-Arbeitsplatz f\u00FCr KMUs \u2014 mit Dokumentenverarbeitung, Kundenverwaltung, Finanzanalyse und interner Wissensdatenbank.', status: 'dev', statusLabel: 'In Entwicklung' },
      { icon: '\uD83C\uDFAF', name: 'Branchenspezifische AI-L\u00F6sungen', desc: 'Aufbauend auf der Erfahrung aus Taxja und anderen Produkten entwickeln wir standardisierte AI-Toolkits f\u00FCr Gastronomie, E-Commerce, Freiberufler und weitere Branchen.', status: 'dev', statusLabel: 'Geplant' },
    ],
    aboutKicker: '\u00DCber uns',
    aboutTitle: 'OOHK',
    aboutDesc: 'OOHK hat seinen Sitz in \u00D6sterreich und verfolgt den Ansatz \u201EMassgeschneidert starten, modular aufbauen, kontinuierlich verbessern\u201C \u2014 f\u00FCr praxistaugliche, umsetzbare AI-L\u00F6sungen und Arbeitssysteme.',
    stats: [
      { value: '2026', label: 'Gr\u00FCndungsjahr' },
      { value: '\u00D6sterreich', label: 'Hauptsitz' },
      { value: 'AI-First', label: 'Technologie-Philosophie' },
      { value: 'DSGVO', label: 'Datenschutzkonformit\u00E4t' },
    ],
    techKicker: 'Technologie',
    techTitle: 'AI-F\u00E4higkeiten & Technische Architektur',
    techDesc: 'Diese F\u00E4higkeiten fliessen in unsere Produkte ein \u2014 z.B. Taxja, AI-Arbeitspl\u00E4tze, Dokumentenverarbeitungs-Tools und Branchenautomatisierungsl\u00F6sungen.',
    aiLabel: 'AI-Kernkompetenzen',
    aiTags: [
      { name: 'Agentic Workflow (LangGraph)', desc: 'Mehrstufige Agent-Orchestrierung mit LangGraph: Aufgabenzerlegung, Tool-Aufrufe und Zustandsverwaltung' },
      { name: 'Multi-Agent Routing (Manus)', desc: 'Manus-inspirierte Multi-Agent-Architektur mit intelligenter Aufgabenverteilung an spezialisierte Agenten' },
      { name: 'RAG + Vector Search', desc: 'Retrieval-Augmented Generation mit ChromaDB / pgvector f\u00FCr nachvollziehbare private Wissensdatenbanken' },
      { name: 'MCP Protocol', desc: 'Model Context Protocol f\u00FCr die Anbindung an E-Mail, CRM, Datenbanken, Kalender und externe Systeme' },
      { name: 'Ollama Lokale Bereitstellung', desc: 'Lokale Ausf\u00FChrung von Open-Source-Modellen mit Ollama \u2014 Daten bleiben im Haus, DSGVO-konform' },
      { name: 'Multimodal OCR', desc: 'Tesseract + OpenCV + LLM f\u00FCr multimodales Dokumentenverstehen: Rechnungen, Vertr\u00E4ge, Tabellen' },
      { name: 'Agent Skills System', desc: 'Modulare, hot-swappable Agent-F\u00E4higkeiten f\u00FCr flexible Erweiterung und schnelle Komposition' },
      { name: 'Fine-Tuning / Online Learning', desc: 'Kontinuierliches Lernen aus Nutzerfeedback und Modell-Feinabstimmung f\u00FCr h\u00F6here Klassifikations- und Empfehlungsgenauigkeit' },
      { name: 'Prompt Engineering', desc: 'Systematisches Prompt-Design und -Management mit Chain-of-Thought, Few-Shot und weiteren fortgeschrittenen Strategien' },
      { name: 'Guardrails & Eval', desc: 'Integrierte Output-Leitplanken, Halluzinationserkennung und automatisierte Evaluierungs-Frameworks f\u00FCr Produktionsstabilit\u00E4t' },
      { name: 'Human-in-the-Loop', desc: 'Menschliche \u00DCberpr\u00FCfung bei kritischen Schritten \u2014 wichtige Aktionen werden erst nach Best\u00E4tigung ausgef\u00FChrt' },
      { name: 'Voice Agent', desc: 'Sprachdialoge, Telefonannahme und gesprochene Dateneingabe f\u00FCr multimodale Interaktion' },
    ],
    engLabel: 'Engineering-Stack',
    engTags: ['LangGraph', 'LangChain', 'Ollama', 'OpenAI', 'Groq', 'ChromaDB', 'pgvector', 'Tesseract', 'scikit-learn', 'Python', 'FastAPI', 'React', 'TypeScript', 'PostgreSQL', 'Redis', 'Docker', 'Kubernetes', 'Celery', 'MCP', 'Stripe'],
    contactTitle: 'Lassen Sie uns gemeinsam Ihr AI-System bauen',
    contactDesc: 'Ob pers\u00F6nlicher AI-Assistent, intelligenter Unternehmens-Arbeitsplatz oder Branchenl\u00F6sung \u2014 wir k\u00F6nnen es f\u00FCr Sie umsetzen.',
    formName: 'Ihr Name',
    formEmail: 'Ihre E-Mail',
    formMessage: 'Beschreiben Sie Ihr Anliegen\u2026',
    formSubmit: 'Nachricht senden',
    formSending: 'Wird gesendet\u2026',
    formSuccess: 'Nachricht gesendet! Wir melden uns bald bei Ihnen.',
    formError: 'Senden fehlgeschlagen. Bitte versuchen Sie es erneut oder schreiben Sie uns direkt.',
    legalLink: 'Impressum',
    privacyLink: 'Datenschutz',
  },
  en: {
    badge: 'AI Agent \u00B7 Intelligent Automation \u00B7 Custom Development',
    heroLine1: 'We Build Your',
    heroLine2: 'Custom AI Work Systems',
    heroSub: 'OOHK specializes in custom AI agents, knowledge base construction, business process automation, and system integration. In short, we build AI work systems that answer questions, organize data, and get things done automatically.',
    ctaContact: 'Get In Touch',
    ctaProduct: 'See Taxja \u2192',
    backToTaxja: '\u2190 Taxja',
    servicesKicker: 'Core Capabilities',
    servicesTitle: 'AI Solutions for Real Business Needs',
    servicesDesc: 'We start from your business goals and integrate model capabilities, knowledge assets, and existing systems into deliverable, operable, and continuously improvable AI work systems.',
    services: [
      { title: 'Custom AI Agent Systems', desc: 'We design executable, manageable AI agent solutions around customer service, operational collaboration, tax processing, and internal workflows.' },
      { title: 'Enterprise Knowledge Base & RAG', desc: 'We structure documents, policies, FAQs, business materials, and historical records into a searchable, traceable, and continuously updatable knowledge foundation.' },
      { title: 'Process Automation & Task Orchestration', desc: 'We chain together email, forms, approvals, customer follow-ups, and data processing into complete workflows with automatic triggering and stable execution.' },
      { title: 'System Integration & Connectivity', desc: 'We connect CRM, ERP, databases, spreadsheets, internal platforms, and third-party services so AI truly enters your existing business processes.' },
      { title: 'Solution Design & Implementation Consulting', desc: 'From scenario identification and priority ranking to implementation path design, we help you advance AI projects with controllable investment.' },
      { title: 'Custom Apps & AI Workstations', desc: 'We deliver team-oriented web apps, internal workstations, and lightweight tools, ensuring solutions are not just presentable but sustainably operable.' },
    ],
    productsKicker: 'Product Portfolio',
    productsTitle: 'Live and In Development',
    productsDesc: 'Based on our technical capabilities, we are building replicable industry solutions.',
    products: [
      { icon: '\uD83E\uDDFE', name: 'Taxja', desc: 'AI tax assistant for Austrian individual taxpayers. Automatic receipt recognition, intelligent transaction classification, and one-click tax report generation.', status: 'live', statusLabel: 'Live' },
      { icon: '\uD83C\uDFE2', name: 'AI Enterprise Workspace', desc: 'A unified AI work hub for SMEs \u2014 integrating document processing, customer management, financial analysis, and internal knowledge Q&A.', status: 'dev', statusLabel: 'In Development' },
      { icon: '\uD83C\uDFAF', name: 'Industry AI Solutions', desc: 'Building on experience from Taxja and other products, we are expanding standardized AI toolkits for hospitality, e-commerce, freelancers, and more verticals.', status: 'dev', statusLabel: 'Planned' },
    ],
    aboutKicker: 'About Us',
    aboutTitle: 'OOHK',
    aboutDesc: 'Based in Austria, OOHK follows the approach of \u201Ccustom entry, modular accumulation, continuous iteration\u201D to build practical, implementable AI solutions and work systems.',
    stats: [
      { value: '2026', label: 'Founded' },
      { value: 'Austria', label: 'Headquarters' },
      { value: 'AI-First', label: 'Technology Philosophy' },
      { value: 'GDPR', label: 'Data Compliance' },
    ],
    techKicker: 'Technology',
    techTitle: 'AI Capabilities & Technical Architecture',
    techDesc: 'These capabilities are integrated into the products we are building \u2014 such as Taxja, AI workspaces, document processing tools, and industry automation solutions.',
    aiLabel: 'AI Core Capabilities',
    aiTags: [
      { name: 'Agentic Workflow (LangGraph)', desc: 'Multi-step agent orchestration with LangGraph: task decomposition, tool calling, and state management' },
      { name: 'Multi-Agent Routing (Manus)', desc: 'Manus-style multi-agent collaboration with intelligent task dispatch to specialized agents' },
      { name: 'RAG + Vector Search', desc: 'Retrieval-Augmented Generation with ChromaDB / pgvector for traceable private knowledge bases' },
      { name: 'MCP Protocol', desc: 'Model Context Protocol for connecting to email, CRM, databases, calendars, and external systems' },
      { name: 'Ollama Local Deployment', desc: 'Local execution of open-source models with Ollama \u2014 data stays on-site, GDPR-compliant' },
      { name: 'Multimodal OCR', desc: 'Tesseract + OpenCV + LLM for multimodal document understanding: invoices, contracts, table extraction' },
      { name: 'Agent Skills System', desc: 'Pluggable agent skill modules with hot-loading and composable orchestration for rapid capability expansion' },
      { name: 'Fine-Tuning / Online Learning', desc: 'Online learning and model fine-tuning based on user feedback for continuously improving classification and recommendation accuracy' },
      { name: 'Prompt Engineering', desc: 'Systematic prompt design and management including Chain-of-Thought, Few-Shot, and other advanced strategies' },
      { name: 'Guardrails & Eval', desc: 'Built-in output guardrails, hallucination detection, and automated evaluation frameworks for production stability' },
      { name: 'Human-in-the-Loop', desc: 'Human review at critical steps \u2014 important actions are confirmed before execution' },
      { name: 'Voice Agent', desc: 'Voice conversations, phone intake, and spoken data entry for multimodal interaction' },
    ],
    engLabel: 'Engineering Stack',
    engTags: ['LangGraph', 'LangChain', 'Ollama', 'OpenAI', 'Groq', 'ChromaDB', 'pgvector', 'Tesseract', 'scikit-learn', 'Python', 'FastAPI', 'React', 'TypeScript', 'PostgreSQL', 'Redis', 'Docker', 'Kubernetes', 'Celery', 'MCP', 'Stripe'],
    contactTitle: "Let's Build Your AI System Together",
    contactDesc: 'Whether it\u2019s a personal AI assistant, an enterprise intelligent workspace, or an industry solution \u2014 we can make it happen for you.',
    formName: 'Your Name',
    formEmail: 'Your Email',
    formMessage: 'Describe what you need\u2026',
    formSubmit: 'Send Message',
    formSending: 'Sending\u2026',
    formSuccess: 'Message sent! We\u2019ll get back to you soon.',
    formError: 'Failed to send. Please try again or email us directly.',
    legalLink: 'Legal Notice',
    privacyLink: 'Privacy Policy',
  },
};

export default CompanyPage;
