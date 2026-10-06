const TZ = "Europe/Berlin";

const dayFmt = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", timeZone: TZ });
const timeFmt = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: TZ });
const fullFmt = new Intl.DateTimeFormat("de-DE", {
  weekday: "long",
  day: "2-digit",
  month: "long",
  year: "numeric",
  timeZone: TZ,
});
const dateTimeFmt = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  timeZone: TZ,
});

export function kickoffShort(iso: string | null | undefined): string {
  if (!iso) return "Termin offen";
  const d = new Date(iso);
  return `${dayFmt.format(d).replace(",", "")} · ${timeFmt.format(d)}`;
}

export function dateLong(iso: string | null | undefined): string {
  return iso ? fullFmt.format(new Date(iso)) : "Termin offen";
}

export function timeOnly(iso: string | null | undefined): string {
  return iso ? `${timeFmt.format(new Date(iso))} Uhr` : "–";
}

export function dateTime(iso: string | null | undefined): string {
  return iso ? dateTimeFmt.format(new Date(iso)) : "–";
}

export function relativeTime(iso: string, now = Date.now()): string {
  const diff = Math.round((now - new Date(iso).getTime()) / 1000);
  if (diff < 45) return "gerade eben";
  if (diff < 3600) return `vor ${Math.round(diff / 60)} Min.`;
  if (diff < 86400) return `vor ${Math.round(diff / 3600)} Std.`;
  if (diff < 7 * 86400) return `vor ${Math.round(diff / 86400)} Tg.`;
  return dayFmt.format(new Date(iso));
}

export function chatTime(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return sameDay ? timeFmt.format(d) : `${dayFmt.format(d).replace(",", "")} ${timeFmt.format(d)}`;
}

export interface Countdown {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  done: boolean;
}

export function countdown(target: string | null | undefined, now = Date.now()): Countdown {
  if (!target) return { days: 0, hours: 0, minutes: 0, seconds: 0, done: true };
  let ms = new Date(target).getTime() - now;
  if (ms <= 0) return { days: 0, hours: 0, minutes: 0, seconds: 0, done: true };
  const days = Math.floor(ms / 86_400_000);
  ms -= days * 86_400_000;
  const hours = Math.floor(ms / 3_600_000);
  ms -= hours * 3_600_000;
  const minutes = Math.floor(ms / 60_000);
  ms -= minutes * 60_000;
  return { days, hours, minutes, seconds: Math.floor(ms / 1000), done: false };
}

export function roman(n: number): string {
  const map: [number, string][] = [
    [1000, "M"], [900, "CM"], [500, "D"], [400, "CD"], [100, "C"], [90, "XC"],
    [50, "L"], [40, "XL"], [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"],
  ];
  let out = "";
  for (const [value, sym] of map) {
    while (n >= value) {
      out += sym;
      n -= value;
    }
  }
  return out;
}

/** Super Bowl number of a season (the 2026 season ends with Super Bowl LXI). */
export function superBowlName(seasonYear: number): string {
  return `Super Bowl ${roman(seasonYear - 1965)}`;
}

export function percent(value: number): string {
  return `${value.toLocaleString("de-DE", { maximumFractionDigits: 1 })} %`;
}

export function pointsLabel(n: number): string {
  return n === 1 ? "1 Punkt" : `${n} Punkte`;
}
