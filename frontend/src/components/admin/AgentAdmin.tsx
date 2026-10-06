"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, Check, Copy, KeyRound, RefreshCw, Trash2, X } from "lucide-react";
import { useState } from "react";

import { TeamLogo } from "@/components/TeamLogo";
import { Badge, Button, Card, EmptyState, Input, Loading, Modal } from "@/components/ui";
import { del, get, post } from "@/lib/api";
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
interface Overview {
  last_run: Run | null;
  runs: Run[];
  errors: Run[];
  tokens: { id: number; name: string; token_prefix: string; created_at: string; last_used_at: string | null; revoked_at: string | null }[];
  reports: Report[];
}

const TONE: Record<string, "green" | "red" | "amber" | "neutral" | "gold"> = {
  APPLIED: "green",
  OK: "green",
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
  const [tokenName, setTokenName] = useState("OpenClaw");
  const [newToken, setNewToken] = useState<string | null>(null);
  const refresh = () => {
    data.refetch();
    invalidate();
  };
  const createToken = useMutation({
    mutationFn: () => post<{ token: string }>("/api/admin/agent/tokens", { name: tokenName }),
    onSuccess: (r) => {
      setNewToken(r.token);
      refresh();
    },
    onError: (e) => toast.error("Token nicht erstellt", errorText(e)),
  });
  const revoke = useMutation({
    mutationFn: (id: number) => del(`/api/admin/agent/tokens/${id}`),
    onSuccess: () => {
      refresh();
      toast.success("Token widerrufen");
    },
  });
  const check = useMutation({
    mutationFn: () => post<{ message: string }>("/api/admin/agent/check", {}),
    onSuccess: (r) => {
      refresh();
      toast.success("Ergebnisprüfung gestartet", r.message);
    },
    onError: (e) => toast.error("Ergebnisprüfung fehlgeschlagen", errorText(e)),
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
  const review = d.reports.filter((r) => r.status === "REVIEW_REQUIRED" || r.status === "PENDING_CONFIRMATION");

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={<span className="flex items-center gap-2"><Bot className="size-4 text-gold" /> Letzter OpenClaw-Lauf</span>}
          action={
            <Button size="sm" onClick={() => check.mutate()} loading={check.isPending}>
              <RefreshCw className="size-4" /> Ergebnisprüfung starten
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
              <p className="text-xs text-slate-500">Agent: {d.last_run.agent_label}</p>
            </div>
          ) : (
            <EmptyState title="Noch kein Agent-Aufruf">Erstelle einen Token und hinterlege ihn in OpenClaw (siehe docs/OPENCLAW.md).</EmptyState>
          )}
        </Card>
        <Card title={<span className="flex items-center gap-2"><KeyRound className="size-4 text-gold" /> API-Tokens (Rolle AGENT)</span>}>
          <form
            className="mb-4 flex items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              createToken.mutate();
            }}
          >
            <Input label="Name" value={tokenName} onChange={(e) => setTokenName(e.target.value)} minLength={2} required />
            <Button type="submit" variant="primary" loading={createToken.isPending} className="shrink-0">
              Token erstellen
            </Button>
          </form>
          <ul className="divide-y divide-white/5 text-sm">
            {d.tokens.map((t) => (
              <li key={t.id} className="flex items-center gap-3 py-2">
                <span className="flex-1">
                  <span className="font-semibold text-white">{t.name}</span> <code className="text-xs text-slate-400">{t.token_prefix}…</code>
                  <span className="block text-xs text-slate-500">
                    erstellt {dateTime(t.created_at)} · {t.last_used_at ? `zuletzt ${relativeTime(t.last_used_at)}` : "nie benutzt"}
                  </span>
                </span>
                {t.revoked_at ? (
                  <Badge tone="red">widerrufen</Badge>
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => revoke.mutate(t.id)} aria-label={`Token ${t.name} widerrufen`}>
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
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
        <Card title={`Agent-Läufe · Fehler (${d.errors.length})`} bodyClassName="p-0">
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

      <Modal open={!!newToken} onClose={() => setNewToken(null)} title="Neuer Agent-Token">
        <p className="mb-3 text-sm text-amber-100">Dieser Token wird nur jetzt angezeigt. Hinterlege ihn sicher in OpenClaw.</p>
        <div className="flex items-center gap-2 rounded-xl bg-black/40 p-3">
          <code className="flex-1 text-xs break-all text-gold" data-testid="agent-token">
            {newToken}
          </code>
          <Button
            size="sm"
            onClick={() => {
              navigator.clipboard?.writeText(newToken ?? "").then(() => toast.success("Kopiert"));
            }}
            aria-label="Token kopieren"
          >
            <Copy className="size-4" />
          </Button>
        </div>
      </Modal>
    </div>
  );
}
