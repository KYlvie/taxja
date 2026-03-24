import { useEffect, useRef, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '../components/common/LanguageSwitcher';
import { useAuthStore } from '../stores/authStore';
import { normalizeLanguage, type SupportedLanguage } from '../utils/locale';
import './HomePage.css';

/* ── Types ── */
type Stat = { value: string; numericValue?: number; suffix?: string; prefix?: string; label: string };
type Feature = { icon: string; title: string; desc: string };
type Step = { num: string; title: string; desc: string };
type Faq = { q: string; a: string };
type ShowcaseReport = {
  id: string; icon: string; title: string; tag?: string;
  headers?: string[]; rows: string[][]; summary?: { label: string; value: string; accent?: boolean }[];
};

interface Copy {
  badge: string; h1: string; h1Highlights: string[]; subtitle: string;
  loginLabel: string; ctaPrimary: string; ctaSecondary: string;
  stats: Stat[]; trustBadges: string[];
  showLabel: string; showTitle: string; showDesc: string; showcaseReports: ShowcaseReport[];
  featKicker: string; featTitle: string; features: Feature[];
  howKicker: string; howTitle: string; steps: Step[];
  faqKicker: string; faqTitle: string; faqs: Faq[];
  ctaKicker: string; ctaTitle: string; ctaBody: string;
  dlTitle: string; dlDesc: string; dlScanHint: string;
  dlApple: string; dlGoogle: string; dlPwa: string;
  oohkBridgeTag: string; oohkBridgeText: string;
}

/* ── Light flowing particles background ── */
const LightParticles = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouse = useRef({ x: -1000, y: -1000, active: false });
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;
    let w = 0, h = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    const onMove = (e: MouseEvent) => { mouse.current.x = e.clientX; mouse.current.y = e.clientY; mouse.current.active = true; };
    const onLeave = () => { mouse.current.active = false; };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseleave', onLeave);

    /* Particles */
    const count = 120;
    const pts: { x: number; y: number; vx: number; vy: number; ox: number; oy: number; r: number; hue: number; baseAlpha: number }[] = [];
    for (let i = 0; i < count; i++) {
      const x = Math.random() * 3000;
      const y = Math.random() * 3000;
      pts.push({
        x, y, ox: 0, oy: 0,
        vx: (Math.random() - 0.5) * 0.8,
        vy: (Math.random() - 0.5) * 0.6 - 0.2,
        r: 2 + Math.random() * 5,
        hue: 220 + Math.random() * 50,
        baseAlpha: 0.12 + Math.random() * 0.25,
      });
    }

    /* Mouse trail sparks */
    const sparks: { x: number; y: number; vx: number; vy: number; life: number; maxLife: number; hue: number; r: number }[] = [];

    /* Large flowing gradient blobs */
    const blobs = [
      { x: 0.15, y: 0.2, r: 500, hue: 240, speed: 0.0004, phase: 0, alpha: 0.14 },
      { x: 0.75, y: 0.4, r: 450, hue: 195, speed: 0.0005, phase: 2, alpha: 0.12 },
      { x: 0.4, y: 0.75, r: 480, hue: 265, speed: 0.00035, phase: 4, alpha: 0.13 },
      { x: 0.6, y: 0.15, r: 350, hue: 175, speed: 0.00045, phase: 1, alpha: 0.1 },
      { x: 0.3, y: 0.5, r: 400, hue: 230, speed: 0.0003, phase: 5, alpha: 0.11 },
    ];

    /* Flowing wave lines */
    const waves = [
      { y: 0.3, amp: 60, freq: 0.003, speed: 0.0008, hue: 235, alpha: 0.06 },
      { y: 0.5, amp: 45, freq: 0.004, speed: 0.001, hue: 200, alpha: 0.05 },
      { y: 0.7, amp: 55, freq: 0.0025, speed: 0.0006, hue: 260, alpha: 0.05 },
    ];

    let time = 0;
    let lastMx = -1000, lastMy = -1000;
    const draw = () => {
      time += 16;
      ctx.clearRect(0, 0, w, h);
      const mx = mouse.current.x, my = mouse.current.y;
      const mActive = mouse.current.active;
      const mouseRadius = 180;

      /* Spawn sparks on mouse move */
      if (mActive) {
        const dx = mx - lastMx, dy = my - lastMy;
        const speed = Math.sqrt(dx * dx + dy * dy);
        if (speed > 2) {
          const spawnCount = Math.min(Math.floor(speed / 4), 5);
          for (let i = 0; i < spawnCount; i++) {
            sparks.push({
              x: mx + (Math.random() - 0.5) * 10,
              y: my + (Math.random() - 0.5) * 10,
              vx: (Math.random() - 0.5) * 2 + dx * 0.05,
              vy: (Math.random() - 0.5) * 2 + dy * 0.05,
              life: 1, maxLife: 40 + Math.random() * 30,
              hue: 220 + Math.random() * 50,
              r: 1.5 + Math.random() * 3,
            });
          }
        }
        lastMx = mx; lastMy = my;
      }

      /* Flowing blobs */
      for (const b of blobs) {
        const bx = (b.x + Math.sin(time * b.speed + b.phase) * 0.2) * w;
        const by = (b.y + Math.cos(time * b.speed * 0.7 + b.phase) * 0.15) * h;
        const pulseR = b.r * (1 + Math.sin(time * 0.001 + b.phase) * 0.15);
        const g = ctx.createRadialGradient(bx, by, 0, bx, by, pulseR);
        g.addColorStop(0, `hsla(${b.hue}, 65%, 72%, ${b.alpha})`);
        g.addColorStop(0.4, `hsla(${b.hue}, 55%, 68%, ${b.alpha * 0.5})`);
        g.addColorStop(1, 'transparent');
        ctx.fillStyle = g;
        ctx.fillRect(bx - pulseR, by - pulseR, pulseR * 2, pulseR * 2);
      }

      /* Mouse glow */
      if (mActive) {
        const mg = ctx.createRadialGradient(mx, my, 0, mx, my, mouseRadius);
        mg.addColorStop(0, 'hsla(235, 65%, 70%, 0.12)');
        mg.addColorStop(0.3, 'hsla(210, 60%, 70%, 0.06)');
        mg.addColorStop(1, 'transparent');
        ctx.fillStyle = mg;
        ctx.beginPath();
        ctx.arc(mx, my, mouseRadius, 0, Math.PI * 2);
        ctx.fill();

        /* Pulse ring */
        const ringPhase = (time * 0.003) % 1;
        const ringR = mouseRadius * 0.3 + ringPhase * mouseRadius * 0.7;
        ctx.beginPath();
        ctx.arc(mx, my, ringR, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(235, 55%, 65%, ${0.15 * (1 - ringPhase)})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      /* Flowing wave lines */
      for (const wave of waves) {
        ctx.beginPath();
        const baseY = wave.y * h;
        for (let x = 0; x <= w; x += 4) {
          const y = baseY + Math.sin(x * wave.freq + time * wave.speed) * wave.amp
                          + Math.sin(x * wave.freq * 1.5 + time * wave.speed * 0.7) * wave.amp * 0.4;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = `hsla(${wave.hue}, 55%, 65%, ${wave.alpha})`;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      /* Particles with mouse interaction */
      for (const p of pts) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < -20) p.x = w + 20;
        if (p.x > w + 20) p.x = -20;
        if (p.y < -20) p.y = h + 20;
        if (p.y > h + 20) p.y = -20;

        /* Mouse attraction / repulsion */
        if (mActive) {
          const dx = mx - p.x, dy = my - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < mouseRadius && dist > 1) {
            const force = (1 - dist / mouseRadius) * 0.8;
            p.ox += (dx / dist) * force;
            p.oy += (dy / dist) * force;
          }
        }
        p.ox *= 0.92;
        p.oy *= 0.92;

        const px = p.x + p.ox;
        const py = p.y + p.oy;

        const pulse = 1 + Math.sin(time * 0.003 + p.x * 0.008 + p.y * 0.005) * 0.5;
        const sz = p.r * pulse;

        /* Proximity to mouse boosts alpha */
        let alphaBoost = 1;
        if (mActive) {
          const dx = mx - px, dy = my - py;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < mouseRadius) alphaBoost = 1 + (1 - dist / mouseRadius) * 1.5;
        }

        ctx.beginPath();
        ctx.arc(px, py, sz, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 60%, 65%, ${Math.min(p.baseAlpha * pulse * alphaBoost, 0.7)})`;
        ctx.fill();

        if (p.r > 3.5) {
          ctx.beginPath();
          ctx.arc(px, py, sz * 2.5, 0, Math.PI * 2);
          ctx.fillStyle = `hsla(${p.hue}, 55%, 65%, ${p.baseAlpha * 0.15 * pulse * alphaBoost})`;
          ctx.fill();
        }
      }

      /* Connection lines */
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const ax = pts[i].x + pts[i].ox, ay = pts[i].y + pts[i].oy;
          const bx = pts[j].x + pts[j].ox, by = pts[j].y + pts[j].oy;
          const dx = ax - bx, dy = ay - by;
          const dist = dx * dx + dy * dy;
          if (dist < 25000) {
            let a = (1 - dist / 25000) * 0.08;
            /* Boost lines near mouse */
            if (mActive) {
              const midX = (ax + bx) / 2, midY = (ay + by) / 2;
              const mdx = mx - midX, mdy = my - midY;
              const mDist = Math.sqrt(mdx * mdx + mdy * mdy);
              if (mDist < mouseRadius) a += (1 - mDist / mouseRadius) * 0.12;
            }
            ctx.beginPath();
            ctx.moveTo(ax, ay);
            ctx.lineTo(bx, by);
            ctx.strokeStyle = `hsla(235, 55%, 65%, ${a})`;
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      }

      /* Mouse trail sparks */
      for (let i = sparks.length - 1; i >= 0; i--) {
        const s = sparks[i];
        s.x += s.vx;
        s.y += s.vy;
        s.vx *= 0.96;
        s.vy *= 0.96;
        s.life++;
        const progress = s.life / s.maxLife;
        if (progress >= 1) { sparks.splice(i, 1); continue; }
        const alpha = (1 - progress) * 0.5;
        const sz = s.r * (1 - progress * 0.5);
        ctx.beginPath();
        ctx.arc(s.x, s.y, sz, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${s.hue}, 60%, 68%, ${alpha})`;
        ctx.fill();
      }

      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseleave', onLeave);
    };
  }, []);
  return <canvas ref={canvasRef} className="hp-particles" />;
};

/* ── OOHK Large Orbital Display (light-theme, with satellite rings) ── */
const OohkOrbLarge = ({ size = 280 }: { size?: number }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hover = useRef(false);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;
    let time = 0;
    const dpr = window.devicePixelRatio || 1;
    const s = size * dpr;
    canvas.width = s; canvas.height = s;
    const cx = s / 2, cy = s / 2;
    const hue = 240;

    /* 3 orbital rings with satellites */
    const rings = [
      { r: s * 0.18, count: 6, speed: 0.35, dotSz: 2.5, hOff: 0 },
      { r: s * 0.28, count: 8, speed: -0.22, dotSz: 2, hOff: 20 },
      { r: s * 0.38, count: 10, speed: 0.15, dotSz: 1.5, hOff: 40 },
    ];
    const sats: { angle: number; ringIdx: number; sz: number; hOff: number; speedMul: number }[] = [];
    rings.forEach((ring, ri) => {
      for (let i = 0; i < ring.count; i++) {
        sats.push({
          angle: (Math.PI * 2 / ring.count) * i + Math.random() * 0.3,
          ringIdx: ri,
          sz: ring.dotSz * (0.7 + Math.random() * 0.6),
          hOff: ring.hOff + Math.random() * 15 - 7,
          speedMul: 0.8 + Math.random() * 0.4,
        });
      }
    });

    const draw = () => {
      time += 0.016;
      ctx.clearRect(0, 0, s, s);
      const sm = hover.current ? 1.6 : 1;
      const gm = hover.current ? 1.4 : 1;

      /* Outer glow */
      const og = ctx.createRadialGradient(cx, cy, s * 0.05, cx, cy, s * 0.45);
      og.addColorStop(0, `hsla(${hue}, 50%, 60%, ${0.06 * gm})`);
      og.addColorStop(0.5, `hsla(${hue + 30}, 45%, 55%, ${0.03 * gm})`);
      og.addColorStop(1, 'transparent');
      ctx.fillStyle = og;
      ctx.fillRect(0, 0, s, s);

      /* Ring tracks */
      for (const ring of rings) {
        ctx.beginPath();
        ctx.arc(cx, cy, ring.r, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(${hue + ring.hOff}, 45%, 55%, ${0.08 * gm})`;
        ctx.lineWidth = 1 * dpr;
        ctx.stroke();
      }

      /* Animated ring arcs */
      rings.forEach((ring, ri) => {
        for (let a = 0; a < 2; a++) {
          const sa = time * ring.speed * sm * (a === 0 ? 1 : -0.7) + ri * 1.5 + a * Math.PI;
          ctx.beginPath();
          ctx.arc(cx, cy, ring.r, sa, sa + 0.8 + ri * 0.2);
          ctx.strokeStyle = `hsla(${hue + ring.hOff + a * 15}, 50%, 55%, ${(0.35 + ri * 0.05) * gm})`;
          ctx.lineWidth = 1.5 * dpr;
          ctx.shadowBlur = 6 * gm * dpr;
          ctx.shadowColor = `hsla(${hue + ring.hOff}, 45%, 50%, 0.2)`;
          ctx.stroke();
          ctx.shadowBlur = 0;
        }
      });

      /* Satellites */
      for (const sat of sats) {
        const ring = rings[sat.ringIdx];
        sat.angle += ring.speed * sat.speedMul * 0.016 * sm;
        const px = cx + Math.cos(sat.angle) * ring.r;
        const py = cy + Math.sin(sat.angle) * ring.r;
        const pulse = 1 + Math.sin(time * 2.5 + sat.angle * 2) * 0.3;
        const sz = sat.sz * pulse * dpr;

        /* Trail */
        const trailLen = 4;
        for (let t = trailLen; t > 0; t--) {
          const ta = sat.angle - ring.speed * sat.speedMul * 0.016 * sm * t * 3;
          const tx = cx + Math.cos(ta) * ring.r;
          const ty = cy + Math.sin(ta) * ring.r;
          ctx.beginPath();
          ctx.arc(tx, ty, sz * (0.3 + 0.15 * (trailLen - t)), 0, Math.PI * 2);
          ctx.fillStyle = `hsla(${hue + sat.hOff}, 50%, 55%, ${0.08 * (trailLen - t) / trailLen * gm})`;
          ctx.fill();
        }

        ctx.beginPath();
        ctx.arc(px, py, sz, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${hue + sat.hOff}, 50%, 60%, ${0.55 * gm})`;
        ctx.shadowBlur = 4 * gm * dpr;
        ctx.shadowColor = `hsla(${hue + sat.hOff}, 50%, 55%, 0.3)`;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      /* Inner rings (close to core) */
      for (let a = 0; a < 3; a++) {
        const ir = s * 0.09;
        const sa = time * (0.5 + a * 0.15) * sm + a * 2.1;
        ctx.beginPath();
        ctx.arc(cx, cy, ir, sa, sa + 0.9);
        ctx.strokeStyle = `hsla(${hue + a * 25}, 55%, 55%, ${0.5 * gm})`;
        ctx.lineWidth = 2 * dpr;
        ctx.shadowBlur = 8 * gm * dpr;
        ctx.shadowColor = `hsla(${hue + a * 25}, 50%, 50%, 0.25)`;
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      /* Core glow */
      const coreR = s * 0.04;
      const cg = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 2.5 * gm);
      cg.addColorStop(0, `hsla(${hue}, 55%, 65%, ${0.5 * gm})`);
      cg.addColorStop(0.5, `hsla(${hue + 20}, 50%, 55%, ${0.15 * gm})`);
      cg.addColorStop(1, 'transparent');
      ctx.beginPath();
      ctx.arc(cx, cy, coreR * 2.5 * gm, 0, Math.PI * 2);
      ctx.fillStyle = cg;
      ctx.fill();

      /* Core dot */
      const cp = 1 + Math.sin(time * 2) * 0.3;
      ctx.beginPath();
      ctx.arc(cx, cy, coreR * cp, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${hue}, 50%, 70%, ${0.6 * gm})`;
      ctx.fill();

      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animId);
  }, [size]);
  return (
    <canvas ref={canvasRef}
      style={{ width: size, height: size, cursor: 'pointer' }}
      onMouseEnter={() => { hover.current = true; }}
      onMouseLeave={() => { hover.current = false; }} />
  );
};

/* ── OOHK Orbital Spinner (light-theme adapted) ── */
const OohkOrb = ({ size = 48 }: { size?: number }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hover = useRef(false);
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
    const hue = 240;
    const orbs: { angle: number; r: number; speed: number; sz: number; hOff: number }[] = [];
    for (let i = 0; i < 12; i++) {
      orbs.push({ angle: Math.random() * Math.PI * 2, r: 10 + Math.random() * 14, speed: (0.4 + Math.random() * 0.5) * (Math.random() > 0.5 ? 1 : -1), sz: 0.8 + Math.random() * 1.2, hOff: Math.random() * 30 - 15 });
    }
    const draw = () => {
      time += 0.016;
      ctx.clearRect(0, 0, s, s);
      const sm = hover.current ? 2.2 : 1;
      const gm = hover.current ? 1.5 : 1;
      ctx.beginPath(); ctx.arc(cx, cy, 22, 0, Math.PI * 2);
      ctx.strokeStyle = `hsla(${hue}, 50%, 55%, ${0.15 * gm})`; ctx.lineWidth = 1; ctx.stroke();
      for (let a = 0; a < 3; a++) {
        const sa = time * (0.6 + a * 0.2) * sm + a * 2.1;
        ctx.beginPath(); ctx.arc(cx, cy, 22, sa, sa + 0.7);
        ctx.strokeStyle = `hsla(${hue + a * 25}, 55%, 55%, ${0.7 * gm})`;
        ctx.lineWidth = 1.5; ctx.shadowBlur = 5 * gm;
        ctx.shadowColor = `hsla(${hue + a * 25}, 50%, 50%, 0.35)`;
        ctx.stroke(); ctx.shadowBlur = 0;
      }
      ctx.beginPath(); ctx.arc(cx, cy, 14, 0, Math.PI * 2);
      ctx.strokeStyle = `hsla(${hue + 40}, 45%, 55%, ${0.12 * gm})`; ctx.lineWidth = 1; ctx.stroke();
      for (let a = 0; a < 2; a++) {
        const sa = -time * (0.5 + a * 0.3) * sm + a * 3;
        ctx.beginPath(); ctx.arc(cx, cy, 14, sa, sa + 1);
        ctx.strokeStyle = `hsla(${hue + 60 + a * 25}, 50%, 55%, ${0.5 * gm})`;
        ctx.lineWidth = 1.5; ctx.shadowBlur = 4 * gm;
        ctx.shadowColor = `hsla(${hue + 60}, 45%, 50%, 0.25)`;
        ctx.stroke(); ctx.shadowBlur = 0;
      }
      for (const o of orbs) {
        o.angle += o.speed * 0.016 * sm;
        const px = cx + Math.cos(o.angle) * o.r;
        const py = cy + Math.sin(o.angle) * o.r;
        const pulse = 1 + Math.sin(time * 3 + o.angle) * 0.3;
        ctx.beginPath(); ctx.arc(px, py, o.sz * pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${hue + o.hOff}, 50%, 55%, ${0.5 * gm})`;
        ctx.fill();
      }
      const pr = 3 + Math.sin(time * 2) * 1.5;
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, pr * gm);
      g.addColorStop(0, `hsla(${hue}, 50%, 65%, ${0.4 * gm})`);
      g.addColorStop(1, `hsla(${hue}, 45%, 55%, 0)`);
      ctx.beginPath(); ctx.arc(cx, cy, pr * gm, 0, Math.PI * 2);
      ctx.fillStyle = g; ctx.fill();
      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animId);
  }, [size]);
  return (
    <canvas ref={canvasRef} style={{ width: size, height: size, cursor: 'pointer' }}
      onMouseEnter={() => { hover.current = true; }} onMouseLeave={() => { hover.current = false; }} />
  );
};

/* ── HUD-style SVG Icons ── */
const HudIcons: Record<string, JSX.Element> = {
  scan: <svg viewBox="0 0 24 24"><path d="M3 7V5a2 2 0 012-2h2M17 3h2a2 2 0 012 2v2M21 17v2a2 2 0 01-2 2h-2M7 21H5a2 2 0 01-2-2v-2" strokeLinecap="round"/><path d="M7 12h10M12 7v10" strokeLinecap="round" strokeDasharray="2 2"/></svg>,
  doc: <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" strokeLinecap="round"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="13" y2="17"/></svg>,
  chart: <svg viewBox="0 0 24 24"><path d="M18 20V10M12 20V4M6 20v-6" strokeLinecap="round"/></svg>,
  shield: <svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4" strokeLinecap="round"/></svg>,
  brain: <svg viewBox="0 0 24 24"><path d="M12 2a7 7 0 017 7c0 2.5-1.3 4.7-3.2 6L12 20l-3.8-5C6.3 13.7 5 11.5 5 9a7 7 0 017-7z"/><circle cx="12" cy="9" r="2"/><path d="M12 2v3M8.5 3.5l1.5 2.5M15.5 3.5l-1.5 2.5" strokeLinecap="round"/></svg>,
  building: <svg viewBox="0 0 24 24"><path d="M3 21h18M5 21V7l7-4 7 4v14" strokeLinecap="round"/><path d="M9 21v-4h6v4M9 9h.01M15 9h.01M9 13h.01M15 13h.01" strokeLinecap="round"/></svg>,
  repeat: <svg viewBox="0 0 24 24"><polyline points="17 1 21 5 17 9" strokeLinecap="round"/><path d="M3 11V9a4 4 0 014-4h14" strokeLinecap="round"/><polyline points="7 23 3 19 7 15" strokeLinecap="round"/><path d="M21 13v2a4 4 0 01-4 4H3" strokeLinecap="round"/></svg>,
  credit: <svg viewBox="0 0 24 24"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>,
  chat: <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" strokeLinecap="round"/><path d="M8 9h8M8 13h4" strokeLinecap="round"/></svg>,
  health: <svg viewBox="0 0 24 24"><path d="M22 12h-4l-3 9L9 3l-3 9H2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  export: <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" strokeLinecap="round"/><polyline points="7 10 12 15 17 10" strokeLinecap="round"/><line x1="12" y1="15" x2="12" y2="3" strokeLinecap="round"/></svg>,
  globe: <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>,
};

/* ── i18n copy — updated to reflect actual system capabilities ── */
const enShowcaseReports: ShowcaseReport[] = [
      { id: 'ea', icon: '📊', title: 'Income-Expense Statement 2025',
        headers: ['Date', 'Description', 'Amount', '✓'],
        rows: [['15.01', 'Salary January', '€ 3,200.00', ''], ['10.03', 'Freelance Web Design', '€ 1,800.00', ''], ['22.04', 'Rental Income Q1', '€ 2,700.00', ''], ['05.01', 'Home Office Allowance', '- € 300.00', '✓'], ['12.01', 'Laptop (Work Equipment)', '- € 1,299.00', '✓'], ['01.04', 'Restaurant (private)', '- € 45.00', '✗']],
        summary: [{ label: 'Income', value: '€ 17,300.00' }, { label: 'Expenses', value: '- € 3,069.90' }, { label: 'Net Result', value: '€ 14,230.10', accent: true }],
      },
      { id: 'e1', icon: '🏛️', title: 'E1 Tax Return 2025',
        headers: ['KZ', 'Field', 'Amount'],
        rows: [['245', 'Employment Income', '€ 45,000.00'], ['320', 'Business Income', '€ 28,650.00'], ['370', 'Rental Income', '€ 8,400.00'], ['717', 'Commuter Allowance', '- € 1,356.00'], ['718', 'Home Office Allowance', '- € 300.00']],
        summary: [{ label: 'Total Income', value: '€ 82,050.00' }, { label: 'Taxable Income', value: '€ 77,474.00', accent: true }],
      },
      { id: 'e1a', icon: '📝', title: 'E1a Supplement 2025',
        headers: ['KZ', 'Field', 'Amount'],
        rows: [['9040', 'Business Revenue', '€ 92,400.00'], ['9050', 'Cost of Goods', '- € 12,300.00'], ['9060', 'Personnel Costs', '- € 38,500.00'], ['9070', 'Depreciation', '- € 4,200.00'], ['9080', 'Operating Expenses', '- € 8,750.00']],
        summary: [{ label: 'Profit/Loss', value: '€ 28,650.00', accent: true }],
      },
      { id: 'e1b', icon: '🏠', title: 'E1b Rental Income 2025',
        headers: ['KZ', 'Field', 'Amount'],
        rows: [['400', 'Rental Income', '€ 14,400.00'], ['410', 'Operating Cost Share', '€ 2,160.00'], ['450', 'Building Depreciation (1.5%)', '- € 3,000.00'], ['460', 'Maintenance', '- € 1,850.00'], ['470', 'Loan Interest', '- € 2,400.00']],
        summary: [{ label: 'Rental Income (net)', value: '€ 9,310.00', accent: true }],
      },
      { id: 'l1', icon: '👤', title: 'L1 Employee Tax Return 2025',
        headers: ['KZ', 'Field', 'Amount'],
        rows: [['210', 'Gross Salary (per L16)', '€ 45,000.00'], ['220', 'Social Insurance', '- € 8,145.00'], ['717', 'Commuter Allowance', '- € 1,356.00'], ['718', 'Home Office Allowance', '- € 300.00']],
        summary: [{ label: 'Tax Base', value: '€ 34,659.00' }, { label: 'Refund', value: '€ 1,247.00', accent: true }],
      },
      { id: 'u1', icon: '📅', title: 'U1 Annual VAT Return 2025',
        headers: ['KZ', 'Position', 'Amount'],
        rows: [['000', 'Total Supplies', '€ 92,400.00'], ['029', 'Tax Base 20%', '€ 92,400.00'], ['060', 'VAT 20%', '€ 18,480.00'], ['065', 'Input VAT', '- € 7,360.00']],
        summary: [{ label: 'Annual VAT Payable', value: '€ 11,120.00', accent: true }],
      },
      { id: 'afa', icon: '🏗️', title: 'Asset Register 2025',
        headers: ['Asset', 'Cost', 'Depr. p.a.', 'Book Value'],
        rows: [['MacBook Pro 16"', '€ 2,999.00', '€ 999.67', '€ 1,000.00'], ['Office Furniture', '€ 1,800.00', '€ 138.46', '€ 1,384.62'], ['Building (Rental)', '€ 200,000.00', '€ 3,000.00', '€ 182,000.00']],
        summary: [{ label: 'Total Depreciation', value: '€ 9,713.13' }, { label: 'Total Book Value', value: '€ 207,459.62', accent: true }],
      },
    ];

const copy: Partial<Record<SupportedLanguage, Copy>> = {
  de: {
    badge: 'Steuer-KI für Österreich',
    h1: 'Beleg rein.\nSteuererklärung raus.',
    h1Highlights: ['KI-gestützt.', 'In Minuten.', 'Stressfrei.'],
    subtitle: 'Taxja verwandelt deine Belege in fertige Steuerformulare — vollautomatisch, transparent und nach österreichischem Recht.',
    loginLabel: 'Anmelden',
    ctaPrimary: 'Kostenlos starten',
    ctaSecondary: 'Preise ansehen',
    stats: [
      { value: '9', numericValue: 9, label: 'Sprachen' },
      { value: '<5 Min', numericValue: 5, prefix: '<', suffix: ' Min', label: 'bis zum Überblick' },
      { value: '2022–2026', label: 'Steuerjahre' },
      { value: 'AES-256', label: 'Verschlüsselung' },
    ],
    trustBadges: ['DSGVO', 'AES-256', 'EU-Hosting', 'FinanzOnline'],
    showLabel: 'Live-Vorschau',
    showTitle: 'Deine Steuerberichte — automatisch generiert',
    showDesc: 'E/A-Rechnung, GuV, E1/E1a/E1b, L1/L1k, K1, U1, UVA, Saldenliste, Anlageverzeichnis — alles auf Knopfdruck.',
    showcaseReports: enShowcaseReports,
    featKicker: 'Funktionen',
    featTitle: 'Alles was du für deine Steuer brauchst.',
    features: [
      { icon: 'doc', title: 'Beleg erkennen', desc: 'Foto oder PDF — Taxja erkennt Typ, Betrag und Kategorie automatisch.' },
      { icon: 'brain', title: 'Steuerlich bewerten', desc: 'Absetzbar? Welches Formular? Taxja entscheidet nach geltendem Recht.' },
      { icon: 'building', title: 'Formulare ausfüllen', desc: 'E1, E1a, E1b, L1, U1 — automatisch ausgefüllt für FinanzOnline.' },
      { icon: 'repeat', title: 'Lücken aufzeigen', desc: 'Fehlende Belege, offene Fristen und Risiken — bevor das Finanzamt es merkt.' },
      { icon: 'chat', title: 'Alle Einkunftsarten', desc: 'Gehalt, Vermietung, Gewerbe, Freiberuf — sauber getrennt.' },
      { icon: 'health', title: 'Aktuelles Recht', desc: 'Tarife, Pauschalen, AfA, SVS, USt — Stand 2022–2026.' },
    ],
    howKicker: 'So funktioniert es',
    howTitle: 'Drei Schritte. Das wars.',
    steps: [
      { num: '01', title: 'Konto erstellen', desc: 'Kostenlos registrieren, Profil einrichten und erste Belege hochladen.' },
      { num: '02', title: 'KI analysiert', desc: 'Dokumente erkennen, Transaktionen klassifizieren, Absetzbeträge berechnen — alles automatisch.' },
      { num: '03', title: 'Exportieren', desc: 'Steuerberichte prüfen und für FinanzOnline oder deinen Steuerberater exportieren.' },
    ],
    faqKicker: 'FAQ',
    faqTitle: 'Häufig gestellte Fragen.',
    faqs: [
      { q: 'Brauche ich Steuerwissen?', a: 'Nein. Taxja erklärt jeden Schritt, schlägt Absetzbeträge vor und prüft deine Daten automatisch mit dem Steuer-Gesundheitscheck.' },
      { q: 'Nur für Angestellte?', a: 'Nein — Arbeitnehmer, Selbständige, Freiberufler und Vermieter werden unterstützt. GmbH-Unterstützung (K1) ist in Planung.' },
      { q: 'Welche Dokumente werden erkannt?', a: 'Über 15 Typen: Lohnzettel, L1, E1, E1a, E1b, E1kv, Kontoauszüge, Grundsteuer, SVS, Jahresabschluss, U1, UVA, Kaufverträge, Mietverträge und mehr.' },
      { q: 'Wie sicher sind meine Daten?', a: 'AES-256 Verschlüsselung, DSGVO-konform, alle Daten in der EU. Keine Tracking-Cookies.' },
    ],
    ctaKicker: 'Bereit?',
    ctaTitle: 'Schluss mit Belegsortieren.',
    ctaBody: 'Hochladen, fertig. Taxja macht den Rest.',
    dlTitle: 'Taxja auch unterwegs nutzen',
    dlDesc: 'Belege fotografieren, Ausgaben erfassen und Steuerstatus prüfen — direkt auf dem Handy.',
    dlScanHint: 'QR-Code scannen zum Herunterladen',
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: 'Web-App öffnen',
    oohkBridgeTag: 'Taxja by OOHK',
    oohkBridgeText: 'Taxja ist ein von OOHK entwickeltes AI-Steuerprodukt und unser Flaggschiff für den österreichischen Steuermarkt.',
  },
  en: {
    badge: 'AI tax engine for Austria',
    h1: 'Drop your receipts.\nGet your tax return.',
    h1Highlights: ['AI-powered.', 'In minutes.', 'Stress-free.'],
    subtitle: 'Taxja turns your documents into completed Austrian tax forms — fully automated, explainable, and legally compliant.',
    loginLabel: 'Sign in',
    ctaPrimary: 'Start Free',
    ctaSecondary: 'See Pricing',
    stats: [
      { value: '9', numericValue: 9, label: 'languages' },
      { value: '<5 min', numericValue: 5, prefix: '<', suffix: ' min', label: 'to first overview' },
      { value: '2022–2026', label: 'tax years' },
      { value: 'AES-256', label: 'encryption' },
    ],
    trustBadges: ['GDPR', 'AES-256', 'EU-Hosted', 'FinanzOnline'],
    showLabel: 'Live Preview',
    showTitle: 'Your tax reports — auto-generated',
    showDesc: 'EA, P&L, E1/E1a/E1b, L1/L1k, K1, U1, VAT, trial balance, asset register — all at the click of a button.',
    showcaseReports: enShowcaseReports,
    featKicker: 'Features',
    featTitle: 'Everything you need for your taxes.',
    features: [
      { icon: 'doc', title: 'Instant recognition', desc: 'Photo or PDF — Taxja identifies type, amount and category automatically.' },
      { icon: 'brain', title: 'Tax intelligence', desc: 'Deductible? Which form? Taxja applies Austrian tax law and explains every decision.' },
      { icon: 'building', title: 'Forms, filled', desc: 'E1, E1a, E1b, L1, U1 — auto-completed and export-ready for FinanzOnline.' },
      { icon: 'repeat', title: 'Gap detection', desc: 'Missing receipts, upcoming deadlines, tax risks — flagged before the tax office does.' },
      { icon: 'chat', title: 'Every income type', desc: 'Salary, rental, business, freelance — separated cleanly with the right rules.' },
      { icon: 'health', title: 'Current law built in', desc: 'Rates, allowances, depreciation, SVS, VAT — all up to date for 2022–2026.' },
    ],
    howKicker: 'How it works',
    howTitle: 'Three steps. That\'s it.',
    steps: [
      { num: '01', title: 'Create account', desc: 'Sign up free, set up your profile and upload your first documents.' },
      { num: '02', title: 'AI analyzes', desc: 'Recognize documents, classify transactions, calculate deductions — all automatic.' },
      { num: '03', title: 'Export', desc: 'Review tax reports and export for FinanzOnline or your tax advisor.' },
    ],
    faqKicker: 'FAQ',
    faqTitle: 'Frequently asked questions.',
    faqs: [
      { q: 'Do I need tax knowledge?', a: 'No. Taxja explains every step, suggests deductions and automatically checks your data with the Tax Health Check.' },
      { q: 'Only for employees?', a: 'No — employees, self-employed, freelancers and landlords are all supported. GmbH support (K1) is planned.' },
      { q: 'Which documents are recognized?', a: 'Over 15 types: Lohnzettel, L1, E1, E1a, E1b, E1kv, bank statements, property tax, SVS, annual accounts, U1, UVA, purchase contracts, rental contracts and more.' },
      { q: 'How secure is my data?', a: 'AES-256 encryption, GDPR-compliant, all data stays in the EU. No tracking cookies.' },
    ],
    ctaKicker: 'Ready?',
    ctaTitle: 'Stop sorting receipts.',
    ctaBody: 'Upload, done. Taxja handles the rest.',
    dlTitle: 'Take Taxja on the go',
    dlDesc: 'Snap receipts, log expenses and check your tax status — right from your phone.',
    dlScanHint: 'Scan QR code to download',
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: 'Open Web App',
    oohkBridgeTag: 'Taxja by OOHK',
    oohkBridgeText: 'Taxja is an AI tax product built by OOHK and serves as our flagship application for the Austrian tax workflow.',
  },
  zh: {
    badge: '奥地利智能税务引擎',
    h1: '上传凭证。\n拿走税表。',
    h1Highlights: ['AI 驱动。', '全自动。', '几分钟搞定。'],
    subtitle: 'Taxja 将你的票据自动转化为完整的奥地利税务申报表 — 全程自动、每步可查、符合当地法规。',
    loginLabel: '登录',
    ctaPrimary: '免费开始',
    ctaSecondary: '查看价格',
    stats: [
      { value: '9', numericValue: 9, label: '种语言' },
      { value: '<5 分钟', numericValue: 5, prefix: '<', suffix: ' 分钟', label: '获得概览' },
      { value: '2022–2026', label: '覆盖税年' },
      { value: 'AES-256', label: '加密标准' },
    ],
    trustBadges: ['GDPR', 'AES-256', 'EU 托管', 'FinanzOnline'],
    showLabel: '实时预览',
    showTitle: '全部税务报表 — 自动生成',
    showDesc: '收支报表、损益表、E1/E1a/E1b、L1/L1k、K1、U1、UVA、科目余额表、固定资产清单 — 一键生成。',
    showcaseReports: enShowcaseReports,
    featKicker: '核心功能',
    featTitle: '报税所需，一应俱全。',
    features: [
      { icon: 'doc', title: '即时识别', desc: '拍照或上传 PDF — 自动识别类型、金额、类别并归档。' },
      { icon: 'brain', title: '税务判断', desc: '能否抵扣？该填哪张表？依据奥地利税法自动判断。' },
      { icon: 'building', title: '表格自动填写', desc: 'E1、E1a、E1b、L1、U1 — 全部自动填好，可直接导出。' },
      { icon: 'repeat', title: '缺漏预警', desc: '缺少的票据、临近的截止日、税务风险 — 在税务局之前发现。' },
      { icon: 'chat', title: '全收入类型', desc: '工资、租金、经营、自由职业 — 清晰分类，熟知规则。' },
      { icon: 'health', title: '法规内置', desc: '税率、补贴、折旧、社保、增值税 — 覆盖 2022–2026 年。' },
    ],
    howKicker: '使用流程',
    howTitle: '三步搞定，就这么简单。',
    steps: [
      { num: '01', title: '创建账户', desc: '免费注册，设置个人资料，上传第一批文档。' },
      { num: '02', title: 'AI 分析', desc: '识别文档、分类交易、计算抵扣 — 全部自动完成。' },
      { num: '03', title: '导出报表', desc: '检查税务报表，导出到 FinanzOnline 或发给税务顾问。' },
    ],
    faqKicker: '常见问题',
    faqTitle: '你可能想知道的。',
    faqs: [
      { q: '需要税务知识吗？', a: '不需要。Taxja 会解释每一步，自动建议抵扣项，并通过税务健康检查自动核查你的数据。' },
      { q: '只适合上班族吗？', a: '不是 — 雇员、自由职业者、个体经营者、房东都支持。GmbH (K1) 支持计划中。' },
      { q: '能识别哪些文档？', a: '超过 15 种：工资单、L1、E1、E1a、E1b、E1kv、银行流水、房产税、SVS、年报、U1、UVA、购房合同、租赁合同等。' },
      { q: '数据安全吗？', a: 'AES-256 加密，GDPR 合规，所有数据存储在欧盟。不使用追踪 Cookie。' },
    ],
    ctaKicker: '准备好了？',
    ctaTitle: '告别手动整理。',
    ctaBody: '上传即完成。Taxja 全程处理。',
    dlTitle: '随时随地使用 Taxja',
    dlDesc: '拍照上传凭证、记录支出、查看税务状态 — 手机上就能完成。',
    dlScanHint: '扫描二维码下载',
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: '打开网页版',
    oohkBridgeTag: 'Taxja by OOHK',
    oohkBridgeText: 'Taxja 是 OOHK 打造的 AI 税务产品，也是 OOHK 面向奥地利税务场景推出的旗舰应用。',
  },
  fr: {
    badge: 'Disponible pour 2022–2026',
    h1: 'Vos imp\u00f4ts.\nEnt\u00e8rement automatis\u00e9s. ',
    h1Highlights: ['Propuls\u00e9 par l\u2019IA.', 'En quelques minutes.', 'Sans stress.'],
    subtitle: '15+ types de documents reconnus automatiquement, transactions class\u00e9es intelligemment, d\u00e9clarations fiscales g\u00e9n\u00e9r\u00e9es en un clic \u2014 conforme au RGPD avec chiffrement AES-256.',
    loginLabel: 'Se connecter',
    ctaPrimary: 'Commencer gratuitement',
    ctaSecondary: 'Voir les tarifs',
    stats: [
      { value: '9', numericValue: 9, label: 'langues' },
      { value: '<5 min', numericValue: 5, prefix: '<', suffix: ' min', label: 'pour un aper\u00e7u' },
      { value: '2022\u20132026', label: 'ann\u00e9es fiscales' },
      { value: 'AES-256', label: 'chiffrement' },
    ],
    trustBadges: ['RGPD', 'AES-256', 'H\u00e9berg\u00e9 en UE', 'FinanzOnline'],
    showLabel: 'Aper\u00e7u en direct',
    showTitle: 'Vos d\u00e9clarations fiscales \u2014 g\u00e9n\u00e9r\u00e9es automatiquement',
    showDesc: 'Compte de r\u00e9sultat, E1/E1a/E1b, L1/L1k, K1, U1, TVA, balance g\u00e9n\u00e9rale, registre des immobilisations \u2014 tout en un clic.',
    showcaseReports: enShowcaseReports,
    featKicker: 'Fonctionnalit\u00e9s',
    featTitle: 'Tout ce dont vous avez besoin pour vos imp\u00f4ts.',
    features: [
      { icon: 'doc', title: '15+ types de documents reconnus', desc: 'L1, L1k, E1, E1a, E1b, E1kv, fiches de paie, relev\u00e9s bancaires, taxe fonci\u00e8re, SVS, comptes annuels, U1, UVA et plus \u2014 reconnus et extraits automatiquement.' },
      { icon: 'brain', title: 'Classification IA avec apprentissage', desc: 'R\u00e8gles, machine learning et LLM dans un seul pipeline. Corrigez une fois, le syst\u00e8me apprend et cr\u00e9e automatiquement des r\u00e8gles.' },
      { icon: 'building', title: 'Gestion immobili\u00e8re & amortissements', desc: 'Actes d\u2019achat, baux, pr\u00eats \u2014 tout est li\u00e9. Les amortissements sont calcul\u00e9s et comptabilis\u00e9s en \u00e9critures r\u00e9currentes.' },
      { icon: 'repeat', title: 'Transactions r\u00e9currentes', desc: 'Loyer, assurance, cotisations SVS \u2014 configurez une fois, comptabilis\u00e9 automatiquement chaque mois.' },
      { icon: 'chat', title: 'Assistant fiscal IA', desc: 'Posez vos questions fiscales directement dans le chat. L\u2019assistant conna\u00eet vos donn\u00e9es et le droit fiscal autrichien.' },
      { icon: 'health', title: 'Bilan de sant\u00e9 fiscal', desc: 'Re\u00e7us manquants, d\u00e9ductions oubli\u00e9es, \u00e9ch\u00e9ances proches \u2014 le syst\u00e8me v\u00e9rifie et vous alerte automatiquement.' },
    ],
    howKicker: 'Comment \u00e7a marche',
    howTitle: 'Trois \u00e9tapes. C\u2019est tout.',
    steps: [
      { num: '01', title: 'Cr\u00e9er un compte', desc: 'Inscription gratuite, configuration du profil et t\u00e9l\u00e9chargement de vos premiers documents.' },
      { num: '02', title: 'L\u2019IA analyse', desc: 'Reconnaissance des documents, classification des transactions, calcul des d\u00e9ductions \u2014 tout est automatique.' },
      { num: '03', title: 'Exporter', desc: 'V\u00e9rifiez vos d\u00e9clarations et exportez-les vers FinanzOnline ou votre conseiller fiscal.' },
    ],
    faqKicker: 'FAQ',
    faqTitle: 'Questions fr\u00e9quentes.',
    faqs: [
      { q: 'Faut-il des connaissances fiscales ?', a: 'Non. Taxja vous guide \u00e0 chaque \u00e9tape, sugg\u00e8re les d\u00e9ductions et v\u00e9rifie automatiquement vos donn\u00e9es gr\u00e2ce au bilan de sant\u00e9 fiscal.' },
      { q: 'R\u00e9serv\u00e9 aux salari\u00e9s ?', a: 'Non \u2014 salari\u00e9s, ind\u00e9pendants, freelances et propri\u00e9taires bailleurs sont tous pris en charge. Le support GmbH (K1) est pr\u00e9vu.' },
      { q: 'Quels documents sont reconnus ?', a: 'Plus de 15 types : fiches de paie, L1, E1, E1a, E1b, E1kv, relev\u00e9s bancaires, taxe fonci\u00e8re, SVS, comptes annuels, U1, UVA, actes d\u2019achat, baux et plus.' },
      { q: 'Mes donn\u00e9es sont-elles s\u00e9curis\u00e9es ?', a: 'Chiffrement AES-256, conformit\u00e9 RGPD, toutes les donn\u00e9es restent dans l\u2019UE. Aucun cookie de suivi.' },
    ],
    ctaKicker: 'Pr\u00eat ?',
    ctaTitle: 'Vos imp\u00f4ts m\u00e9ritent l\u2019automatisation.',
    ctaBody: 'Compte gratuit en moins de 2 minutes \u2014 l\u2019IA s\u2019occupe du reste.',
    dlTitle: 'Emportez Taxja partout',
    dlDesc: 'Photographiez vos re\u00e7us, enregistrez vos d\u00e9penses et suivez votre situation fiscale \u2014 directement sur votre t\u00e9l\u00e9phone.',
    dlScanHint: 'Scannez le QR code pour t\u00e9l\u00e9charger',
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: 'Ouvrir l\u2019appli web',
    oohkBridgeTag: 'Taxja by OOHK',
    oohkBridgeText: 'Taxja est un produit fiscal pilot\u00e9 par l\u2019IA, d\u00e9velopp\u00e9 par OOHK. C\u2019est notre application phare pour la fiscalit\u00e9 autrichienne.',
  },
  ru: {
    badge: '\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u0434\u043b\u044f 2022\u20132026',
    h1: '\u0412\u0430\u0448\u0438 \u043d\u0430\u043b\u043e\u0433\u0438.\n\u041f\u043e\u043b\u043d\u043e\u0441\u0442\u044c\u044e \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438. ',
    h1Highlights: ['\u041d\u0430 \u0431\u0430\u0437\u0435 \u0418\u0418.', '\u0417\u0430 \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u043e \u043c\u0438\u043d\u0443\u0442.', '\u0411\u0435\u0437 \u0441\u0442\u0440\u0435\u0441\u0441\u0430.'],
    subtitle: '15+ \u0442\u0438\u043f\u043e\u0432 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432 \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u044e\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438, \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0438 \u043a\u043b\u0430\u0441\u0441\u0438\u0444\u0438\u0446\u0438\u0440\u0443\u044e\u0442\u0441\u044f \u0438\u043d\u0442\u0435\u043b\u043b\u0435\u043a\u0442\u0443\u0430\u043b\u044c\u043d\u043e, \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0435 \u043e\u0442\u0447\u0451\u0442\u044b \u0433\u0435\u043d\u0435\u0440\u0438\u0440\u0443\u044e\u0442\u0441\u044f \u043c\u0433\u043d\u043e\u0432\u0435\u043d\u043d\u043e \u2014 GDPR, \u0448\u0438\u0444\u0440\u043e\u0432\u0430\u043d\u0438\u0435 AES-256.',
    loginLabel: '\u0412\u043e\u0439\u0442\u0438',
    ctaPrimary: '\u041d\u0430\u0447\u0430\u0442\u044c \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e',
    ctaSecondary: '\u0423\u0437\u043d\u0430\u0442\u044c \u0446\u0435\u043d\u044b',
    stats: [
      { value: '9', numericValue: 9, label: '\u044f\u0437\u044b\u043a\u043e\u0432' },
      { value: '<5 \u043c\u0438\u043d', numericValue: 5, prefix: '<', suffix: ' \u043c\u0438\u043d', label: '\u0434\u043e \u043f\u0435\u0440\u0432\u043e\u0433\u043e \u043e\u0431\u0437\u043e\u0440\u0430' },
      { value: '2022\u20132026', label: '\u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0435 \u0433\u043e\u0434\u044b' },
      { value: 'AES-256', label: '\u0448\u0438\u0444\u0440\u043e\u0432\u0430\u043d\u0438\u0435' },
    ],
    trustBadges: ['GDPR', 'AES-256', '\u0425\u043e\u0441\u0442\u0438\u043d\u0433 \u0432 \u0415\u0421', 'FinanzOnline'],
    showLabel: '\u041f\u0440\u0435\u0434\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440',
    showTitle: '\u0412\u0430\u0448\u0438 \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0435 \u043e\u0442\u0447\u0451\u0442\u044b \u2014 \u0441\u0433\u0435\u043d\u0435\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u044b \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438',
    showDesc: '\u041e\u0442\u0447\u0451\u0442 \u043e \u0434\u043e\u0445\u043e\u0434\u0430\u0445, E1/E1a/E1b, L1/L1k, K1, U1, \u041d\u0414\u0421, \u043e\u0431\u043e\u0440\u043e\u0442\u043d\u043e-\u0441\u0430\u043b\u044c\u0434\u043e\u0432\u0430\u044f \u0432\u0435\u0434\u043e\u043c\u043e\u0441\u0442\u044c, \u0440\u0435\u0435\u0441\u0442\u0440 \u0430\u043a\u0442\u0438\u0432\u043e\u0432 \u2014 \u0432\u0441\u0451 \u043e\u0434\u043d\u0438\u043c \u043d\u0430\u0436\u0430\u0442\u0438\u0435\u043c.',
    showcaseReports: enShowcaseReports,
    featKicker: '\u0412\u043e\u0437\u043c\u043e\u0436\u043d\u043e\u0441\u0442\u0438',
    featTitle: '\u0412\u0441\u0451, \u0447\u0442\u043e \u043d\u0443\u0436\u043d\u043e \u0434\u043b\u044f \u0432\u0430\u0448\u0438\u0445 \u043d\u0430\u043b\u043e\u0433\u043e\u0432.',
    features: [
      { icon: 'doc', title: '15+ \u0442\u0438\u043f\u043e\u0432 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432 \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u044e\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438', desc: 'L1, L1k, E1, E1a, E1b, E1kv, \u0440\u0430\u0441\u0447\u0451\u0442\u043d\u044b\u0435 \u043b\u0438\u0441\u0442\u043a\u0438, \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u0438\u0435 \u0432\u044b\u043f\u0438\u0441\u043a\u0438, \u043d\u0430\u043b\u043e\u0433 \u043d\u0430 \u043d\u0435\u0434\u0432\u0438\u0436\u0438\u043c\u043e\u0441\u0442\u044c, SVS, \u0433\u043e\u0434\u043e\u0432\u044b\u0435 \u043e\u0442\u0447\u0451\u0442\u044b, U1, UVA \u0438 \u0434\u0440\u0443\u0433\u043e\u0435 \u2014 \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u044e\u0442\u0441\u044f \u0438 \u0438\u0437\u0432\u043b\u0435\u043a\u0430\u044e\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438.' },
      { icon: 'brain', title: 'AI-\u043a\u043b\u0430\u0441\u0441\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u044f \u0441 \u043e\u0431\u0443\u0447\u0435\u043d\u0438\u0435\u043c', desc: '\u041f\u0440\u0430\u0432\u0438\u043b\u0430, \u043c\u0430\u0448\u0438\u043d\u043d\u043e\u0435 \u043e\u0431\u0443\u0447\u0435\u043d\u0438\u0435 \u0438 LLM \u0432 \u0435\u0434\u0438\u043d\u043e\u043c \u043a\u043e\u043d\u0432\u0435\u0439\u0435\u0440\u0435. \u0418\u0441\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u043e\u0434\u0438\u043d \u0440\u0430\u0437 \u2014 \u0441\u0438\u0441\u0442\u0435\u043c\u0430 \u0437\u0430\u043f\u043e\u043c\u043d\u0438\u0442 \u0438 \u0441\u043e\u0437\u0434\u0430\u0441\u0442 \u043f\u0440\u0430\u0432\u0438\u043b\u0430 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438.' },
      { icon: 'building', title: '\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u043d\u0435\u0434\u0432\u0438\u0436\u0438\u043c\u043e\u0441\u0442\u044c\u044e \u0438 \u0430\u043c\u043e\u0440\u0442\u0438\u0437\u0430\u0446\u0438\u044f', desc: '\u0414\u043e\u0433\u043e\u0432\u043e\u0440\u044b \u043a\u0443\u043f\u043b\u0438-\u043f\u0440\u043e\u0434\u0430\u0436\u0438, \u0430\u0440\u0435\u043d\u0434\u044b, \u043a\u0440\u0435\u0434\u0438\u0442\u044b \u2014 \u0432\u0441\u0451 \u0441\u0432\u044f\u0437\u0430\u043d\u043e. \u0410\u043c\u043e\u0440\u0442\u0438\u0437\u0430\u0446\u0438\u044f \u0440\u0430\u0441\u0441\u0447\u0438\u0442\u044b\u0432\u0430\u0435\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438 \u0438 \u043f\u0440\u043e\u0432\u043e\u0434\u0438\u0442\u0441\u044f \u043a\u0430\u043a \u043f\u0435\u0440\u0438\u043e\u0434\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u044f.' },
      { icon: 'repeat', title: '\u041f\u0435\u0440\u0438\u043e\u0434\u0438\u0447\u0435\u0441\u043a\u0438\u0435 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438', desc: '\u0410\u0440\u0435\u043d\u0434\u0430, \u0441\u0442\u0440\u0430\u0445\u043e\u0432\u043a\u0430, \u0432\u0437\u043d\u043e\u0441\u044b SVS \u2014 \u043d\u0430\u0441\u0442\u0440\u043e\u0439\u0442\u0435 \u043e\u0434\u0438\u043d \u0440\u0430\u0437, \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u0435 \u043a\u0430\u0436\u0434\u044b\u0439 \u043c\u0435\u0441\u044f\u0446.' },
      { icon: 'chat', title: 'AI \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u043f\u043e\u043c\u043e\u0449\u043d\u0438\u043a', desc: '\u0417\u0430\u0434\u0430\u0432\u0430\u0439\u0442\u0435 \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u044b \u043f\u0440\u044f\u043c\u043e \u0432 \u0447\u0430\u0442\u0435. \u041f\u043e\u043c\u043e\u0449\u043d\u0438\u043a \u0437\u043d\u0430\u0435\u0442 \u0432\u0430\u0448\u0438 \u0434\u0430\u043d\u043d\u044b\u0435 \u0438 \u0430\u0432\u0441\u0442\u0440\u0438\u0439\u0441\u043a\u043e\u0435 \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u043e\u0435 \u043f\u0440\u0430\u0432\u043e.' },
      { icon: 'health', title: '\u041d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u0447\u0435\u043a-\u0430\u043f', desc: '\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u044e\u0449\u0438\u0435 \u0447\u0435\u043a\u0438, \u0437\u0430\u0431\u044b\u0442\u044b\u0435 \u0432\u044b\u0447\u0435\u0442\u044b, \u043f\u0440\u0438\u0431\u043b\u0438\u0436\u0430\u044e\u0449\u0438\u0435\u0441\u044f \u0441\u0440\u043e\u043a\u0438 \u2014 \u0441\u0438\u0441\u0442\u0435\u043c\u0430 \u043f\u0440\u043e\u0432\u0435\u0440\u044f\u0435\u0442 \u0438 \u043d\u0430\u043f\u043e\u043c\u0438\u043d\u0430\u0435\u0442 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438.' },
    ],
    howKicker: '\u041a\u0430\u043a \u044d\u0442\u043e \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442',
    howTitle: '\u0422\u0440\u0438 \u0448\u0430\u0433\u0430. \u0418 \u0432\u0441\u0451.',
    steps: [
      { num: '01', title: '\u0421\u043e\u0437\u0434\u0430\u0439\u0442\u0435 \u0430\u043a\u043a\u0430\u0443\u043d\u0442', desc: '\u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u0430\u044f \u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044f, \u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430 \u043f\u0440\u043e\u0444\u0438\u043b\u044f \u0438 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u043f\u0435\u0440\u0432\u044b\u0445 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432.' },
      { num: '02', title: 'AI \u0430\u043d\u0430\u043b\u0438\u0437\u0438\u0440\u0443\u0435\u0442', desc: '\u0420\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u0432\u0430\u043d\u0438\u0435 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u043e\u0432, \u043a\u043b\u0430\u0441\u0441\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u044f \u0442\u0440\u0430\u043d\u0437\u0430\u043a\u0446\u0438\u0439, \u0440\u0430\u0441\u0447\u0451\u0442 \u0432\u044b\u0447\u0435\u0442\u043e\u0432 \u2014 \u0432\u0441\u0451 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438.' },
      { num: '03', title: '\u042d\u043a\u0441\u043f\u043e\u0440\u0442', desc: '\u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0435 \u043e\u0442\u0447\u0451\u0442\u044b \u0438 \u044d\u043a\u0441\u043f\u043e\u0440\u0442\u0438\u0440\u0443\u0439\u0442\u0435 \u0434\u043b\u044f FinanzOnline \u0438\u043b\u0438 \u0432\u0430\u0448\u0435\u0433\u043e \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u043e\u0433\u043e \u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u043d\u0442\u0430.' },
    ],
    faqKicker: '\u0427\u0430\u0441\u0442\u044b\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u044b',
    faqTitle: '\u041e\u0442\u0432\u0435\u0442\u044b \u043d\u0430 \u043f\u043e\u043f\u0443\u043b\u044f\u0440\u043d\u044b\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u044b.',
    faqs: [
      { q: '\u041d\u0443\u0436\u043d\u044b \u043b\u0438 \u0437\u043d\u0430\u043d\u0438\u044f \u0432 \u043d\u0430\u043b\u043e\u0433\u043e\u043e\u0431\u043b\u043e\u0436\u0435\u043d\u0438\u0438?', a: '\u041d\u0435\u0442. Taxja \u043e\u0431\u044a\u044f\u0441\u043d\u044f\u0435\u0442 \u043a\u0430\u0436\u0434\u044b\u0439 \u0448\u0430\u0433, \u043f\u0440\u0435\u0434\u043b\u0430\u0433\u0430\u0435\u0442 \u0432\u044b\u0447\u0435\u0442\u044b \u0438 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438 \u043f\u0440\u043e\u0432\u0435\u0440\u044f\u0435\u0442 \u0432\u0430\u0448\u0438 \u0434\u0430\u043d\u043d\u044b\u0435 \u0441 \u043f\u043e\u043c\u043e\u0449\u044c\u044e \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u043e\u0433\u043e \u0447\u0435\u043a-\u0430\u043f\u0430.' },
      { q: '\u0422\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u043d\u0430\u0451\u043c\u043d\u044b\u0445 \u0440\u0430\u0431\u043e\u0442\u043d\u0438\u043a\u043e\u0432?', a: '\u041d\u0435\u0442 \u2014 \u043d\u0430\u0451\u043c\u043d\u044b\u0435, \u0441\u0430\u043c\u043e\u0437\u0430\u043d\u044f\u0442\u044b\u0435, \u0444\u0440\u0438\u043b\u0430\u043d\u0441\u0435\u0440\u044b \u0438 \u0430\u0440\u0435\u043d\u0434\u043e\u0434\u0430\u0442\u0435\u043b\u0438 \u2014 \u0432\u0441\u0435 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u044e\u0442\u0441\u044f. \u041f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430 GmbH (K1) \u043f\u043b\u0430\u043d\u0438\u0440\u0443\u0435\u0442\u0441\u044f.' },
      { q: '\u041a\u0430\u043a\u0438\u0435 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b \u0440\u0430\u0441\u043f\u043e\u0437\u043d\u0430\u044e\u0442\u0441\u044f?', a: '\u0411\u043e\u043b\u0435\u0435 15 \u0442\u0438\u043f\u043e\u0432: \u0440\u0430\u0441\u0447\u0451\u0442\u043d\u044b\u0435 \u043b\u0438\u0441\u0442\u043a\u0438, L1, E1, E1a, E1b, E1kv, \u0431\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u0438\u0435 \u0432\u044b\u043f\u0438\u0441\u043a\u0438, \u043d\u0430\u043b\u043e\u0433 \u043d\u0430 \u043d\u0435\u0434\u0432\u0438\u0436\u0438\u043c\u043e\u0441\u0442\u044c, SVS, \u0433\u043e\u0434\u043e\u0432\u044b\u0435 \u043e\u0442\u0447\u0451\u0442\u044b, U1, UVA, \u0434\u043e\u0433\u043e\u0432\u043e\u0440\u044b \u043a\u0443\u043f\u043b\u0438-\u043f\u0440\u043e\u0434\u0430\u0436\u0438, \u0434\u043e\u0433\u043e\u0432\u043e\u0440\u044b \u0430\u0440\u0435\u043d\u0434\u044b \u0438 \u0434\u0440\u0443\u0433\u043e\u0435.' },
      { q: '\u041d\u0430\u0441\u043a\u043e\u043b\u044c\u043a\u043e \u0437\u0430\u0449\u0438\u0449\u0435\u043d\u044b \u043c\u043e\u0438 \u0434\u0430\u043d\u043d\u044b\u0435?', a: '\u0428\u0438\u0444\u0440\u043e\u0432\u0430\u043d\u0438\u0435 AES-256, \u0441\u043e\u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0438\u0435 GDPR, \u0432\u0441\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 \u0445\u0440\u0430\u043d\u044f\u0442\u0441\u044f \u0432 \u0415\u0421. \u041d\u0438\u043a\u0430\u043a\u0438\u0445 \u043e\u0442\u0441\u043b\u0435\u0436\u0438\u0432\u0430\u044e\u0449\u0438\u0445 \u0444\u0430\u0439\u043b\u043e\u0432 cookie.' },
    ],
    ctaKicker: '\u0413\u043e\u0442\u043e\u0432\u044b?',
    ctaTitle: '\u0412\u0430\u0448\u0438 \u043d\u0430\u043b\u043e\u0433\u0438 \u0437\u0430\u0441\u043b\u0443\u0436\u0438\u0432\u0430\u044e\u0442 \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0437\u0430\u0446\u0438\u0438.',
    ctaBody: '\u0411\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u044b\u0439 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u0437\u0430 2 \u043c\u0438\u043d\u0443\u0442\u044b \u2014 AI \u0441\u0434\u0435\u043b\u0430\u0435\u0442 \u043e\u0441\u0442\u0430\u043b\u044c\u043d\u043e\u0435.',
    dlTitle: 'Taxja \u0432\u0441\u0435\u0433\u0434\u0430 \u043f\u043e\u0434 \u0440\u0443\u043a\u043e\u0439',
    dlDesc: '\u0424\u043e\u0442\u043e\u0433\u0440\u0430\u0444\u0438\u0440\u0443\u0439\u0442\u0435 \u0447\u0435\u043a\u0438, \u0444\u0438\u043a\u0441\u0438\u0440\u0443\u0439\u0442\u0435 \u0440\u0430\u0441\u0445\u043e\u0434\u044b \u0438 \u043e\u0442\u0441\u043b\u0435\u0436\u0438\u0432\u0430\u0439\u0442\u0435 \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u0441\u0442\u0430\u0442\u0443\u0441 \u2014 \u043f\u0440\u044f\u043c\u043e \u0441 \u0442\u0435\u043b\u0435\u0444\u043e\u043d\u0430.',
    dlScanHint: '\u041e\u0442\u0441\u043a\u0430\u043d\u0438\u0440\u0443\u0439\u0442\u0435 QR-\u043a\u043e\u0434 \u0434\u043b\u044f \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438',
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: '\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0432\u0435\u0431-\u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435',
    oohkBridgeTag: 'Taxja by OOHK',
    oohkBridgeText: 'Taxja \u2014 \u044d\u0442\u043e AI-\u043f\u0440\u043e\u0434\u0443\u043a\u0442 \u0434\u043b\u044f \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u043e\u0433\u043e \u0443\u0447\u0451\u0442\u0430, \u0440\u0430\u0437\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043d\u044b\u0439 OOHK. \u042d\u0442\u043e \u043d\u0430\u0448\u0435 \u0444\u043b\u0430\u0433\u043c\u0430\u043d\u0441\u043a\u043e\u0435 \u043f\u0440\u0438\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u0434\u043b\u044f \u0430\u0432\u0441\u0442\u0440\u0438\u0439\u0441\u043a\u043e\u0439 \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u043e\u0439 \u0441\u0438\u0441\u0442\u0435\u043c\u044b.',
  },
  hu: {
    badge: 'AI adómotor Ausztriához',
    h1: "Töltsd fel a bizonylatot.\nKapd meg az adóbevallást.",
    h1Highlights: ['AI-alapú.', 'Percek alatt.', 'Stresszmentesen.'],
    subtitle: 'A Taxja a dokumentumaidat kész osztrák adóbevallássá alakítja — teljesen automatikusan, átláthatóan és jogszabályoknak megfelelően.',
    loginLabel: 'Bejelentkezés',
    ctaPrimary: 'Ingyenes indítás',
    ctaSecondary: 'Árak megtekintése',
    stats: [
      { value: '9', numericValue: 9, label: 'nyelv' },
      { value: '<5 perc', numericValue: 5, prefix: '<', suffix: ' perc', label: 'az első áttekintésig' },
      { value: '2022–2026', label: 'adóévek' },
      { value: 'AES-256', label: 'titkosítás' },
    ],
    trustBadges: ['GDPR', 'AES-256', 'EU-tárhely', 'FinanzOnline'],
    showLabel: 'Élő előnézet',
    showTitle: 'Adójelentéseid — automatikusan generálva',
    showDesc: 'E/A kimutatás, E1/E1a/E1b, L1/L1k, K1, U1, ÁFA, főkönyvi kivonat, eszköznyilvántartás — egyetlen kattintással.',
    showcaseReports: enShowcaseReports,
    featKicker: 'Funkciók',
    featTitle: 'Minden, amire az adózáshoz szükséged van.',
    features: [
      { icon: 'doc', title: 'Azonnali felismerés', desc: 'Fénykép vagy PDF — a Taxja automatikusan azonosítja a típust, összeget és kategóriát.' },
      { icon: 'brain', title: 'Adóintelligencia', desc: 'Leválasztható? Melyik űrlap? A Taxja az osztrák adójog alapján dönt.' },
      { icon: 'building', title: 'Űrlapok kitöltve', desc: 'E1, E1a, E1b, L1, U1 — automatikusan kitöltve, exportálásra készen.' },
      { icon: 'repeat', title: 'Hiányok felismerése', desc: 'Hiányzó bizonylatok, határidők, kockázatok — még az adóhivatal előtt jelezve.' },
      { icon: 'chat', title: 'Minden jövedelemtípus', desc: 'Fizetés, bérleti díj, vállalkozás, szabadfoglalkozás — tisztán elkülönítve.' },
      { icon: 'health', title: 'Aktuális jogszabályok', desc: 'Tarifak, kedvezmények, értékcsökkenés, SVS, ÁFA — 2022–2026 naprakész.' },
    ],
    howKicker: "Hogyan működik",
    howTitle: "Három lépés. Ennyi az egész.",
    steps: [
      { num: '01', title: 'Fiók létrehozása', desc: 'Ingyenes regisztráció, profil beállítása és első dokumentumok feltöltése.' },
      { num: '02', title: 'AI elemez', desc: 'Dokumentumok felismerése, tranzakciók osztályozása, levonások számítása — mind automatikusan.' },
      { num: '03', title: 'Exportálás', desc: "Adójelentések áttekintése és exportálása a FinanzOnline-hoz vagy az adótanácsadódnak." },
    ],
    faqKicker: 'GYIK',
    faqTitle: 'Gyakran ismételt kérdések.',
    faqs: [
      { q: 'Kell adózási tudás?', a: 'Nem. A Taxja minden lépést elmagyaráz, levonásokat javasol és automatikusan ellenőrzi az adataidat.' },
      { q: 'Csak alkalmazottaknak?', a: 'Nem — alkalmazottak, önállók, szabadfoglalkozásúk és bérbeadók egyaránt támogatottak. GmbH (K1) támogatás tervben.' },
      { q: 'Milyen dokumentumokat ismer fel?', a: "Több mint 15 típust: bérjegyzék, L1, E1, E1a, E1b, E1kv, bankkivonatok, ingatlanadó, SVS, éves beszámoló, U1, UVA, adásvételi és bérleti szerződések és még több." },
      { q: 'Mennyire biztonságosak az adataim?', a: 'AES-256 titkosítás, GDPR-megfelelő, minden adat az EU-ban marad. Nincs követő cookie.' },
    ],
    ctaKicker: 'Készen állsz?',
    ctaTitle: "Vége a bizonylatok rendezgetésének.",
    ctaBody: "Feltöltés, kész. A Taxja intézi a többit.",
    dlTitle: "Vidd magaddal a Taxját",
    dlDesc: "Fényképezd a bizonylatokat, rögzítsd a kiadásokat és ellenőrizd az adóstátuszodat — közvetlenül a telefonodról.",
    dlScanHint: 'QR-kód beolvasása a letöltéshez',
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: 'Webalkalmazás megnyitása',
    oohkBridgeTag: 'Taxja by OOHK',
    oohkBridgeText: "A Taxja az OOHK által fejlesztett AI adótermék, és az osztrák adózási munkafolyamatok zászlóshajó alkalmazása.",
  },
  pl: {
    badge: 'Silnik podatkowy AI dla Austrii',
    h1: "Wrzuć paragon.\nOdbierz zeznanie podatkowe.",
    h1Highlights: ['Napędzane AI.', 'W kilka minut.', 'Bez stresu.'],
    subtitle: 'Taxja zamienia Twoje dokumenty w gotowe austriackie formularze podatkowe — w pełni automatycznie, przejrzyście i zgodnie z prawem.',
    loginLabel: 'Zaloguj się',
    ctaPrimary: 'Zacznij za darmo',
    ctaSecondary: 'Zobacz ceny',
    stats: [
      { value: '9', numericValue: 9, label: "języków" },
      { value: '<5 min', numericValue: 5, prefix: '<', suffix: ' min', label: 'do pierwszego przeglądu' },
      { value: '2022–2026', label: 'lata podatkowe' },
      { value: 'AES-256', label: 'szyfrowanie' },
    ],
    trustBadges: ['RODO', 'AES-256', 'Hosting w UE', 'FinanzOnline'],
    showLabel: "Podgląd na żywo",
    showTitle: 'Twoje raporty podatkowe — generowane automatycznie',
    showDesc: 'Rachunek przychodów, E1/E1a/E1b, L1/L1k, K1, U1, VAT, bilans próbny, rejestr środków trwałych — jednym kliknięciem.',
    showcaseReports: enShowcaseReports,
    featKicker: 'Funkcje',
    featTitle: 'Wszystko, czego potrzebujesz do rozliczenia podatków.',
    features: [
      { icon: 'doc', title: 'Natychmiastowe rozpoznawanie', desc: "Zdjęcie lub PDF — Taxja automatycznie identyfikuje typ, kwotę i kategorię." },
      { icon: 'brain', title: 'Inteligencja podatkowa', desc: "Odliczalne? Który formularz? Taxja stosuje austriackie prawo podatkowe i wyjaśnia każdą decyzję." },
      { icon: 'building', title: 'Formularze wypełnione', desc: 'E1, E1a, E1b, L1, U1 — automatycznie wypełnione i gotowe do eksportu.' },
      { icon: 'repeat', title: 'Wykrywanie braków', desc: "Brakujące paragony, zbliżające się terminy, ryzyka podatkowe — zgłoszone zanim zrobi to urząd skarbowy." },
      { icon: 'chat', title: "Każdy typ dochodu", desc: "Wynagrodzenie, najem, działalność, freelance — czytelnie rozdzielone." },
      { icon: 'health', title: 'Aktualne prawo', desc: "Stawki, ulgi, amortyzacja, SVS, VAT — aktualne na lata 2022–2026." },
    ],
    howKicker: 'Jak to działa',
    howTitle: "Trzy kroki. To wszystko.",
    steps: [
      { num: '01', title: "Utwórz konto", desc: "Darmowa rejestracja, konfiguracja profilu i przesłanie pierwszych dokumentów." },
      { num: '02', title: 'AI analizuje', desc: "Rozpoznawanie dokumentów, klasyfikacja transakcji, obliczanie odliczeń — wszystko automatycznie." },
      { num: '03', title: 'Eksport', desc: "Sprawdź raporty podatkowe i wyeksportuj do FinanzOnline lub swojego doradcy podatkowego." },
    ],
    faqKicker: 'FAQ',
    faqTitle: 'Często zadawane pytania.',
    faqs: [
      { q: 'Czy potrzebna jest wiedza podatkowa?', a: "Nie. Taxja wyjaśnia każdy krok, sugeruje odliczenia i automatycznie sprawdza Twoje dane." },
      { q: 'Tylko dla pracowników?', a: "Nie — pracownicy, samozatrudnieni, freelancerzy i wynajmujący są obsługiwani. Wsparcie GmbH (K1) w planach." },
      { q: 'Jakie dokumenty są rozpoznawane?', a: "Ponad 15 typów: paski płacowe, L1, E1, E1a, E1b, E1kv, wyciągi bankowe, podatek od nieruchomości, SVS, sprawozdania roczne, U1, UVA, umowy kupna i najmu." },
      { q: 'Jak bezpieczne są moje dane?', a: "Szyfrowanie AES-256, zgodność z RODO, wszystkie dane w UE. Brak ciasteczek śledzących." },
    ],
    ctaKicker: 'Gotowy?',
    ctaTitle: "Koniec z sortowaniem paragonów.",
    ctaBody: "Prześlij, gotowe. Taxja zajmie się resztą.",
    dlTitle: "Zabierz Taxję ze sobą",
    dlDesc: "Fotografuj paragony, rejestruj wydatki i sprawdzaj status podatkowy — prosto z telefonu.",
    dlScanHint: "Zeskanuj kod QR, aby pobrać",
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: "Otwórz aplikację webową",
    oohkBridgeTag: 'Taxja by OOHK',
    oohkBridgeText: "Taxja to produkt podatkowy oparty na AI, stworzony przez OOHK — nasza flagowa aplikacja dla austriackiego systemu podatkowego.",
  },
  tr: {
    badge: "Avusturya için AI vergi motoru",
    h1: "Fişinizi yükleyin.\nVergi beyannamenizi alın.",
    h1Highlights: ['AI destekli.', 'Dakikalar içinde.', 'Stressiz.'],
    subtitle: "Taxja belgelerinizi tamamlanmış Avusturya vergi formlarına dönüştürür — tamamen otomatik, şeffaf ve yasalara uygun.",
    loginLabel: "Giriş yap",
    ctaPrimary: "Ücretsiz başla",
    ctaSecondary: "Fiyatları gör",
    stats: [
      { value: '9', numericValue: 9, label: 'dil' },
      { value: '<5 dk', numericValue: 5, prefix: '<', suffix: ' dk', label: "ilk genel bakışa" },
      { value: '2022–2026', label: "vergi yılları" },
      { value: 'AES-256', label: "şifreleme" },
    ],
    trustBadges: ['KVKK', 'AES-256', 'AB Barındırma', 'FinanzOnline'],
    showLabel: "Canlı önizleme",
    showTitle: "Vergi raporlarınız — otomatik oluşturuldu",
    showDesc: "Gelir-gider tablosu, E1/E1a/E1b, L1/L1k, K1, U1, KDV, mizan, varlık kaydı — tek tıkla.",
    showcaseReports: enShowcaseReports,
    featKicker: "Özellikler",
    featTitle: "Vergileriniz için ihtiyacınız olan her şey.",
    features: [
      { icon: 'doc', title: "Anında tanıma", desc: "Fotoğraf veya PDF — Taxja türü, tutarı ve kategoriyi otomatik belirler." },
      { icon: 'brain', title: 'Vergi zekası', desc: "Düşülebilir mi? Hangi form? Taxja Avusturya vergi hukukunu uygular ve her kararı açıklar." },
      { icon: 'building', title: "Formlar dolduruldu", desc: "E1, E1a, E1b, L1, U1 — otomatik doldurulmuş ve dışa aktarmaya hazır." },
      { icon: 'repeat', title: "Eksik tespiti", desc: "Eksik fişler, yaklaşan son tarihler, vergi riskleri — vergi dairesinden önce bildirilir." },
      { icon: 'chat', title: "Her gelir türü", desc: "Maaş, kira, işletme, serbest meslek — temiz bir şekilde ayrılmış." },
      { icon: 'health', title: "Güncel mevzuat", desc: "Tarifeler, indirimler, amortisman, SVS, KDV — 2022–2026 güncel." },
    ],
    howKicker: "Nasıl çalışır",
    howTitle: "Üç adım. Hepsi bu.",
    steps: [
      { num: '01', title: "Hesap oluştur", desc: "Ücretsiz kayıt, profil ayarı ve ilk belgelerinizi yükleyin." },
      { num: '02', title: 'AI analiz eder', desc: "Belge tanıma, işlem sınıflandırma, kesinti hesaplama — tamamen otomatik." },
      { num: '03', title: "Dışa aktar", desc: "Vergi raporlarınızı inceleyin ve FinanzOnline veya vergi danışmanınıza aktarın." },
    ],
    faqKicker: 'SSS',
    faqTitle: "Sık sorulan sorular.",
    faqs: [
      { q: "Vergi bilgisi gerekli mi?", a: "Hayır. Taxja her adımı açıklar, kesintiler önerir ve verilerinizi otomatik kontrol eder." },
      { q: "Sadece çalışanlar için mi?", a: "Hayır — çalışanlar, serbest meslek, freelancerlar ve ev sahipleri desteklenir. GmbH (K1) desteği planlanıyor." },
      { q: "Hangi belgeler tanınır?", a: "15+ tür: bordro, L1, E1, E1a, E1b, E1kv, banka ekstresi, emlak vergisi, SVS, yıllık hesaplar, U1, UVA, alım ve kira sözleşmeleri." },
      { q: "Verilerim ne kadar güvende?", a: "AES-256 şifreleme, KVKK uyumlu, tüm veriler AB içinde. Takip çerezi yok." },
    ],
    ctaKicker: "Hazır mısınız?",
    ctaTitle: "Fiş sıralamaya son.",
    ctaBody: "Yükle, bitti. Gerisini Taxja halleder.",
    dlTitle: "Taxja yanınızda",
    dlDesc: "Fişleri çekin, harcamaları kaydedin ve vergi durumunuzu kontrol edin — doğrudan telefonunuzdan.",
    dlScanHint: "QR kodu tarayın",
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: "Web uygulamayı aç",
    oohkBridgeTag: 'Taxja by OOHK',
    oohkBridgeText: "Taxja, OOHK tarafından geliştirilen AI vergi ürünüdür ve Avusturya vergi sistemi için amiral gemı uygulamamdır.",
  },
  bs: {
    badge: 'AI porezni motor za Austriju',
    h1: "Dodaj račun.\nDobi poreznu prijavu.",
    h1Highlights: ['AI pogon.', 'Za par minuta.', 'Bez stresa.'],
    subtitle: "Taxja pretvara vaše dokumente u gotove austrijske porezne obrasce — potpuno automatski, transparentno i u skladu sa zakonom.",
    loginLabel: 'Prijava',
    ctaPrimary: 'Počni besplatno',
    ctaSecondary: 'Pogledaj cijene',
    stats: [
      { value: '9', numericValue: 9, label: 'jezika' },
      { value: '<5 min', numericValue: 5, prefix: '<', suffix: ' min', label: 'do prvog pregleda' },
      { value: '2022–2026', label: 'porezne godine' },
      { value: 'AES-256', label: 'enkripcija' },
    ],
    trustBadges: ['GDPR', 'AES-256', 'EU hosting', 'FinanzOnline'],
    showLabel: 'Pregled uživo',
    showTitle: "Vaši porezni izvještaji — automatski generirani",
    showDesc: "Bilans uspjeha, E1/E1a/E1b, L1/L1k, K1, U1, PDV, bruto bilans, registar imovine — jednim klikom.",
    showcaseReports: enShowcaseReports,
    featKicker: 'Funkcije',
    featTitle: "Sve što vam treba za porez.",
    features: [
      { icon: 'doc', title: 'Trenutno prepoznavanje', desc: "Fotografija ili PDF — Taxja automatski prepoznaje tip, iznos i kategoriju." },
      { icon: 'brain', title: 'Porezna inteligencija', desc: "Odbitno? Koji obrazac? Taxja primjenjuje austrijsko porezno pravo i objašnjava svaku odluku." },
      { icon: 'building', title: 'Obrasci popunjeni', desc: "E1, E1a, E1b, L1, U1 — automatski popunjeni i spremni za izvoz." },
      { icon: 'repeat', title: 'Otkrivanje nedostataka', desc: "Nedostajući računi, rokovi, porezni rizici — prijavljeni prije porezne uprave." },
      { icon: 'chat', title: 'Svaka vrsta prihoda', desc: "Plaća, najam, poslovanje, slobodna profesija — uredno razdvojeno." },
      { icon: 'health', title: 'Aktuelno pravo', desc: "Tarife, olakšice, amortizacija, SVS, PDV — ažurno za 2022–2026." },
    ],
    howKicker: 'Kako funkcionira',
    howTitle: "Tri koraka. To je sve.",
    steps: [
      { num: '01', title: 'Kreiraj račun', desc: "Besplatna registracija, podešavanje profila i upload prvih dokumenata." },
      { num: '02', title: 'AI analizira', desc: "Prepoznavanje dokumenata, klasifikacija transakcija, izračun odbitaka — sve automatski." },
      { num: '03', title: 'Izvoz', desc: "Pregledajte porezne izvještaje i izvezite za FinanzOnline ili vašeg poreznog savjetnika." },
    ],
    faqKicker: 'FAQ',
    faqTitle: "Često postavljana pitanja.",
    faqs: [
      { q: "Treba li mi porezno znanje?", a: "Ne. Taxja objašnjava svaki korak, predlaže odbitke i automatski provjerava vaše podatke." },
      { q: 'Samo za zaposlene?', a: "Ne — zaposleni, samozaposleni, freelanceri i iznajmljivači su podržani. GmbH (K1) podrška u planu." },
      { q: 'Koji dokumenti se prepoznaju?', a: "Više od 15 tipova: platne liste, L1, E1, E1a, E1b, E1kv, bankovni izvodi, porez na imovinu, SVS, godišnji računi, U1, UVA, kupoprodajni i ugovori o najmu." },
      { q: 'Koliko su sigurni moji podaci?', a: "AES-256 enkripcija, GDPR usklađenost, svi podaci u EU. Bez praćenja kolačićima." },
    ],
    ctaKicker: 'Spremni?',
    ctaTitle: "Kraj sortiranja računa.",
    ctaBody: "Uploadaj, gotovo. Taxja radi ostatak.",
    dlTitle: 'Taxja uvijek s vama',
    dlDesc: "Fotografirajte račune, bilježite troškove i provjeravajte porezni status — direktno s telefona.",
    dlScanHint: 'Skenirajte QR kod za preuzimanje',
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: 'Otvori web aplikaciju',
    oohkBridgeTag: 'Taxja by OOHK',
    oohkBridgeText: "Taxja je AI porezni proizvod koji je razvio OOHK i naša je vodeća aplikacija za austrijski porezni sistem.",
  },
};

/* ── Typing effect hook ── */
const useTypingEffect = (words: string[], speed = 8, startDelay = 300) => {
  const [index, setIndex] = useState(0);
  const [displayed, setDisplayed] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const word = words[index];
    let timeout: ReturnType<typeof setTimeout>;

    if (!isDeleting && displayed === word) {
      timeout = setTimeout(() => setIsDeleting(true), 2000);
    } else if (isDeleting && displayed === '') {
      setIsDeleting(false);
      setIndex((i) => (i + 1) % words.length);
    } else {
      const delay = isDeleting ? speed * 2 : speed + Math.random() * 20;
      timeout = setTimeout(() => {
        setDisplayed(isDeleting ? word.slice(0, displayed.length - 1) : word.slice(0, displayed.length + 1));
      }, delay);
    }
    return () => clearTimeout(timeout);
  }, [displayed, isDeleting, index, words, speed]);

  // Start delay
  const [started, setStarted] = useState(false);
  useEffect(() => { const t = setTimeout(() => setStarted(true), startDelay); return () => clearTimeout(t); }, [startDelay]);

  return started ? displayed : '';
};

/* ── Reveal hook ── */
const useReveal = () => {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.setAttribute('data-reveal', '');
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { el.classList.add('is-visible'); io.unobserve(el); }
    }, { threshold: 0.1 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return ref;
};

/* ── QR Code Canvas ── */
const QRCanvas = ({ url, size = 140 }: { url: string; size?: number }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    canvas.width = size;
    canvas.height = size;
    // Simple placeholder QR pattern
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, size, size);
    const cellSize = size / 25;
    ctx.fillStyle = '#a855f7';
    // Draw finder patterns
    const drawFinder = (x: number, y: number) => {
      for (let i = 0; i < 7; i++) for (let j = 0; j < 7; j++) {
        if (i === 0 || i === 6 || j === 0 || j === 6 || (i >= 2 && i <= 4 && j >= 2 && j <= 4))
          ctx.fillRect((x + i) * cellSize, (y + j) * cellSize, cellSize, cellSize);
      }
    };
    drawFinder(1, 1); drawFinder(17, 1); drawFinder(1, 17);
    // Random data modules
    for (let i = 0; i < 25; i++) for (let j = 0; j < 25; j++) {
      if (Math.random() > 0.55 && !((i < 9 && j < 9) || (i > 15 && j < 9) || (i < 9 && j > 15)))
        ctx.fillRect(i * cellSize, j * cellSize, cellSize, cellSize);
    }
    // Center logo
    ctx.fillStyle = '#030308';
    ctx.fillRect(size / 2 - 14, size / 2 - 14, 28, 28);
    ctx.fillStyle = '#22d3ee';
    ctx.font = 'bold 14px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('T', size / 2, size / 2 + 1);
  }, [url, size]);
  return <canvas ref={canvasRef} style={{ width: size, height: size }} />;
};


/* ═══ Main HomePage Component ═══ */
const HomePage = () => {
  const { i18n } = useTranslation();
  const lang = normalizeLanguage(i18n.resolvedLanguage || i18n.language);
  const c = copy[lang] ?? copy.en!;
  const { isAuthenticated } = useAuthStore();

  /* Typing effect for hero highlights */
  const typedHighlight = useTypingEffect(c.h1Highlights, 60, 800);

  /* FAQ toggle */
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  /* Mouse tracking for bento card glow */
  const handleBentoMouse = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const card = e.currentTarget;
    const rect = card.getBoundingClientRect();
    card.style.setProperty('--mx', `${e.clientX - rect.left}px`);
    card.style.setProperty('--my', `${e.clientY - rect.top}px`);
  }, []);

  /* Reveal refs */
  const statsRef = useReveal();
  const trustRef = useReveal();
  const showcaseRef = useReveal();
  const featRef = useReveal();
  const stepsRef = useReveal();
  const faqRef = useReveal();
  const ctaRef = useReveal();
  const dlRef = useReveal();

  /* Duplicate showcase reports for infinite carousel */
  const carouselReports = [...c.showcaseReports, ...c.showcaseReports];

  return (
    <div className={`hp ${lang === 'zh' ? 'hp-zh' : ''}`}>
      {/* ── Background layers ── */}
      <LightParticles />
      <div className="hp-ambient">
        <div className="hp-orb hp-orb-1" />
        <div className="hp-orb hp-orb-2" />
        <div className="hp-orb hp-orb-3" />
        <div className="hp-orb hp-orb-4" />
        <div className="hp-orb hp-orb-5" />
      </div>
      <div className="hp-floaters">
        <div className="hp-floater hp-fl-1" />
        <div className="hp-floater hp-fl-2" />
        <div className="hp-floater hp-fl-3" />
        <div className="hp-floater hp-fl-4" />
        <div className="hp-floater hp-fl-5" />
        <div className="hp-floater hp-fl-6" />
        <div className="hp-floater hp-fl-7" />
        <div className="hp-floater hp-fl-8" />
      </div>
      <div className="hp-grid-bg" />

      {/* ── Nav ── */}
      <nav className="hp-nav">
        <div className="hp-nav-in">
          <Link to="/" className="hp-logo">
            <span className="hp-logo-mark">T</span>
            <span className="hp-logo-tx">Taxja</span>
          </Link>
          <div className="hp-nav-r">
            <LanguageSwitcher />
            {isAuthenticated ? (
              <Link to="/dashboard" className="hp-nav-cta">{c.loginLabel}</Link>
            ) : (
              <>
                <Link to="/login" className="hp-nav-link">{c.loginLabel}</Link>
                <Link to="/register" className="hp-nav-cta">{c.ctaPrimary}</Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* ═══ Hero ═══ */}
      <section className="hp-hero">
        <div className="hp-hero-content">
          <span className="hp-chip">{c.badge}</span>
          <h1 className="hp-h1">
            {c.h1}
            <span className="hp-highlight hp-typing">
              {typedHighlight}
              <span className="hp-cursor" />
            </span>
          </h1>
          <p className="hp-subtitle">{c.subtitle}</p>
          <div className="hp-hero-actions">
            <Link to="/register" className="hp-btn hp-btn-primary">{c.ctaPrimary}</Link>
            <Link to="/pricing" className="hp-btn hp-btn-secondary">{c.ctaSecondary}</Link>
          </div>
        </div>
        <div className="hp-scroll-hint">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M19 12l-7 7-7-7" /></svg>
        </div>
      </section>

      {/* ═══ Stats ═══ */}
      <section className="hp-stats-section" ref={statsRef} data-reveal>
        <div className="hp-stats-orb hp-stats-orb-1" />
        <div className="hp-stats-orb hp-stats-orb-2" />
        <div className="hp-stats-orb hp-stats-orb-3" />
        <div className="hp-stats-row">
          {c.stats.map((s, i) => (
            <div className="hp-stat" key={i}>
              <span className="hp-stat-v">{s.value}</span>
              <span className="hp-stat-l">{s.label}</span>
              <div className="hp-stat-bar"><div className="hp-stat-bar-fill" /></div>
            </div>
          ))}
        </div>
      </section>

      <div className="hp-shell">
        {/* ═══ Trust badges ═══ */}
        <div ref={trustRef} data-reveal className="hp-trust-strip">
          {c.trustBadges.map((b, i) => (
            <span className={`hp-trust-badge hp-trust-badge-${i}`} key={i}>
              <span className="hp-trust-pulse" />
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="M9 12l2 2 4-4" /></svg>
              {b}
            </span>
          ))}
        </div>

        <div className="hp-divider" />

        {/* ═══ Showcase (Report Carousel) ═══ */}
        <section className="hp-showcase" ref={showcaseRef} data-reveal>
          <div className="hp-showcase-inner">
            <div className="hp-showcase-grid" />
            <div className="hp-showcase-glow" />
            <div className="hp-scan-line" />
            <div className="hp-showcase-carousel-layout">
              <div className="hp-showcase-left">
                <div className="hp-showcase-pills">
                  <span className="hp-pill hp-pill-live">Live</span>
                  <span className="hp-pill">2025</span>
                </div>
                <h2 className="hp-showcase-title">{c.showTitle}</h2>
                <p className="hp-showcase-desc">{c.showDesc}</p>
                <div className="hp-carousel-indicators">
                  {c.showcaseReports.map((r) => (
                    <span className="hp-carousel-ind" key={r.id}>
                      <span className="hp-carousel-ind-icon">{r.id.toUpperCase()}</span>
                    </span>
                  ))}
                </div>
              </div>
              <div className="hp-showcase-right">
                <div className="hp-carousel-track-wrapper">
                  <div className="hp-carousel-track">
                    {carouselReports.map((r, idx) => (
                      <div className="hp-carousel-card" key={`${r.id}-${idx}`}>
                        <div className="hp-cc-chrome">
                          <span className="hp-cc-dot hp-cc-dot-r" />
                          <span className="hp-cc-dot hp-cc-dot-y" />
                          <span className="hp-cc-dot hp-cc-dot-g" />
                          <span className="hp-cc-chrome-title">{r.icon} {r.title}</span>
                        </div>
                        <div className="hp-cc-body">
                          <table className="hp-cc-table">
                            {r.headers && (
                              <thead><tr>{r.headers.map((h, hi) => <th key={hi}>{h}</th>)}</tr></thead>
                            )}
                            <tbody>
                              {r.rows.map((row, ri) => (
                                <tr key={ri}>
                                  {row.map((cell, ci) => (
                                    <td key={ci} className={cell === '✓' ? 'hp-cc-ded-yes' : cell === '✗' ? 'hp-cc-ded-no' : ''}>
                                      {cell}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {r.summary && (
                            <div className="hp-cc-summary">
                              {r.summary.map((s, si) => (
                                <div key={si} className={`hp-cc-sum-row ${s.accent ? 'hp-cc-sum-accent' : ''}`}>
                                  <span>{s.label}</span>
                                  <span>{s.value}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ═══ Features Bento Grid ═══ */}
        <section className="hp-section" ref={featRef} data-reveal>
          <div className="hp-section-header">
            <span className="hp-kicker">{c.featKicker}</span>
            <h2 className="hp-section-title">{c.featTitle}</h2>
          </div>
          <div className="hp-bento">
            {c.features.map((f, i) => (
              <div className="hp-bento-card" key={i} onMouseMove={handleBentoMouse}>
                <div className="hp-bento-card-glow" />
                <div className="hp-bento-icon">{HudIcons[f.icon]}</div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ═══ Steps ═══ */}
        <section className="hp-section" ref={stepsRef} data-reveal>
          <div className="hp-section-header" style={{ textAlign: 'center' }}>
            <span className="hp-kicker">{c.howKicker}</span>
            <h2 className="hp-section-title">{c.howTitle}</h2>
          </div>
          <div className="hp-steps">
            {c.steps.map((s, i) => (
              <div className="hp-step" key={i}>
                <div className="hp-step-num">
                  <span className="hp-step-ring" />
                  {s.num}
                </div>
                {i < c.steps.length - 1 && <div className="hp-step-connector" />}
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ═══ FAQ ═══ */}
        <section className="hp-section" ref={faqRef} data-reveal>
          <div className="hp-section-header" style={{ textAlign: 'center' }}>
            <span className="hp-kicker">{c.faqKicker}</span>
            <h2 className="hp-section-title">{c.faqTitle}</h2>
          </div>
          <div className="hp-faq-list">
            {c.faqs.map((f, i) => (
              <div
                className={`hp-faq-item ${openFaq === i ? 'hp-faq-open' : ''}`}
                key={i}
                onMouseEnter={() => setOpenFaq(i)}
                onMouseLeave={() => setOpenFaq(null)}
              >
                <div className="hp-faq-q">
                  <span>{f.q}</span>
                  <span className="hp-faq-icon">{openFaq === i ? '−' : '+'}</span>
                </div>
                <div className={`hp-faq-a ${openFaq === i ? 'hp-faq-a-open' : ''}`}>
                  <p>{f.a}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ═══ CTA ═══ */}
        <section className="hp-cta-section" ref={ctaRef} data-reveal>
          <div className="hp-cta-glow" />
          <span className="hp-kicker">{c.ctaKicker}</span>
          <h2>{c.ctaTitle}</h2>
          <p>{c.ctaBody}</p>
          <Link to="/register" className="hp-btn hp-btn-primary">{c.ctaPrimary}</Link>
        </section>

        {/* ═══ OOHK Showcase ═══ */}
        <section className="hp-oohk-showcase">
          <Link to="/company" className="hp-oohk-showcase-link" aria-label="OOHK Company Page">
            <div className="hp-oohk-orbital-stage">
              <div className="hp-oohk-bridge">
                <span className="hp-oohk-bridge-tag">{c.oohkBridgeTag}</span>
                <p className="hp-oohk-bridge-text">{c.oohkBridgeText}</p>
              </div>
              <OohkOrbLarge size={260} />
              <div className="hp-oohk-showcase-label">
                <span className="hp-oohk-showcase-name">OOHK</span>
                <span className="hp-oohk-showcase-sub">AI SYSTEMS</span>
              </div>
            </div>
            <div className="hp-oohk-services">
              {[
                { icon: <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><circle cx="24" cy="24" r="8" opacity="0.6"/><circle cx="24" cy="24" r="3"/><line x1="24" y1="16" x2="24" y2="6"/><line x1="24" y1="32" x2="24" y2="42"/><line x1="16" y1="24" x2="6" y2="24"/><line x1="32" y1="24" x2="42" y2="24"/><circle cx="24" cy="6" r="2"/><circle cx="24" cy="42" r="2"/><circle cx="6" cy="24" r="2"/><circle cx="42" cy="24" r="2"/></svg>,
                  zh: '定制 AI Agent', de: 'AI-Agent-Systeme', en: 'AI Agent Systems',
                  descZh: '围绕客户服务、运营协同与内部流程，设计可执行、可管理的 AI Agent 解决方案。',
                  descDe: 'Ausführbare, verwaltbare AI-Agent-Lösungen rund um Kundenservice, Zusammenarbeit und interne Abläufe.',
                  descEn: 'Executable, manageable AI agent solutions for customer service, collaboration, and internal workflows.' },
                { icon: <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="24,4 42,14 42,34 24,44 6,34 6,14"/><line x1="6" y1="14" x2="42" y2="14" opacity="0.3"/><line x1="6" y1="24" x2="42" y2="24" opacity="0.3"/><line x1="6" y1="34" x2="42" y2="34" opacity="0.3"/><circle cx="24" cy="14" r="2"/><circle cx="24" cy="24" r="2"/><circle cx="24" cy="34" r="2"/></svg>,
                  zh: '知识库 & RAG', de: 'Wissensdatenbank & RAG', en: 'Knowledge Base & RAG',
                  descZh: '将文档、制度与业务资料结构化整理，构建可检索、可追溯的知识底座。',
                  descDe: 'Dokumente und Geschäftsmaterialien strukturiert aufbereitet — durchsuchbar und nachvollziehbar.',
                  descEn: 'Structure documents and business materials into a searchable, traceable knowledge foundation.' },
                { icon: <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M8 24h8l4-8 4 16 4-12 4 4h8"/><circle cx="8" cy="24" r="3" opacity="0.5"/><circle cx="40" cy="24" r="3" opacity="0.5"/><rect x="20" y="4" width="8" height="4" rx="1" opacity="0.4"/><rect x="20" y="40" width="8" height="4" rx="1" opacity="0.4"/></svg>,
                  zh: '流程自动化', de: 'Prozessautomatisierung', en: 'Process Automation',
                  descZh: '将邮件、表单、审批与数据处理串联成完整链路，实现自动触发与稳定执行。',
                  descDe: 'E-Mail, Formulare und Datenverarbeitung zu vollständigen Prozessketten verbunden.',
                  descEn: 'Chain email, forms, approvals, and data processing into complete automated workflows.' },
                { icon: <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><rect x="4" y="18" width="12" height="12" rx="2" opacity="0.5"/><rect x="32" y="4" width="12" height="12" rx="2" opacity="0.5"/><rect x="32" y="32" width="12" height="12" rx="2" opacity="0.5"/><line x1="16" y1="22" x2="32" y2="12"/><line x1="16" y1="28" x2="32" y2="38"/><circle cx="24" cy="17" r="1.5"/><circle cx="24" cy="33" r="1.5"/></svg>,
                  zh: '系统集成', de: 'Systemintegration', en: 'System Integration',
                  descZh: '打通 CRM、ERP、数据库与第三方服务，让 AI 真正进入既有业务链路。',
                  descDe: 'CRM, ERP, Datenbanken und Drittanbieter verbinden — AI in bestehende Prozesse einbetten.',
                  descEn: 'Connect CRM, ERP, databases, and third-party services so AI enters your existing processes.' },
                { icon: <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><circle cx="24" cy="24" r="16" opacity="0.3"/><circle cx="24" cy="24" r="10" opacity="0.5"/><circle cx="24" cy="24" r="3"/><line x1="24" y1="2" x2="24" y2="12"/><line x1="24" y1="36" x2="24" y2="46"/><line x1="2" y1="24" x2="12" y2="24"/><line x1="36" y1="24" x2="46" y2="24"/></svg>,
                  zh: '方案咨询', de: 'Lösungsberatung', en: 'Solution Consulting',
                  descZh: '从场景识别到实施路径设计，帮助您以更可控的投入推进 AI 项目落地。',
                  descDe: 'Von der Szenarioerkennung bis zum Implementierungspfad — AI-Projekte kontrolliert umsetzen.',
                  descEn: 'From scenario identification to implementation path design — advance AI projects with controlled investment.' },
                { icon: <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="8" width="40" height="32" rx="3" opacity="0.4"/><line x1="4" y1="16" x2="44" y2="16" opacity="0.3"/><circle cx="10" cy="12" r="1.5" opacity="0.5"/><circle cx="16" cy="12" r="1.5" opacity="0.5"/><polyline points="12,24 18,28 12,32"/><line x1="22" y1="32" x2="32" y2="32" opacity="0.5"/></svg>,
                  zh: '定制应用', de: 'Massgeschneiderte Apps', en: 'Custom Apps',
                  descZh: '交付面向团队使用的 Web 应用与轻量化工具，确保方案可长期运行。',
                  descDe: 'Teamorientierte Web-Apps und schlanke Tools — langfristig betreibbar.',
                  descEn: 'Team-oriented web apps and lightweight tools — built for long-term operation.' },
              ].map((svc, i) => (
                <div className="hp-oohk-svc" key={i} style={{ animationDelay: `${i * 0.1}s` }}
                  data-tooltip={lang === 'zh' ? svc.descZh : lang === 'de' ? svc.descDe : svc.descEn}>
                  <span className="hp-oohk-svc-icon">{svc.icon}</span>
                  <span className="hp-oohk-svc-label">{lang === 'zh' ? svc.zh : lang === 'de' ? svc.de : svc.en}</span>
                </div>
              ))}
            </div>
            <span className="hp-oohk-showcase-cta">
              {lang === 'zh' ? '了解 OOHK →' : lang === 'de' ? 'Mehr über OOHK →' : 'Discover OOHK →'}
            </span>
          </Link>
        </section>

        {/* ═══ App Download ═══ */}
        <section className="hp-dl-section" ref={dlRef} data-reveal>
          <div className="hp-dl-card">
            <div className="hp-dl-info">
              <h2>{c.dlTitle}</h2>
              <p>{c.dlDesc}</p>
              <div className="hp-dl-stores">
                {/* Apple App Store — TODO: Replace href with actual App Store link */}
                <a href="#" className="hp-store-btn hp-store-apple" aria-label={c.dlApple} onClick={(e) => e.preventDefault()} style={{ position: 'relative' }}>
                  <svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
                  <div className="hp-store-text">
                    <span className="hp-store-small">Download on the</span>
                    <span className="hp-store-name">{c.dlApple}</span>
                  </div>
                </a>
                {/* Google Play — TODO: Replace href with actual Google Play link */}
                <a href="#" className="hp-store-btn hp-store-google" aria-label={c.dlGoogle} onClick={(e) => e.preventDefault()} style={{ position: 'relative' }}>
                  <svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M3.18 23.67c-.37-.2-.68-.6-.68-1.16V1.5c0-.55.3-.96.67-1.16l11.6 11.66L3.18 23.67zM15.72 12.95l-2.5 2.5 7.67 4.35c.7.4 1.4.04 1.56-.36l-6.73-6.49zM15.72 11.05l6.73-6.49c-.16-.4-.86-.76-1.56-.36l-7.67 4.35 2.5 2.5zM12.27 11.55L4.15.78c.1-.02.2-.03.3 0l10.32 5.86-2.5 4.91z"/></svg>
                  <div className="hp-store-text">
                    <span className="hp-store-small">GET IT ON</span>
                    <span className="hp-store-name">{c.dlGoogle}</span>
                  </div>
                </a>
                {/* PWA */}
                <a href="https://taxja.at" className="hp-store-btn hp-store-pwa" aria-label={c.dlPwa}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="22" height="22"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
                  <div className="hp-store-text">
                    <span className="hp-store-small">PWA</span>
                    <span className="hp-store-name">{c.dlPwa}</span>
                  </div>
                </a>
              </div>
            </div>
            {/* Phone mockup */}
            <div className="hp-dl-phone">
              <div className="hp-phone-frame">
                <div className="hp-phone-notch" />
                <div className="hp-phone-screen">
                  <div className="hp-phone-status">
                    <span>Taxja</span>
                    <span className="hp-phone-dot" />
                  </div>
                  <div className="hp-phone-row"><span className="hp-phone-label">📄</span><span>Lohnzettel 2025</span><span className="hp-phone-tag hp-phone-tag-ok">✓</span></div>
                  <div className="hp-phone-row"><span className="hp-phone-label">🏠</span><span>Mieteinnahmen Q1</span><span className="hp-phone-tag hp-phone-tag-ok">✓</span></div>
                  <div className="hp-phone-row"><span className="hp-phone-label">🧾</span><span>SVS Vorschreibung</span><span className="hp-phone-tag hp-phone-tag-new">NEW</span></div>
                  <div className="hp-phone-bar">
                    <div className="hp-phone-bar-fill" />
                  </div>
                  <div className="hp-phone-summary">
                    <span>€ 1.247,00</span>
                    <span className="hp-phone-summary-label">Gutschrift</span>
                  </div>
                </div>
              </div>
            </div>
            {/* QR code */}
            <div className="hp-dl-qr">
              <QRCanvas url="https://taxja.at" size={120} />
              <p>{c.dlScanHint}</p>
            </div>
          </div>
        </section>
      </div>

      {/* ═══ Footer ═══ */}
      <footer className="hp-footer">
        <div className="hp-footer-in">
          <span className="hp-footer-copy">&copy; {new Date().getFullYear()} Taxja by OOHK</span>
          <Link to="/company" className="hp-footer-oohk" aria-label="OOHK Company Page">
            <OohkOrb size={40} />
            <span className="hp-footer-oohk-text">OOHK</span>
          </Link>
          <div className="hp-footer-links">
            <Link to="/legal/impressum">Impressum</Link>
            <Link to="/legal/datenschutz">Datenschutz</Link>
            <Link to="/legal/agb">AGB</Link>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default HomePage;
