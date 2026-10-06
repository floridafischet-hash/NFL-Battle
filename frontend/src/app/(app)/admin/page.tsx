"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, FileClock, ShieldAlert, Users } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AgentAdmin } from "@/components/admin/AgentAdmin";
import { AuditAdmin } from "@/components/admin/AuditAdmin";
import { BracketSetup } from "@/components/admin/BracketSetup";
import { useAdminSeasons } from "@/components/admin/common";
import { MatchesAdmin } from "@/components/admin/MatchesAdmin";
import { RequestsAdmin } from "@/components/admin/RequestsAdmin";
import { SeasonsAdmin } from "@/components/admin/SeasonsAdmin";
import { TeamsAdmin } from "@/components/admin/TeamsAdmin";
import { UsersAdmin } from "@/components/admin/UsersAdmin";
import { Card, EmptyState, Loading, PageHeader, Select, StatTile, Tabs } from "@/components/ui";
import { get } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { relativeTime } from "@/lib/format";

type Tab = "overview" | "users" | "seasons" | "teams" | "setup" | "matches" | "requests" | "agent" | "audit";

interface Summary {
  pending_change_requests: number;
  review_required: number;
  users: number;
  last_agent_run: { status: string; started_at: string; message: string | null; kind: string } | null;
}

function Overview({ summary, go }: { summary: Summary | undefined; go: (t: Tab) => void }) {
  if (!summary) return <Loading />;
  const tiles = [
    { label: "Offene Änderungsanträge", value: summary.pending_change_requests, tab: "requests" as Tab, icon: FileClock, tone: summary.pending_change_requests ? ("afc" as const) : undefined },
    { label: "Agent-Ergebnisse zu prüfen", value: summary.review_required, tab: "agent" as Tab, icon: ShieldAlert, tone: summary.review_required ? ("afc" as const) : undefined },
    { label: "Benutzer", value: summary.users, tab: "users" as Tab, icon: Users, tone: undefined },
  ];
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        {tiles.map((t) => (
          <button key={t.label} onClick={() => go(t.tab)} className="focus-ring text-left">
            <StatTile label={t.label} value={t.value} tone={t.tone} hint="öffnen →" />
          </button>
        ))}
      </div>
      <Card title={<span className="flex items-center gap-2"><Bot className="size-4 text-gold" /> OpenClaw</span>}>
        {summary.last_agent_run ? (
          <p className="text-sm text-slate-300">
            Letzter Lauf ({summary.last_agent_run.kind}) {relativeTime(summary.last_agent_run.started_at)}: <strong>{summary.last_agent_run.status}</strong> –{" "}
            {summary.last_agent_run.message}
          </p>
        ) : (
          <p className="text-sm text-slate-400">Noch kein Agent-Lauf.</p>
        )}
      </Card>
      <Card title="Ablauf einer Saison">
        <ol className="list-decimal space-y-1.5 pl-5 text-sm text-slate-300">
          <li>Saisons: Saison erstellen und Punktesystem festlegen.</li>
          <li>Bracket-Setup: Setzliste per Drag &amp; Drop füllen, speichern, „Wild Card erzeugen“.</li>
          <li>Saisons: Saison aktivieren. Spiele: Kickoff-Zeiten setzen (Tipp-Lock folgt automatisch).</li>
          <li>Ergebnisse kommen von OpenClaw oder werden unter „Spiele“ eingetragen – Punkte, Rangliste, NFL Bot und nächste Runde laufen automatisch.</li>
          <li>Nach dem Super Bowl wird die Saison abgeschlossen und in die Hall of Fame übernommen.</li>
        </ol>
      </Card>
    </div>
  );
}

function AdminInner() {
  const me = useMe();
  const search = useSearchParams();
  const router = useRouter();
  const tab = (search.get("tab") as Tab) || "overview";
  const seasons = useAdminSeasons();
  const [seasonId, setSeasonId] = useState<number | null>(null);
  const summary = useQuery({ queryKey: ["admin-summary"], queryFn: () => get<Summary>("/api/admin/summary"), enabled: me.is_admin });
  if (!me.is_admin) {
    return (
      <Card>
        <EmptyState title="Kein Zugriff">Dieser Bereich ist nur für Admins.</EmptyState>
      </Card>
    );
  }
  const go = (t: Tab) => router.replace(`/admin?tab=${t}`);
  const playable = (seasons.data ?? []).filter((s) => s.status !== "COMPLETED");
  const sid = seasonId ?? playable.find((s) => s.status === "ACTIVE")?.id ?? playable[0]?.id ?? seasons.data?.[0]?.id ?? null;
  const needsSeason = tab === "setup" || tab === "matches";

  return (
    <div className="space-y-5">
      <PageHeader title="Admin" subtitle="Verwaltung von Benutzern, Saisons, Teams, Spielen, Tipps, Punkten, OpenClaw und Audit-Log.">
        {needsSeason && (seasons.data?.length ?? 0) > 0 && (
          <Select value={sid ?? ""} onChange={(e) => setSeasonId(Number(e.target.value))} aria-label="Saison wählen" className="w-44">
            {(seasons.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.status === "ACTIVE" ? "aktiv" : s.status === "DRAFT" ? "Entwurf" : "fertig"})
              </option>
            ))}
          </Select>
        )}
      </PageHeader>
      <Tabs<Tab>
        tabs={[
          { value: "overview", label: "Übersicht" },
          { value: "users", label: "Benutzer" },
          { value: "seasons", label: "Saisons & Punkte" },
          { value: "teams", label: "Teams" },
          { value: "setup", label: "Bracket-Setup" },
          { value: "matches", label: "Spiele" },
          { value: "requests", label: "Anträge", badge: summary.data?.pending_change_requests },
          { value: "agent", label: "OpenClaw", badge: summary.data?.review_required },
          { value: "audit", label: "Audit-Log" },
        ]}
        value={tab}
        onChange={go}
      />
      {tab === "overview" && <Overview summary={summary.data} go={go} />}
      {tab === "users" && <UsersAdmin />}
      {tab === "seasons" && <SeasonsAdmin />}
      {tab === "teams" && <TeamsAdmin />}
      {needsSeason && !sid && (
        <Card>
          <EmptyState title="Keine Saison">Lege zuerst unter „Saisons &amp; Punkte“ eine Saison an.</EmptyState>
        </Card>
      )}
      {tab === "setup" && sid && <BracketSetup key={sid} seasonId={sid} />}
      {tab === "matches" && sid && <MatchesAdmin key={sid} seasonId={sid} />}
      {tab === "requests" && <RequestsAdmin />}
      {tab === "agent" && <AgentAdmin />}
      {tab === "audit" && <AuditAdmin />}
    </div>
  );
}

export default function AdminPage() {
  return (
    <Suspense fallback={<Loading />}>
      <AdminInner />
    </Suspense>
  );
}
