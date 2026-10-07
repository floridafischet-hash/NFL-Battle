"use client";

import clsx from "clsx";
import { useState } from "react";

import type { Team } from "@/lib/types";

const FALLBACK = "/logos/TBD.svg";

/** Team logo from the team's configurable logo_url (never hard-coded per component). */
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
  const [failed, setFailed] = useState(false);
  const src = !team ? FALLBACK : failed || !team.logo_url ? FALLBACK : team.logo_url;
  return (
    <img
      src={src}
      alt={team ? team.name : "Noch offen"}
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      draggable={false}
      onError={() => setFailed(true)}
      className={clsx("shrink-0 object-contain select-none", className)}
      style={{
        width: size,
        height: size,
        filter: glow && team ? `drop-shadow(0 0 ${Math.round(size / 4)}px ${team.primary_color}aa)` : undefined,
      }}
    />
  );
}
