"use client";

import { DivisionStandings } from "@/components/standings/DivisionStandings";
import { ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useLiveTeams } from "@/lib/queries";
import { dateTime } from "@/lib/format";

export default function StandingsPage() {
  const teams = useLiveTeams();
  const favorites = new Set(teams.data?.favorites ?? []);
  return <div>
    <PageHeader title="NFL Division Standings" subtitle="Live-Tabelle aller acht Divisions – Team antippen, um alle Statistiken zu öffnen" />
    {teams.data && <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400"><span className="inline-flex items-center gap-1.5 font-semibold text-emerald-300"><span className="size-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" /> LIVE</span><span>Stand: {teams.data.updated_at ? dateTime(teams.data.updated_at) : "gerade aktualisiert"}</span><span>Quelle: {teams.data.source}</span></div>}
    {teams.isLoading && <Loading label="Aktuelle NFL-Standings werden geladen …" />}
    {teams.error && <ErrorBox error={teams.error} />}
    {!!teams.data?.divisions.length && <DivisionStandings divisions={teams.data.divisions} favorites={favorites} />}
  </div>;
}
