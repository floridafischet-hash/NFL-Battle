"use client";

import clsx from "clsx";
import { useEffect, useState } from "react";

import type { Team } from "@/lib/types";

const FALLBACK = "/logos/TBD.svg";

/** Team logo from the team's configurable logo_url (never hard-coded per component). If the image
 * cannot be loaded (e.g. the logo CDN is unreachable) the neutral crest of the team is shown. */
export function TeamLogo({
  team,
  size = 32,
  className,
  glow,
}: {
  team: Pick<Team, "logo_url" | "abbreviation" | "name" | "primary_color"> | null | undefined;
  size?: number;
  className?: string;
  glow?: boolean;
}) {
  const [failures, setFailures] = useState(0);
  useEffect(() => setFailures(0), [team?.logo_url]);
  const neutral = team ? `/logos/${team.abbreviation}.svg` : FALLBACK;
  const candidates = team ? [team.logo_url, neutral, FALLBACK].filter((u): u is string => !!u) : [FALLBACK];
  const src = candidates[Math.min(failures, candidates.length - 1)];
  return (
    <img
      src={src}
      alt={team ? team.name : "Noch offen"}
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      draggable={false}
      referrerPolicy="no-referrer"
      onError={() => setFailures((n) => (n < candidates.length - 1 ? n + 1 : n))}
      className={clsx("shrink-0 object-contain select-none", className)}
      style={{
        width: size,
        height: size,
        filter: glow && team ? `drop-shadow(0 0 ${Math.round(size / 4)}px ${team.primary_color}aa)` : undefined,
      }}
    />
  );
}
