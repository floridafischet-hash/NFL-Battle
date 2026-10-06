"use client";

import clsx from "clsx";

const PALETTE = ["#ef3349", "#2f7bff", "#f5c451", "#22c55e", "#a855f7", "#f97316", "#06b6d4", "#ec4899"];

function colorFor(name: string): string {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

export function Avatar({
  user,
  size = 36,
  className,
  ring,
}: {
  user: { display_name: string; avatar_url?: string | null; is_bot?: boolean };
  size?: number;
  className?: string;
  ring?: boolean;
}) {
  const style = { width: size, height: size };
  if (user.is_bot) {
    return (
      <div
        style={style}
        className={clsx(
          "flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-afc via-ink-800 to-nfc ring-2 ring-gold/70",
          className,
        )}
        aria-label="NFL Bot"
      >
        <svg viewBox="0 0 24 24" style={{ width: size * 0.6, height: size * 0.6 }} aria-hidden>
          <ellipse cx="12" cy="12" rx="10" ry="6.2" transform="rotate(-35 12 12)" fill="#8b4513" stroke="#fff" strokeWidth="0.8" />
          <path d="M8.6 15.4 15.4 8.6M10 12.6l1.4 1.4M11.4 11.2l1.4 1.4M12.8 9.8l1.4 1.4" stroke="#fff" strokeWidth="1" strokeLinecap="round" />
        </svg>
      </div>
    );
  }
  if (user.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt={user.display_name}
        style={style}
        className={clsx("shrink-0 rounded-full object-cover", ring && "ring-2 ring-gold", className)}
      />
    );
  }
  const initials = user.display_name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  const color = colorFor(user.display_name);
  return (
    <div
      style={{ ...style, background: `linear-gradient(135deg, ${color}, ${color}66)`, fontSize: size * 0.4 }}
      className={clsx(
        "display flex shrink-0 items-center justify-center rounded-full font-bold text-white",
        ring && "ring-2 ring-gold",
        className,
      )}
      aria-label={user.display_name}
    >
      {initials}
    </div>
  );
}
