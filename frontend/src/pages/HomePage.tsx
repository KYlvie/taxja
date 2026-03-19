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
}

/* ── Data Rain Canvas (from CompanyPage) ── */
const DataRainCanvas = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let animId: number;
    const chars = 'TAXJA0123456789€§%ABCDEF@#&*<>{}[]';
    const fontSize = 20;
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
      hues = Array.from({ length: columns }, () => 260 + Math.random() * 30);
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
        ctx.font = `${fontSize}px "JetBrains Mono", "Fira Code", monospace`;
        ctx.fillStyle = `hsla(${hues[i]}, 55%, 65%, 0.5)`;
        ctx.shadowBlur = 5;
        ctx.shadowColor = `hsla(${hues[i]}, 50%, 55%, 0.3)`;
        ctx.fillText(char, x, y);
        ctx.shadowBlur = 0;
        for (let t = 1; t < 5; t++) {
          const trailY = y - t * fontSize;
          if (trailY > 0) {
            ctx.fillStyle = `hsla(${hues[i]}, 45%, 45%, ${0.15 * (1 - t / 5)})`;
            ctx.fillText(chars[Math.floor(Math.random() * chars.length)], x, trailY);
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
  return <canvas ref={canvasRef} className="hp-datarain" />;
};

/* ── Cursor Glow ── */
const CursorGlow = () => {
  const glowRef = useRef<HTMLDivElement>(null);
  const trailRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let mx = -200, my = -200, gx = -200, gy = -200, tx = -200, ty = -200;
    let animId: number;
    const onMove = (e: MouseEvent) => { mx = e.clientX; my = e.clientY; };
    window.addEventListener('mousemove', onMove);
    const animate = () => {
      gx += (mx - gx) * 0.35; gy += (my - gy) * 0.35;
      if (glowRef.current) glowRef.current.style.transform = `translate(${gx - 150}px, ${gy - 150}px)`;
      tx += (mx - tx) * 0.15; ty += (my - ty) * 0.15;
      if (trailRef.current) trailRef.current.style.transform = `translate(${tx - 200}px, ${ty - 200}px)`;
      animId = requestAnimationFrame(animate);
    };
    animate();
    return () => { cancelAnimationFrame(animId); window.removeEventListener('mousemove', onMove); };
  }, []);
  return (<>
    <div ref={glowRef} className="hp-cursor-glow" />
    <div ref={trailRef} className="hp-cursor-trail" />
  </>);
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
const copy: Record<SupportedLanguage, Copy> = {
  de: {
    badge: 'Jetzt verfügbar für 2022–2026',
    h1: 'Deine Steuer.\nKomplett automatisch. ',
    h1Highlights: ['KI-gestützt.', 'In Minuten.', 'Stressfrei.'],
    subtitle: '15+ Dokumenttypen per OCR erkennen, Transaktionen automatisch klassifizieren, Steuerberichte auf Knopfdruck — DSGVO-konform mit AES-256.',
    loginLabel: 'Anmelden',
    ctaPrimary: 'Kostenlos starten',
    ctaSecondary: 'Preise ansehen',
    stats: [
      { value: '15+', numericValue: 15, suffix: '+', label: 'Dokumenttypen (OCR)' },
      { value: '<5 Min', numericValue: 5, prefix: '<', suffix: ' Min', label: 'bis zum Überblick' },
      { value: '2022–2026', label: 'Steuerjahre' },
      { value: 'AES-256', label: 'Verschlüsselung' },
    ],
    trustBadges: ['DSGVO', 'AES-256', 'EU-Hosting', 'FinanzOnline'],
    showLabel: 'Live-Vorschau',
    showTitle: 'Deine Steuerberichte — automatisch generiert',
    showDesc: 'E/A-Rechnung, GuV, E1/E1a/E1b, L1/L1k, K1, U1, UVA, Saldenliste, Anlageverzeichnis — alles auf Knopfdruck.',
    showcaseReports: [
      { id: 'ea', icon: '📊', title: 'E/A-Rechnung 2025',
        headers: ['Datum', 'Beschreibung', 'Betrag', '✓'],
        rows: [['15.01', 'Gehalt Jänner', '€ 3.200,00', ''], ['10.03', 'Freelance Webdesign', '€ 1.800,00', ''], ['22.04', 'Mieteinnahmen Q1', '€ 2.700,00', ''], ['05.01', 'Home-Office Pauschale', '- € 300,00', '✓'], ['12.01', 'Laptop (Arbeitsmittel)', '- € 1.299,00', '✓'], ['01.04', 'Restaurant (privat)', '- € 45,00', '✗']],
        summary: [{ label: 'Einnahmen', value: '€ 17.300,00' }, { label: 'Ausgaben', value: '- € 3.069,90' }, { label: 'Betriebsergebnis', value: '€ 14.230,10', accent: true }],
      },
      { id: 'e1', icon: '🏛️', title: 'E1 Steuererklärung 2025',
        headers: ['KZ', 'Feld', 'Betrag'],
        rows: [['245', 'Einkünfte nichtselbst. Arbeit', '€ 45.000,00'], ['320', 'Einkünfte Gewerbebetrieb', '€ 28.650,00'], ['370', 'Einkünfte V+V', '€ 8.400,00'], ['717', 'Pendlerpauschale', '- € 1.356,00'], ['718', 'Home-Office Pauschale', '- € 300,00']],
        summary: [{ label: 'Gesamtbetrag Einkünfte', value: '€ 82.050,00' }, { label: 'Zu versteuerndes Einkommen', value: '€ 77.474,00', accent: true }],
      },
      { id: 'e1a', icon: '📝', title: 'E1a Beilage 2025',
        headers: ['KZ', 'Feld', 'Betrag'],
        rows: [['9040', 'Betriebseinnahmen', '€ 92.400,00'], ['9050', 'Wareneinkauf', '- € 12.300,00'], ['9060', 'Personalaufwand', '- € 38.500,00'], ['9070', 'AfA', '- € 4.200,00'], ['9080', 'Betriebsausgaben', '- € 8.750,00']],
        summary: [{ label: 'Gewinn/Verlust', value: '€ 28.650,00', accent: true }],
      },
      { id: 'e1b', icon: '🏠', title: 'E1b Vermietung 2025',
        headers: ['KZ', 'Feld', 'Betrag'],
        rows: [['400', 'Mieteinnahmen', '€ 14.400,00'], ['410', 'Betriebskosten-Anteil', '€ 2.160,00'], ['450', 'AfA Gebäude (1,5%)', '- € 3.000,00'], ['460', 'Instandhaltung', '- € 1.850,00'], ['470', 'Zinsen Kredit', '- € 2.400,00']],
        summary: [{ label: 'Einkünfte V+V', value: '€ 9.310,00', accent: true }],
      },
      { id: 'l1', icon: '👤', title: 'L1 Arbeitnehmerveranlagung 2025',
        headers: ['KZ', 'Feld', 'Betrag'],
        rows: [['210', 'Bruttobezüge lt. L16', '€ 45.000,00'], ['220', 'SV-Beiträge', '- € 8.145,00'], ['717', 'Pendlerpauschale', '- € 1.356,00'], ['718', 'Home-Office Pauschale', '- € 300,00']],
        summary: [{ label: 'Steuerbemessung', value: '€ 34.659,00' }, { label: 'Gutschrift', value: '€ 1.247,00', accent: true }],
      },
      { id: 'u1', icon: '📅', title: 'U1 Jahres-UVA 2025',
        headers: ['KZ', 'Position', 'Betrag'],
        rows: [['000', 'Gesamtbetrag Lieferungen', '€ 92.400,00'], ['029', 'Bemessungsgrundlage 20%', '€ 92.400,00'], ['060', 'USt 20%', '€ 18.480,00'], ['065', 'Vorsteuer', '- € 7.360,00']],
        summary: [{ label: 'Jahres-Zahllast', value: '€ 11.120,00', accent: true }],
      },
      { id: 'afa', icon: '🏗️', title: 'Anlageverzeichnis 2025',
        headers: ['Anlage', 'Ansch.-Wert', 'AfA p.a.', 'Buchwert'],
        rows: [['MacBook Pro 16"', '€ 2.999,00', '€ 999,67', '€ 1.000,00'], ['Büromöbel', '€ 1.800,00', '€ 138,46', '€ 1.384,62'], ['Gebäude (V+V)', '€ 200.000,00', '€ 3.000,00', '€ 182.000,00']],
        summary: [{ label: 'AfA gesamt', value: '€ 9.713,13' }, { label: 'Buchwert gesamt', value: '€ 207.459,62', accent: true }],
      },
    ],
    featKicker: 'Funktionen',
    featTitle: 'Alles was du für deine Steuer brauchst.',
    features: [
      { icon: 'doc', title: '15+ Dokumenttypen per OCR', desc: 'L1, L1k, E1, E1a, E1b, E1kv, Lohnzettel, Kontoauszug, Grundsteuer, SVS, Jahresabschluss, U1, UVA und mehr — automatisch erkannt und extrahiert.' },
      { icon: 'brain', title: 'KI-Klassifizierung mit Lerneffekt', desc: 'Regelbasiert, ML und LLM in einer Pipeline. Korrigierst du einmal, lernt das System und erstellt automatisch Regeln für die Zukunft.' },
      { icon: 'building', title: 'Immobilienverwaltung & AfA', desc: 'Kaufverträge, Mietverträge, Darlehen — alles verknüpft. AfA wird automatisch berechnet und als wiederkehrende Buchung angelegt.' },
      { icon: 'repeat', title: 'Wiederkehrende Transaktionen', desc: 'Miete, Versicherung, SVS-Beiträge — einmal einrichten, automatisch jeden Monat gebucht.' },
      { icon: 'chat', title: 'KI-Steuerassistent', desc: 'Steuerfragen direkt im Chat beantworten lassen. Der Assistent kennt deine Daten und österreichisches Steuerrecht.' },
      { icon: 'health', title: 'Steuer-Gesundheitscheck', desc: 'Fehlende Belege, vergessene Absetzbeträge, nahende Fristen — das System prüft und erinnert dich automatisch.' },
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
      { q: 'Nur für Angestellte?', a: 'Nein — Arbeitnehmer, Selbständige, Freiberufler, Vermieter und GmbH (K1) werden unterstützt.' },
      { q: 'Welche Dokumente werden erkannt?', a: 'Über 15 Typen: Lohnzettel, L1, E1, E1a, E1b, E1kv, Kontoauszüge, Grundsteuer, SVS, Jahresabschluss, U1, UVA, Kaufverträge, Mietverträge und mehr.' },
      { q: 'Wie sicher sind meine Daten?', a: 'AES-256 Verschlüsselung, DSGVO-konform, alle Daten in der EU. Keine Tracking-Cookies.' },
    ],
    ctaKicker: 'Bereit?',
    ctaTitle: 'Deine Steuer verdient Automatisierung.',
    ctaBody: 'Kostenloses Konto in unter 2 Minuten — KI erledigt den Rest.',
    dlTitle: 'Taxja auch unterwegs nutzen',
    dlDesc: 'Belege fotografieren, Ausgaben erfassen und Steuerstatus prüfen — direkt auf dem Handy.',
    dlScanHint: 'QR-Code scannen zum Herunterladen',
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: 'Web-App öffnen',
  },
  en: {
    badge: 'Now available for 2022–2026',
    h1: 'Your taxes.\nFully automated. ',
    h1Highlights: ['AI-powered.', 'In minutes.', 'Stress-free.'],
    subtitle: '15+ document types via OCR, auto-classify transactions, generate tax reports instantly — GDPR-compliant with AES-256.',
    loginLabel: 'Sign in',
    ctaPrimary: 'Start Free',
    ctaSecondary: 'See Pricing',
    stats: [
      { value: '15+', numericValue: 15, suffix: '+', label: 'document types (OCR)' },
      { value: '<5 min', numericValue: 5, prefix: '<', suffix: ' min', label: 'to first overview' },
      { value: '2022–2026', label: 'tax years' },
      { value: 'AES-256', label: 'encryption' },
    ],
    trustBadges: ['GDPR', 'AES-256', 'EU-Hosted', 'FinanzOnline'],
    showLabel: 'Live Preview',
    showTitle: 'Your tax reports — auto-generated',
    showDesc: 'EA, P&L, E1/E1a/E1b, L1/L1k, K1, U1, VAT, trial balance, asset register — all at the click of a button.',
    showcaseReports: [
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
    ],
    featKicker: 'Features',
    featTitle: 'Everything you need for your taxes.',
    features: [
      { icon: 'doc', title: '15+ Document Types via OCR', desc: 'L1, L1k, E1, E1a, E1b, E1kv, Lohnzettel, bank statements, property tax, SVS, annual accounts, U1, UVA and more — auto-recognized and extracted.' },
      { icon: 'brain', title: 'AI Classification with Learning', desc: 'Rule-based, ML and LLM in one pipeline. Correct once, the system learns and creates rules for the future automatically.' },
      { icon: 'building', title: 'Property Management & Depreciation', desc: 'Purchase contracts, rental contracts, loans — all linked. Depreciation is auto-calculated and booked as recurring transactions.' },
      { icon: 'repeat', title: 'Recurring Transactions', desc: 'Rent, insurance, SVS contributions — set up once, automatically booked every month.' },
      { icon: 'chat', title: 'AI Tax Assistant', desc: 'Get tax questions answered directly in chat. The assistant knows your data and Austrian tax law.' },
      { icon: 'health', title: 'Tax Health Check', desc: 'Missing receipts, forgotten deductions, approaching deadlines — the system checks and reminds you automatically.' },
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
      { q: 'Only for employees?', a: 'No — employees, self-employed, freelancers, landlords and GmbH (K1) are all supported.' },
      { q: 'Which documents are recognized?', a: 'Over 15 types: Lohnzettel, L1, E1, E1a, E1b, E1kv, bank statements, property tax, SVS, annual accounts, U1, UVA, purchase contracts, rental contracts and more.' },
      { q: 'How secure is my data?', a: 'AES-256 encryption, GDPR-compliant, all data stays in the EU. No tracking cookies.' },
    ],
    ctaKicker: 'Ready?',
    ctaTitle: 'Your taxes deserve automation.',
    ctaBody: 'Free account in under 2 minutes — AI handles the rest.',
    dlTitle: 'Take Taxja on the go',
    dlDesc: 'Snap receipts, log expenses and check your tax status — right from your phone.',
    dlScanHint: 'Scan QR code to download',
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: 'Open Web App',
  },
  zh: {
    badge: '已支持 2022–2026 税年',
    h1: '奥地利税务管理，',
    h1Highlights: ['AI 驱动。', '全自动。', '几分钟搞定。'],
    subtitle: '15+ 文档类型 OCR 识别、交易自动分类、一键生成报税表 — GDPR 合规，AES-256 加密。',
    loginLabel: '登录',
    ctaPrimary: '免费开始',
    ctaSecondary: '查看价格',
    stats: [
      { value: '15+', numericValue: 15, suffix: '+', label: '文档类型 (OCR)' },
      { value: '<5 分钟', numericValue: 5, prefix: '<', suffix: ' 分钟', label: '获得概览' },
      { value: '2022–2026', label: '覆盖税年' },
      { value: 'AES-256', label: '加密标准' },
    ],
    trustBadges: ['GDPR', 'AES-256', 'EU 托管', 'FinanzOnline'],
    showLabel: '实时预览',
    showTitle: '全部税务报表 — 自动生成',
    showDesc: '收支报表、损益表、E1/E1a/E1b、L1/L1k、K1、U1、UVA、科目余额表、固定资产清单 — 一键生成。',
    showcaseReports: [
      { id: 'ea', icon: '📊', title: '收支报表 2025',
        headers: ['日期', '描述', '金额', '✓'],
        rows: [['01.15', '1月工资', '€ 3.200,00', ''], ['03.10', '自由职业 网页设计', '€ 1.800,00', ''], ['04.22', '租金收入 Q1', '€ 2.700,00', ''], ['01.05', '居家办公补贴', '- € 300,00', '✓'], ['01.12', '笔记本电脑', '- € 1.299,00', '✓'], ['04.01', '餐厅（私人）', '- € 45,00', '✗']],
        summary: [{ label: '收入', value: '€ 17.300,00' }, { label: '支出', value: '- € 3.069,90' }, { label: '经营成果', value: '€ 14.230,10', accent: true }],
      },
      { id: 'e1', icon: '🏛️', title: 'E1 报税表 2025',
        headers: ['KZ', '字段', '金额'],
        rows: [['245', '工资收入', '€ 45.000,00'], ['320', '经营所得', '€ 28.650,00'], ['370', '租赁收入', '€ 8.400,00'], ['717', '通勤补贴', '- € 1.356,00'], ['718', '居家办公补贴', '- € 300,00']],
        summary: [{ label: '总收入', value: '€ 82.050,00' }, { label: '应税所得', value: '€ 77.474,00', accent: true }],
      },
      { id: 'e1a', icon: '📝', title: 'E1a 个体经营附表 2025',
        headers: ['KZ', '字段', '金额'],
        rows: [['9040', '营业收入', '€ 92.400,00'], ['9050', '采购成本', '- € 12.300,00'], ['9060', '人工成本', '- € 38.500,00'], ['9070', '折旧', '- € 4.200,00'], ['9080', '经营费用', '- € 8.750,00']],
        summary: [{ label: '盈亏', value: '€ 28.650,00', accent: true }],
      },
      { id: 'e1b', icon: '🏠', title: 'E1b 租赁收入附表 2025',
        headers: ['KZ', '字段', '金额'],
        rows: [['400', '租金收入', '€ 14.400,00'], ['410', '物业费分摊', '€ 2.160,00'], ['450', '建筑折旧 (1,5%)', '- € 3.000,00'], ['460', '维修费', '- € 1.850,00'], ['470', '贷款利息', '- € 2.400,00']],
        summary: [{ label: '租赁净收入', value: '€ 9.310,00', accent: true }],
      },
      { id: 'l1', icon: '👤', title: 'L1 雇员报税表 2025',
        headers: ['KZ', '字段', '金额'],
        rows: [['210', '工资总额 (L16)', '€ 45.000,00'], ['220', '社保缴费', '- € 8.145,00'], ['717', '通勤补贴', '- € 1.356,00'], ['718', '居家办公补贴', '- € 300,00']],
        summary: [{ label: '计税基础', value: '€ 34.659,00' }, { label: '退税金额', value: '€ 1.247,00', accent: true }],
      },
      { id: 'u1', icon: '📅', title: 'U1 年度增值税申报 2025',
        headers: ['KZ', '项目', '金额'],
        rows: [['000', '供应总额', '€ 92.400,00'], ['029', '20%税基', '€ 92.400,00'], ['060', '增值税 20%', '€ 18.480,00'], ['065', '进项税', '- € 7.360,00']],
        summary: [{ label: '年度应缴', value: '€ 11.120,00', accent: true }],
      },
      { id: 'afa', icon: '🏗️', title: '固定资产清单 2025',
        headers: ['资产', '购置价', '年折旧', '账面价值'],
        rows: [['MacBook Pro 16"', '€ 2.999,00', '€ 999,67', '€ 1.000,00'], ['办公家具', '€ 1.800,00', '€ 138,46', '€ 1.384,62'], ['出租房产', '€ 200.000,00', '€ 3.000,00', '€ 182.000,00']],
        summary: [{ label: '折旧合计', value: '€ 9.713,13' }, { label: '账面价值合计', value: '€ 207.459,62', accent: true }],
      },
    ],
    featKicker: '核心功能',
    featTitle: '报税所需，一应俱全。',
    features: [
      { icon: 'doc', title: '15+ 文档类型 OCR 识别', desc: 'L1、L1k、E1、E1a、E1b、E1kv、工资单、银行流水、房产税、SVS、年报、U1、UVA 等 — 自动识别并提取数据。' },
      { icon: 'brain', title: 'AI 分类 + 自动学习', desc: '规则引擎、机器学习、LLM 三级管道。纠正一次，系统自动学习并创建规则。' },
      { icon: 'building', title: '房产管理 & 折旧计算', desc: '购房合同、租赁合同、贷款 — 全部关联。折旧自动计算并生成定期交易。' },
      { icon: 'repeat', title: '定期交易自动记账', desc: '房租、保险、SVS 社保 — 设置一次，每月自动入账。' },
      { icon: 'chat', title: 'AI 税务助手', desc: '在聊天中直接提问税务问题。助手了解你的数据和奥地利税法。' },
      { icon: 'health', title: '税务健康检查', desc: '缺少凭证、遗漏抵扣、临近截止日期 — 系统自动检查并提醒。' },
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
      { q: '只适合上班族吗？', a: '不是 — 雇员、自由职业者、个体经营者、房东和 GmbH (K1) 都支持。' },
      { q: '能识别哪些文档？', a: '超过 15 种：工资单、L1、E1、E1a、E1b、E1kv、银行流水、房产税、SVS、年报、U1、UVA、购房合同、租赁合同等。' },
      { q: '数据安全吗？', a: 'AES-256 加密，GDPR 合规，所有数据存储在欧盟。不使用追踪 Cookie。' },
    ],
    ctaKicker: '准备好了？',
    ctaTitle: '你的税务值得自动化。',
    ctaBody: '2 分钟内免费注册 — AI 搞定剩下的。',
    dlTitle: '随时随地使用 Taxja',
    dlDesc: '拍照上传凭证、记录支出、查看税务状态 — 手机上就能完成。',
    dlScanHint: '扫描二维码下载',
    dlApple: 'App Store',
    dlGoogle: 'Google Play',
    dlPwa: '打开网页版',
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
  const c = copy[lang] || copy.en;
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
      <DataRainCanvas />
      <CursorGlow />
      <div className="hp-noise" />
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
            <span className="hp-trust-badge" key={i}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="M9 12l2 2 4-4" /></svg>
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
                onClick={() => setOpenFaq(openFaq === i ? null : i)}
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

        {/* ═══ App Download ═══ */}
        <section className="hp-dl-section" ref={dlRef} data-reveal>
          <div className="hp-dl-card">
            <div className="hp-dl-info">
              <h2>{c.dlTitle}</h2>
              <p>{c.dlDesc}</p>
              <div className="hp-dl-stores">
                {/* Apple App Store */}
                <a href="#" className="hp-store-btn hp-store-apple" aria-label={c.dlApple}>
                  <svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
                  <div className="hp-store-text">
                    <span className="hp-store-small">Download on the</span>
                    <span className="hp-store-name">{c.dlApple}</span>
                  </div>
                </a>
                {/* Google Play */}
                <a href="#" className="hp-store-btn hp-store-google" aria-label={c.dlGoogle}>
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
          <div className="hp-footer-links">
            <Link to="/legal/impressum">Impressum</Link>
            <Link to="/legal/datenschutz">Datenschutz</Link>
            <Link to="/legal/agb">AGB</Link>
            <Link to="/company">OOHK</Link>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default HomePage;
