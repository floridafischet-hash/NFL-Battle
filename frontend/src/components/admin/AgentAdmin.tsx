"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, Check, PlugZap, RefreshCw, Settings2, X } from "lucide-react";

import { TeamLogo } from "@/components/TeamLogo";
import { Badge, Button, Card, EmptyState, Loading } from "@/components/ui";
import { get, post } from "@/lib/api";
import { slotLabel } from "@/lib/bracket";
import { dateTime, relativeTime } from "@/lib/format";
import { useToast } from "@/lib/toast";
import type { Match, Team } from "@/lib/types";

import { errorText, useInvalidateAdmin } from "./common";

interface Run {
  id: number;
  agent_label: string;
  kind: string;
  status: string;
  match_id: number | null;
  message: string | null;
  started_at: string;
  request_payload: Record<string, unknown> | null;
}
interface Report {
  id: number;
  match: Match;
  agent_label: string;
  home_score: number;
  away_score: number;
  winner_team: Team;
  source: string;
  source_url: string | null;
  reported_at: string | null;
  status: string;
  review_reason: string | null;
  created_at: string;
}
interface AgentConfig {
  enabled: boolean;
  configured: boolean;
  provider: "chatgpt" | "openai_api";
  has_key: boolean;
  chatgpt_login: boolean;
  model: string;
  trusted_domains: string[];
  min_confirmations: number;
  first_check_minutes: number;
  retry_minutes: number;
  max_calls_per_day: number;
  calls_last_24h: number;
}
interface Overview {
  config: AgentConfig;
  last_run: Run | null;
  runs: Run[];
  errors: Run[];
  reports: Report[];
}

const TONE: Record<string, "green" | "red" | "amber" | "neutral" | "gold"> = {
  APPLIED: "green",
  OK: "green",
  NO_RESULT: "neutral",
  DUPLICATE: "neutral",
  PENDING_CONFIRMATION: "gold",
  REVIEW_REQUIRED: "amber",
  REJECTED: "red",
  ERROR: "red",
  SUPERSEDED: "neutral",
};

export function AgentAdmin() {
  const toast = useToast();
  const invalidate = useInvalidateAdmin();
  const data = useQuery({ queryKey: ["agent-overview"], queryFn: () => get<Overview>("/api/admin/agent/overview"), refetchInterval: 30_000 });
  const refresh = () => {
    data.refetch();
    invalidate();
  };
  const testConnection = useMutation({
    mutationFn: () => post<{ ok: boolean; message: string }>("/api/admin/agent/test"),
    onSuccess: (r) => (r.ok ? toast.success("ChatGPT erreichbar", r.message) : toast.error("ChatGPT nicht erreichbar", r.message)),
    onError: (e) => toast.error("Test fehlgeschlagen", errorText(e)),
  });
  const check = useMutation({
    mutationFn: () => post<{ message: string }>("/api/admin/agent/check", {}),
    onSuccess: (r) => {
      refresh();
      toast.success("Prüfung angestoßen", `${r.message} ChatGPT sucht innerhalb einer Minute.`);
    },
    onError: (e) => toast.error("Prüfung fehlgeschlagen", errorText(e)),
  });
  const decide = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "accept" | "reject" }) => post(`/api/admin/agent/reports/${id}/${action}`),
    onSuccess: (_, v) => {
      refresh();
      toast.success(v.action === "accept" ? "Ergebnis übernommen und gewertet" : "Meldung verworfen");
    },
    onError: (e) => toast.error("Aktion fehlgeschlagen", errorText(e)),
  });

  if (data.isLoading) return <Loading />;
  const d = data.data!;
  const c = d.config;
  const review = d.reports.filter((r) => r.status === "REVIEW_REQUIRED" || r.status === "PENDING_CONFIRMATION");

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={<span className="flex items-center gap-2"><Settings2 className="size-4 text-gold" /> ChatGPT-Ergebnis-Agent</span>}
          action={
            <Button size="sm" onClick={() => testConnection.mutate()} loading={testConnection.isPending}>
              <PlugZap className="size-4" /> Verbindung testen
            </Button>
          }
        >
          <div className="space-y-2 text-sm" data-testid="agent-config">
            <p className="flex flex-wrap items-center gap-2">
              {c.configured ? (
                <Badge tone="green">aktiv</Badge>
              ) : (
                <Badge tone="red">{!c.enabled ? "deaktiviert" : c.provider === "chatgpt" ? "nicht angemeldet" : "kein API-Key"}</Badge>
              )}
              <span className="text-slate-300">
                {c.provider === "chatgpt" ? "über dein ChatGPT-Abo" : "über die OpenAI API"} · <code className="text-gold">{c.model}</code>
              </span>
            </p>
            {!c.configured && (
              <p className="text-amber-100">
                {!c.enabled
                  ? "RESULT_AGENT_ENABLED=false – Ergebnisse werden unter „Spiele“ eingetragen."
                  : c.provider === "chatgpt"
                    ? "Einmal auf dem Server mit deinem ChatGPT-Konto anmelden: docker compose exec backend codex login --device-auth (docs/CHATGPT.md). Bis dahin trägst du Ergebnisse unter „Spiele“ ein."
                    : "OPENAI_API_KEY in der .env auf dem Server eintragen und das Backend neu starten (docs/CHATGPT.md). Bis dahin trägst du Ergebnisse unter „Spiele“ ein."}
              </p>
            )}
            <p className="text-slate-400">
              Prüft {c.first_check_minutes} Min. nach Kickoff, danach alle {c.retry_minutes} Min. · braucht {c.min_confirmations} übereinstimmende Quelle(n) ·
              Abrufe 24 h: <strong className="text-white">{c.calls_last_24h}/{c.max_calls_per_day}</strong>
            </p>
            <p className="text-xs text-slate-500">Vertrauenswürdige Seiten: {c.trusted_domains.join(", ")}</p>
          </div>
        </Card>
        <Card title={<span className="flex items-center gap-2"><Bot className="size-4 text-gold" /> Letzter Lauf</span>}
          action={
            <Button size="sm" onClick={() => check.mutate()} loading={check.isPending} disabled={!c.configured}>
              <RefreshCw className="size-4" /> Jetzt prüfen
            </Button>
          }
        >
          {d.last_run ? (
            <div className="space-y-2 text-sm">
              <p className="flex items-center gap-2">
                <Badge tone={TONE[d.last_run.status] ?? "neutral"}>{d.last_run.status}</Badge>
                <span className="text-slate-300">{d.last_run.kind}</span>
                <span className="text-slate-500">· {relativeTime(d.last_run.started_at)}</span>
              </p>
              <p className="text-slate-300">{d.last_run.message}</p>
              <p className="text-xs text-slate-500">{d.last_run.agent_label}</p>
            </div>
          ) : (
            <EmptyState title="Noch kein Lauf">ChatGPT sucht automatisch nach Spielende; „Jetzt prüfen“ startet die Suche sofort.</EmptyState>
          )}
        </Card>
      </div>

      <Card title={`Prüfung erforderlich (${review.length})`} accent={review.length ? "gold" : undefined}>
        {review.length === 0 ? (
          <EmptyState title="Keine offenen Meldungen" />
        ) : (
          <div className="space-y-3">
            {review.map((r) => (
              <div key={r.id} className="rounded-2xl border border-amber-500/30 bg-amber-500/[0.06] p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-semibold text-white">{slotLabel(r.match.slot)}</span>
                  <span className="flex items-center gap-2 text-sm">
                    <TeamLogo team={r.match.home_team} size={22} /> {r.match.home_team?.short_name}
                    <strong className="display text-lg text-white">
                      {r.home_score} : {r.away_score}
                    </strong>
                    {r.match.away_team?.short_name} <TeamLogo team={r.match.away_team} size={22} />
                  </span>
                  <Badge tone={TONE[r.status]}>{r.status}</Badge>
                </div>
                <p className="mt-2 text-sm text-amber-100">{r.review_reason}</p>
                <p className="mt-1 text-xs text-slate-400">
                  Quelle: {r.source}{" "}
                  {r.source_url && (
                    <a href={r.source_url} target="_blank" rel="noreferrer noopener" className="text-gold underline">
                      {r.source_url}
                    </a>
                  )}{" "}
                  · {dateTime(r.created_at)} · {r.agent_label}
                </p>
                <div className="mt-3 flex gap-2">
                  <Button size="sm" variant="success" onClick={() => decide.mutate({ id: r.id, action: "accept" })} loading={decide.isPending}>
                    <Check className="size-4" /> Übernehmen & werten
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => decide.mutate({ id: r.id, action: "reject" })} loading={decide.isPending}>
                    <X className="size-4" /> Verwerfen
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Gemeldete Ergebnisse (Quellen)" bodyClassName="p-0">
          <div className="max-h-[480px] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-ink-900 text-[11px] text-slate-500 uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Spiel</th>
                  <th className="px-3 py-2 text-left">Ergebnis</th>
                  <th className="px-3 py-2 text-left">Quelle</th>
                  <th className="px-3 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {d.reports.map((r) => (
                  <tr key={r.id} className="border-t border-white/5">
                    <td className="px-3 py-2 text-slate-200">{slotLabel(r.match.slot)}</td>
                    <td className="px-3 py-2 font-semibold text-white tabular-nums">
                      {r.home_score}:{r.away_score}
                    </td>
                    <td className="max-w-[200px] truncate px-3 py-2 text-xs text-slate-400" title={r.source_url ?? ""}>
                      {r.source}
                    </td>
                    <td className="px-3 py-2">
                      <Badge tone={TONE[r.status] ?? "neutral"}>{r.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title={`Läufe · Fehler (${d.errors.length})`} bodyClassName="p-0">
          <div className="max-h-[480px] overflow-auto">
            <ul className="divide-y divide-white/5">
              {d.runs.map((r) => (
                <li key={r.id} className="px-4 py-2.5 text-sm">
                  <p className="flex items-center gap-2">
                    <Badge tone={TONE[r.status] ?? "neutral"}>{r.status}</Badge>
                    <span className="text-xs text-slate-400">{r.kind}</span>
                    <span className="ml-auto text-xs text-slate-500">{dateTime(r.started_at)}</span>
                  </p>
                  {r.message && <p className="mt-1 text-xs text-slate-300">{r.message}</p>}
                </li>
              ))}
              {d.runs.length === 0 && <li className="px-4 py-6 text-center text-sm text-slate-500">Keine Läufe</li>}
            </ul>
          </div>
        </Card>
      </div>

    </div>
  );
}
