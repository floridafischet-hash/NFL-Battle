"use client";

import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, Lock } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { BracketBoard } from "@/components/bracket/BracketBoard";
import { TeamLogo } from "@/components/TeamLogo";
import { Card, ErrorBox, Loading, PageHeader, Tabs } from "@/components/ui";
import { get } from "@/lib/api";
import { ROUND_TITLES, slotLabel } from "@/lib/bracket";
import { useSelectedSeason } from "@/lib/queries";
import type { BracketSlot, BracketView, Distribution, Team } from "@/lib/types";

interface CompareData {
  a: BracketView;
  b: BracketView;
  diff: { slot: string; state: "same" | "different" | "hidden" | "missing" }[];
  distribution: Distribution[];
}

function PickCell({ slot }: { slot: BracketSlot }) {
  if (slot.pick_state === "hidden")
    return (
      <span className="flex items-center gap-1.5 text-xs text-slate-500">
        <Lock className="size-3.5" /> verdeckt
      </span>
    );
  if (!slot.pick) return <span className="text-xs text-slate-500">kein Tipp</span>;
  const team = [slot.home, slot.away].find((t) => t?.id === slot.pick?.winner_team_id);
  return (
    <span className="flex items-center gap-2">
      <TeamLogo team={team ?? null} size={26} />
      <span className="text-sm font-semibold text-white">{team?.short_name ?? "ausgeschieden"}</span>
      {slot.pick.winner_score != null && (
        <span className="text-xs text-slate-500 tabular-nums">
          {slot.pick.winner_score}:{slot.pick.loser_score}
        </span>
      )}
      {slot.points != null && <span className={clsx("text-xs font-bold", slot.points > 0 ? "text-emerald-300" : "text-slate-500")}>+{slot.points}</span>}
    </span>
  );
}

function Compare() {
  const search = useSearchParams();
  const a = search.get("a") ?? "me";
  const b = search.get("b") ?? "";
  const { id, season } = useSelectedSeason(search.get("season") ? Number(search.get("season")) : null);
  const [tab, setTab] = useState<"table" | "a" | "b">("table");
  const query = useQuery({
    queryKey: ["compare", id, a, b],
    queryFn: () => get<CompareData>(`/api/seasons/${id}/compare?a=${a}&b=${b}`),
    enabled: id != null && !!b,
  });

  if (query.isLoading || !season) return <Loading />;
  if (query.error) return <ErrorBox error={query.error} />;
  const data = query.data!;
  const diffBySlot = Object.fromEntries(data.diff.map((d) => [d.slot, d.state]));
  const distBySlot = Object.fromEntries(data.distribution.map((d) => [d.slot, d]));
  const same = data.diff.filter((d) => d.state === "same").length;
  const different = data.diff.filter((d) => d.state === "different").length;
  const hidden = data.diff.filter((d) => d.state === "hidden").length;
  const teamsById = new Map<number, Team>();
  for (const s of [...data.a.slots, ...data.b.slots]) for (const t of [s.home, s.away]) if (t) teamsById.set(t.id, t);

  return (
    <div className="space-y-5">
      <Link href="/brackets" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white">
        <ArrowLeft className="size-4" /> Alle Brackets
      </Link>
      <PageHeader title="Bracket-Vergleich" subtitle={`Saison ${season.name}`} />

      <section className="glass flex flex-col items-center gap-4 rounded-3xl p-5 sm:flex-row sm:justify-around">
        {[data.a, data.b].map((v, i) => (
          <div key={v.user.id} className="flex items-center gap-3">
            <Avatar user={v.user} size={56} />
            <div>
              <p className="display text-2xl font-bold text-white">{v.user.display_name}</p>
              <p className="text-sm text-slate-400">
                {v.points} Punkte {v.rank ? `· Rang ${v.rank}` : ""}
              </p>
            </div>
            {i === 0 && <span className="display ml-6 hidden text-3xl font-bold text-slate-600 sm:block">VS</span>}
          </div>
        ))}
        <div className="flex gap-4 text-center text-sm">
          <div>
            <p className="display text-3xl font-bold text-emerald-300">{same}</p>
            <p className="text-xs text-slate-400">gleich</p>
          </div>
          <div>
            <p className="display text-3xl font-bold text-amber-300">{different}</p>
            <p className="text-xs text-slate-400">unterschiedlich</p>
          </div>
          <div>
            <p className="display text-3xl font-bold text-slate-400">{hidden}</p>
            <p className="text-xs text-slate-400">verdeckt</p>
          </div>
        </div>
      </section>

      <Tabs
        tabs={[
          { value: "table", label: "Gegenüberstellung" },
          { value: "a", label: `Bracket ${data.a.user.display_name}` },
          { value: "b", label: `Bracket ${data.b.user.display_name}` },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "table" ? (
        <Card bodyClassName="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="text-[11px] tracking-wider text-slate-500 uppercase">
                <tr className="border-b border-white/5">
                  <th className="px-4 py-3 text-left">Spiel</th>
                  <th className="px-4 py-3 text-left">{data.a.user.display_name}</th>
                  <th className="px-4 py-3 text-left">{data.b.user.display_name}</th>
                  <th className="px-4 py-3 text-left">Community</th>
                </tr>
              </thead>
              <tbody>
                {data.a.slots.map((sa, idx) => {
                  const sb = data.b.slots[idx];
                  const state = diffBySlot[sa.slot];
                  const dist = distBySlot[sa.slot];
                  return (
                    <tr
                      key={sa.slot}
                      className={clsx(
                        "border-b border-white/5 last:border-0",
                        state === "different" && "bg-amber-500/[0.08]",
                        state === "same" && "bg-emerald-500/[0.05]",
                      )}
                    >
                      <td className="px-4 py-3">
                        <p className="font-semibold text-slate-100">{slotLabel(sa.slot)}</p>
                        <p className="text-[11px] text-slate-500">{ROUND_TITLES[sa.round]}</p>
                      </td>
                      <td className="px-4 py-3">
                        <PickCell slot={sa} />
                      </td>
                      <td className="px-4 py-3">
                        <PickCell slot={sb} />
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-300">
                        {dist ? (
                          dist.teams.slice(0, 2).map((t) => (
                            <span key={t.team_id} className="mr-3 inline-flex items-center gap-1">
                              <TeamLogo team={teamsById.get(t.team_id) ?? null} size={16} /> {t.percent} %
                            </span>
                          ))
                        ) : (
                          <span className="flex items-center gap-1 text-slate-500">
                            <Lock className="size-3" /> nach Lock
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <Card accent="gold" bodyClassName="p-3 sm:p-5">
          {(() => {
            const v = tab === "a" ? data.a : data.b;
            return (
              <BracketBoard
                slots={v.slots}
                byes={v.byes}
                mode="view"
                seasonYear={season.year}
                scoreTips={season.score_tips_enabled}
                championTeamId={season.champion_team?.id ?? v.champion_team_id}
                championLabel={season.champion_team ? "Champion" : "Champion-Tipp"}
                highlights={diffBySlot}
              />
            );
          })()}
          <p className="mt-3 text-center text-xs text-slate-400">
            <span className="mr-3 inline-block size-2.5 rounded-sm ring-2 ring-amber-400" /> unterschiedlicher Tipp
            <span className="mx-3 inline-block size-2.5 rounded-sm ring-1 ring-emerald-400" /> gleicher Tipp
          </p>
        </Card>
      )}
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<Loading />}>
      <Compare />
    </Suspense>
  );
}
