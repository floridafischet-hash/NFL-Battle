"use client";

import clsx from "clsx";
import { ArrowRight, MessageSquare } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { BracketBoard } from "@/components/bracket/BracketBoard";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { LeaderboardCompact, NextGameCard, RecentResults, UserStatsCard } from "@/components/dashboard/Widgets";
import { Button, Card, EmptyState, Loading, Tabs } from "@/components/ui";
import { slotsFromMatches, withOrigins } from "@/lib/bracket";
import { superBowlName } from "@/lib/format";
import { useBracket, useDashboard, useSeasonMatches } from "@/lib/queries";

type View = "mine" | "official";

export default function DashboardPage() {
  const router = useRouter();
  const dashboard = useDashboard();
  const season = dashboard.data?.season ?? null;
  const [view, setView] = useState<View>("mine");
  const bracket = useBracket(season?.id ?? null, "me");
  const matches = useSeasonMatches(view === "official" ? (season?.id ?? null) : null);

  const official = useMemo(() => {
    if (!matches.data || !bracket.data) return null;
    return withOrigins(slotsFromMatches(matches.data), bracket.data.byes);
  }, [matches.data, bracket.data]);

  if (dashboard.isLoading) return <Loading label="Dashboard lädt …" />;
  if (!season) {
    return (
      <Card>
        <EmptyState title="Noch keine Saison">
          Ein Admin muss zuerst eine Saison mit Teams und Paarungen anlegen. Danach erscheint hier der Playoff-Bracket.
        </EmptyState>
      </Card>
    );
  }
  const d = dashboard.data!;
  const slots = view === "mine" ? bracket.data?.slots : official ?? undefined;
  const champion = season.champion_team?.id ?? (view === "mine" ? (bracket.data?.champion_team_id ?? null) : null);

  return (
    <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-5">
        {/* Hero / bracket */}
        <section className="glass relative overflow-hidden rounded-3xl">
          <div className="pointer-events-none absolute -top-24 left-0 h-48 w-1/2 bg-gradient-to-r from-afc/25 to-transparent blur-3xl" />
          <div className="pointer-events-none absolute -top-24 right-0 h-48 w-1/2 bg-gradient-to-l from-nfc/25 to-transparent blur-3xl" />
          <div className="relative flex flex-col gap-3 px-4 pt-5 sm:flex-row sm:items-end sm:justify-between sm:px-6">
            <div>
              <p className="text-[11px] font-bold tracking-[0.35em] text-slate-400">NFL PLAYOFFS {season.name}</p>
              <h1 className="display text-3xl font-bold text-white sm:text-5xl">
                <span className="text-afc-soft">AFC</span> <span className="text-slate-500">·</span>{" "}
                <span className="text-gradient-gold">{superBowlName(season.year)}</span> <span className="text-slate-500">·</span>{" "}
                <span className="text-nfc-soft">NFC</span>
              </h1>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Tabs<View>
                tabs={[
                  { value: "mine", label: "Mein Tipp" },
                  { value: "official", label: "Offizieller Stand" },
                ]}
                value={view}
                onChange={setView}
              />
              <Link href="/bracket">
                <Button variant="primary" size="sm" className="min-h-10">
                  {d.me && d.me.missing_open_picks > 0 ? `Jetzt tippen (${d.me.missing_open_picks})` : "Bracket bearbeiten"}
                  <ArrowRight className="size-4" />
                </Button>
              </Link>
            </div>
          </div>
          <div className="relative px-2 pt-4 pb-4 sm:px-4">
            {slots && bracket.data ? (
              <BracketBoard
                slots={slots}
                byes={bracket.data.byes}
                mode={view === "mine" ? "view" : "live"}
                size="compact"
                fit
                seasonYear={season.year}
                scoreTips={season.score_tips_enabled}
                championTeamId={champion}
                championLabel={season.champion_team || view === "official" ? "Champion" : "Dein Champion"}
                onOpen={(slot) => router.push(`/spiele/${slot.match_id}`)}
              />
            ) : (
              <Loading label="Bracket lädt …" />
            )}
            <div className="mt-2 flex flex-wrap items-center justify-center gap-x-5 gap-y-1 text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5">
                <span className="h-0.5 w-6 rounded bg-afc shadow-[0_0_6px_#ef3349]" /> weitergekommen
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-0.5 w-6 border-t-2 border-dashed border-nfc" /> dein Tipp
              </span>
              <span className="flex items-center gap-1.5">
                <span className="flex size-3.5 items-center justify-center rounded-full bg-gold text-[8px] text-ink-950">✓</span> getippt
              </span>
            </div>
          </div>
        </section>

        <div className="2xl:hidden">
          <NextGameCard match={d.next_match} />
        </div>

        <div className={clsx("grid gap-5 md:grid-cols-2 xl:grid-cols-3")}>
          {d.me && <UserStatsCard me={d.me} />}
          <LeaderboardCompact rows={d.leaderboard ?? []} />
          <RecentResults matches={d.recent_results ?? []} />
        </div>
      </div>

      <aside className="min-w-0 space-y-5">
        <div className="hidden 2xl:block">
          <NextGameCard match={d.next_match} />
        </div>
        <Card
          title={
            <span className="flex items-center gap-2">
              <MessageSquare className="size-4 text-gold" /> Playoff Chat
            </span>
          }
          action={
            <Link href="/chat" className="text-xs font-semibold text-gold hover:underline">
              Vollbild
            </Link>
          }
          bodyClassName="p-0"
        >
          <ChatPanel compact className="h-[520px]" />
        </Card>
      </aside>
    </div>
  );
}
