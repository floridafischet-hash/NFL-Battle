"use client";

import clsx from "clsx";
import { CheckCircle2, GitCompareArrows, Lock } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { TeamLogo } from "@/components/TeamLogo";
import { Button, Card, EmptyState, Loading, PageHeader, Select } from "@/components/ui";
import { useMe } from "@/lib/auth";
import { useBracketsOverview, useSelectedSeason } from "@/lib/queries";

export default function AllBracketsPage() {
  const me = useMe();
  const router = useRouter();
  const [selected, setSelected] = useState<number | null>(null);
  const { id, season, seasons } = useSelectedSeason(selected);
  const overview = useBracketsOverview(id);
  const [a, setA] = useState<string>("me");
  const [b, setB] = useState<string>("");
  const entries = overview.data ?? [];
  const others = entries.filter((e) => !e.is_me);

  return (
    <div className="space-y-5">
      <PageHeader title="Alle Brackets" subtitle="Tippbäume deiner Freunde – Tipps werden pro Spiel erst mit dem Tipp-Lock aufgedeckt.">
        {seasons.length > 1 && (
          <Select value={id ?? ""} onChange={(e) => setSelected(Number(e.target.value))} aria-label="Saison wählen" className="w-40">
            {seasons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        )}
      </PageHeader>

      <Card title={<span className="flex items-center gap-2"><GitCompareArrows className="size-4 text-gold" /> Brackets vergleichen</span>} accent="gold">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <Select label="Spieler A" value={a} onChange={(e) => setA(e.target.value)}>
            <option value="me">{me.display_name} (du)</option>
            {others.map((e) => (
              <option key={e.user.id} value={e.user.id}>
                {e.user.display_name}
              </option>
            ))}
          </Select>
          <span className="display hidden pb-3 text-lg font-bold text-slate-500 sm:block">VS</span>
          <Select label="Spieler B" value={b} onChange={(e) => setB(e.target.value)}>
            <option value="">– wählen –</option>
            {entries
              .filter((e) => (a === "me" ? !e.is_me : e.user.id !== a))
              .map((e) => (
                <option key={e.user.id} value={e.is_me ? "me" : e.user.id}>
                  {e.user.display_name}
                  {e.is_me ? " (du)" : ""}
                </option>
              ))}
          </Select>
          <Button variant="primary" disabled={!b || !id} onClick={() => router.push(`/brackets/vergleich?season=${id}&a=${a}&b=${b}`)} className="shrink-0">
            Vergleichen
          </Button>
        </div>
      </Card>

      {overview.isLoading && <Loading />}
      {!overview.isLoading && entries.length === 0 && (
        <Card>
          <EmptyState title="Noch keine Brackets" />
        </Card>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {entries.map((e) => (
          <Link
            key={e.user.id}
            href={e.is_me ? "/bracket" : `/brackets/${e.user.id}?season=${id}`}
            className={clsx("glass group rounded-2xl p-4 transition hover:-translate-y-0.5 hover:border-white/20", e.is_me && "ring-1 ring-gold/40")}
          >
            <div className="flex items-center gap-3">
              <Avatar user={e.user} size={48} ring={e.is_me} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-white">
                  {e.user.display_name} {e.is_me && <span className="text-xs text-gold">(du)</span>}
                </p>
                <p className="text-xs text-slate-400">
                  {e.rank ? `Rang ${e.rank} · ` : ""}
                  {e.points} Punkte
                </p>
              </div>
              {e.submitted_at && <CheckCircle2 className="size-5 text-emerald-400" aria-label="abgegeben" />}
            </div>
            <div className="mt-4 flex items-center justify-between gap-3">
              <div className="flex-1">
                <div className="mb-1 flex justify-between text-[11px] text-slate-400">
                  <span>Getippt</span>
                  <span className="tabular-nums">{e.picks_count}/13</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
                  <div className="h-full rounded-full bg-gradient-to-r from-afc via-gold to-nfc" style={{ width: `${(e.picks_count / 13) * 100}%` }} />
                </div>
                {season?.status !== "COMPLETED" && e.missing_open_picks > 0 && (
                  <p className="mt-1 text-[11px] text-amber-300">{e.missing_open_picks} offene Tipps</p>
                )}
              </div>
              <div className="flex flex-col items-center">
                {e.champion ? (
                  <TeamLogo team={e.champion} size={40} glow />
                ) : (
                  <span className="flex size-10 items-center justify-center rounded-full bg-white/5 text-slate-500" title="Champion-Tipp wird mit dem Super-Bowl-Lock sichtbar">
                    <Lock className="size-4" />
                  </span>
                )}
                <span className="mt-0.5 text-[9px] font-bold tracking-widest text-gold">CHAMPION</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
