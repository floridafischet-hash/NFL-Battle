"use client";

import { DivisionStandings } from "@/components/standings/DivisionStandings";
import { ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useLiveTeams } from "@/lib/queries";

export default function StandingsPage() {
  const teams = useLiveTeams();
  const favorites = new Set(teams.data?.favorites ?? []);
  return <div>
    <PageHeader title="NFL Division Standings" subtitle="Aktuelle Tabellen und Saisonstatistiken aller acht Divisions" />
    {teams.isLoading && <Loading label="Aktuelle NFL-Standings werden geladen …" />}
    {teams.error && <ErrorBox error={teams.error} />}
    {!!teams.data?.divisions.length && <DivisionStandings divisions={teams.data.divisions} favorites={favorites} />}
  </div>;
}
