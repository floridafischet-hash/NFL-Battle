import clsx from "clsx";

export function BrandMark({ size = 40, className }: { size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} className={className} aria-hidden>
      <defs>
        <linearGradient id="bm-shield" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ef3349" />
          <stop offset="0.5" stopColor="#1a2340" />
          <stop offset="1" stopColor="#2f7bff" />
        </linearGradient>
        <linearGradient id="bm-gold" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffe08a" />
          <stop offset="1" stopColor="#f5c451" />
        </linearGradient>
      </defs>
      <path d="M32 3 L58 11 V31 C58 47 47 57 32 61 C17 57 6 47 6 31 V11 Z" fill="url(#bm-shield)" stroke="url(#bm-gold)" strokeWidth="3" />
      <path d="M15 20 H24 V28 H30 M15 36 H24 V28 M49 20 H40 V28 H34 M49 36 H40 V28" fill="none" stroke="#fff" strokeOpacity=".75" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      <ellipse cx="32" cy="44" rx="9" ry="5.5" fill="#8b4513" stroke="#fff" strokeWidth="1.2" />
      <path d="M27.5 44 H36.5 M30 42.4 V45.6 M32 42.4 V45.6 M34 42.4 V45.6" stroke="#fff" strokeWidth="1" strokeLinecap="round" />
      <circle cx="32" cy="28" r="3.2" fill="url(#bm-gold)" />
    </svg>
  );
}

export function Brand({ compact, className }: { compact?: boolean; className?: string }) {
  return (
    <div className={clsx("flex items-center gap-3", className)}>
      <BrandMark size={compact ? 34 : 42} />
      <div className="leading-none">
        <p className="display text-[11px] font-semibold tracking-[0.3em] text-slate-400">NFL</p>
        <p className="display text-lg font-bold tracking-wide text-white">
          Bracket <span className="text-gold">Battle</span>
        </p>
      </div>
    </div>
  );
}
