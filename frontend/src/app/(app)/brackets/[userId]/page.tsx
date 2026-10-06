"use client";

import { ArrowLeft, EyeOff } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { Avatar } from "@/components/Avatar";
import { BracketBoard } from "@/components/bracket/BracketBoard";
import { Card, ErrorBox, Loading, PageHeader, StatTile } from "@/components/ui";
import { useBracket, useSelectedSeason } from "@/lib/queries";

function UserBracket() {
  const params = useParams<{ userId: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const seasonParam = search.get("season");
  const { id, season } = useSelectedSeason(seasonParam ? Number(seasonParam) : null);
  const bracket = useBracket(id, params.userId);

  if (bracket.isLoading || !season) return <Loading />;
  if (bracket.error) return <ErrorBox error={bracket.error} />;
  const view = bracket.data!;
  const hidden = view.slots.filter((s) => s.pick_state === "hidden").length;

  return (
    <div className="space-y-5">
      <Link href="/brackets" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white">
        <ArrowLeft className="size-4" /> Alle Brackets
      </Link>
      <PageHeader title={`Bracket von ${view.user.display_name}`} subtitle={`Saison ${season.name}`}>
        <Avatar user={view.user} size={48} />
      </PageHeader>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Punkte" value={view.points} tone="gold" />
        <StatTile label="Rang" value={view.rank ? `#${view.rank}` : "–"} />
        <StatTile label="Getippt" value={`${view.picks_count}/13`} />
        <StatTile label="Verdeckt" value={hidden} hint="bis zum Tipp-Lock" />
      </div>
      {hidden > 0 && !view.full_visibility && (
        <p className="flex items-center gap-2 rounded-xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-slate-300">
          <EyeOff className="size-4 text-slate-400" /> {hidden} Tipps sind noch verdeckt – sie werden mit dem jeweiligen Tipp-Lock sichtbar (Schutz gegen Abschreiben).
        </p>
      )}
      <Card accent="gold" bodyClassName="p-3 sm:p-5">
        <BracketBoard
          slots={view.slots}
          byes={view.byes}
          mode="view"
          seasonYear={season.year}
          scoreTips={season.score_tips_enabled}
          championTeamId={season.champion_team?.id ?? view.champion_team_id}
          championLabel={season.champion_team ? "Champion" : `Champion-Tipp`}
          onOpen={(slot) => router.push(`/spiele/${slot.match_id}`)}
        />
      </Card>
    </div>
  );
}

export default function UserBracketPage() {
  return (
    <Suspense fallback={<Loading />}>
      <UserBracket />
    </Suspense>
  );
}
