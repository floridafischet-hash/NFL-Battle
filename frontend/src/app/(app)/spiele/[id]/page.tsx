"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, Clock3, EyeOff, FileEdit, Lock, MapPin } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { DistributionBar, StatusBadge } from "@/components/MatchBits";
import { TeamLogo } from "@/components/TeamLogo";
import { Badge, Button, Card, EmptyState, ErrorBox, Input, Loading } from "@/components/ui";
import { del, post, put } from "@/lib/api";
import { slotLabel } from "@/lib/bracket";
import { countdown, dateLong, dateTime, kickoffShort, timeOnly } from "@/lib/format";
import { useMatch } from "@/lib/queries";
import { useToast } from "@/lib/toast";
import type { MatchDetail, Team, Tip } from "@/lib/types";

function TipForm({
  home,
  away,
  initial,
  scoreTips,
  submitLabel,
  withReason,
  busy,
  onSubmit,
}: {
  home: Team;
  away: Team;
  initial: Tip | null;
  scoreTips: boolean;
  submitLabel: string;
  withReason?: boolean;
  busy?: boolean;
  onSubmit: (tip: Tip, reason?: string) => void;
}) {
  const [winner, setWinner] = useState<number | null>(initial?.winner_team_id ?? null);
  const [ws, setWs] = useState(initial?.winner_score?.toString() ?? "");
  const [ls, setLs] = useState(initial?.loser_score?.toString() ?? "");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setWinner(initial?.winner_team_id ?? null);
    setWs(initial?.winner_score?.toString() ?? "");
    setLs(initial?.loser_score?.toString() ?? "");
  }, [initial?.winner_team_id, initial?.winner_score, initial?.loser_score]);

  const submit = () => {
    setError(null);
    if (!winner) return setError("Bitte einen Sieger wählen.");
    let winner_score: number | null = null;
    let loser_score: number | null = null;
    if (scoreTips && (ws !== "" || ls !== "")) {
      winner_score = Number(ws);
      loser_score = Number(ls);
      if (!Number.isInteger(winner_score) || !Number.isInteger(loser_score) || winner_score < 0 || loser_score < 0 || winner_score > 99 || loser_score > 99)
        return setError("Punkte müssen ganze Zahlen zwischen 0 und 99 sein.");
      if (winner_score <= loser_score) return setError("Der Sieger muss mehr Punkte haben.");
    }
    onSubmit({ winner_team_id: winner, winner_score, loser_score }, reason || undefined);
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        {[home, away].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setWinner(t.id)}
            className={clsx(
              "focus-ring flex flex-col items-center gap-2 rounded-2xl border p-4 transition",
              winner === t.id ? "border-gold bg-gold/10 shadow-[0_0_24px_-6px_rgb(245_196_81/0.6)]" : "border-white/10 bg-white/[0.03] hover:border-white/25",
            )}
            aria-pressed={winner === t.id}
          >
            <TeamLogo team={t} size={56} glow={winner === t.id} />
            <span className="display text-lg font-bold text-white">{t.short_name}</span>
            <span className="text-[11px] text-slate-400">{winner === t.id ? "Dein Sieger" : "als Sieger wählen"}</span>
          </button>
        ))}
      </div>
      {scoreTips && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400">Endstand (optional):</span>
          <input
            type="number"
            min={0}
            max={99}
            value={ws}
            onChange={(e) => setWs(e.target.value)}
            placeholder="Sieger"
            className="focus-ring h-11 w-24 rounded-xl border border-white/10 bg-ink-900 text-center font-bold text-white"
            aria-label="Punkte Sieger"
          />
          <span className="text-slate-500">:</span>
          <input
            type="number"
            min={0}
            max={99}
            value={ls}
            onChange={(e) => setLs(e.target.value)}
            placeholder="Verlierer"
            className="focus-ring h-11 w-24 rounded-xl border border-white/10 bg-ink-900 text-center font-bold text-white"
            aria-label="Punkte Verlierer"
          />
        </div>
      )}
      {withReason && (
        <Input label="Begründung (optional)" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} placeholder="z. B. verklickt" />
      )}
      {error && <p className="text-sm text-red-300">{error}</p>}
      <Button variant="primary" onClick={submit} loading={busy}>
        {submitLabel}
      </Button>
    </div>
  );
}

export default function MatchPage() {
  const params = useParams<{ id: string }>();
  const matchId = Number(params.id);
  const detail = useMatch(matchId);
  const qc = useQueryClient();
  const toast = useToast();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["match", matchId] });
    qc.invalidateQueries({ queryKey: ["bracket"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
    qc.invalidateQueries({ queryKey: ["matches"] });
  };

  const setTip = useMutation({
    mutationFn: ({ d, tip }: { d: MatchDetail; tip: Tip }) => put(`/api/seasons/${d.season.id}/bracket/me/picks/${d.match.slot}`, tip),
    onSuccess: () => {
      toast.success("Tipp gespeichert");
      refresh();
    },
    onError: (e) => toast.error("Tipp nicht gespeichert", e instanceof Error ? e.message : undefined),
  });
  const request = useMutation({
    mutationFn: ({ tip, reason }: { tip: Tip; reason?: string }) => post(`/api/matches/${matchId}/change-requests`, { ...tip, reason }),
    onSuccess: () => {
      toast.success("Änderungsantrag gestellt", "Ein Admin entscheidet über deinen Antrag.");
      refresh();
    },
    onError: (e) => toast.error("Antrag nicht möglich", e instanceof Error ? e.message : undefined),
  });
  const cancel = useMutation({
    mutationFn: (id: number) => del(`/api/change-requests/${id}`),
    onSuccess: () => {
      toast.info("Antrag zurückgezogen");
      refresh();
    },
  });

  if (detail.isLoading) return <Loading />;
  if (detail.error) return <ErrorBox error={detail.error} />;
  const d = detail.data!;
  const m = d.match;
  const final = m.status === "FINAL";
  const homeWon = final && m.winner_team_id === m.home_team?.id;
  const awayWon = final && m.winner_team_id === m.away_team?.id;
  const c = countdown(m.lock_at ?? m.kickoff_at, now);
  const cr = d.my_change_request;
  const teamById = (id: number | null | undefined) => [m.home_team, m.away_team].find((t) => t?.id === id) ?? null;

  const side = (team: Team | null, won: boolean, score: number | null) => (
    <div className={clsx("flex flex-1 flex-col items-center gap-3 text-center", final && !won && "opacity-50")}>
      <div className="relative">
        {team && <div className="absolute inset-0 rounded-full blur-2xl" style={{ background: `${team.primary_color}55` }} />}
        <TeamLogo team={team} size={110} glow={won} className="relative" />
      </div>
      <div>
        <p className="text-[11px] font-bold tracking-widest text-slate-500">{team ? `SEED ${team.seed ?? "–"} · ${team.city ?? ""}` : "NOCH OFFEN"}</p>
        <p className="display text-2xl font-bold text-white sm:text-3xl">{team?.short_name ?? "TBD"}</p>
      </div>
      {final && <p className={clsx("display text-5xl font-bold tabular-nums sm:text-6xl", won ? "text-white" : "text-slate-500")}>{score}</p>}
    </div>
  );

  return (
    <div className="space-y-5">
      <Link href="/spiele" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white">
        <ArrowLeft className="size-4" /> Alle Spiele
      </Link>

      <section className="glass relative overflow-hidden rounded-3xl px-4 py-6 sm:px-8">
        <div className="pointer-events-none absolute -top-20 left-0 h-56 w-1/2 blur-3xl" style={{ background: `${m.home_team?.primary_color ?? "#334155"}33` }} />
        <div className="pointer-events-none absolute -top-20 right-0 h-56 w-1/2 blur-3xl" style={{ background: `${m.away_team?.primary_color ?? "#334155"}33` }} />
        <div className="relative mb-6 flex flex-wrap items-center justify-center gap-2 text-center">
          <StatusBadge match={m} />
          <span className={clsx("display text-sm font-semibold tracking-widest", m.conference === "AFC" ? "text-afc-soft" : m.conference === "NFC" ? "text-nfc-soft" : "text-gold")}>
            {slotLabel(m.slot)}
          </span>
        </div>
        <div className="relative flex items-center gap-4">
          {side(m.home_team, homeWon, m.home_score)}
          <div className="display shrink-0 text-3xl font-bold text-slate-600">{final ? ":" : "VS"}</div>
          {side(m.away_team, awayWon, m.away_score)}
        </div>
        <div className="relative mt-6 flex flex-wrap items-center justify-center gap-x-6 gap-y-1 text-sm text-slate-300">
          <span className="flex items-center gap-1.5">
            <Clock3 className="size-4 text-slate-500" /> {dateLong(m.kickoff_at)} · {timeOnly(m.kickoff_at)}
          </span>
          {m.venue && (
            <span className="flex items-center gap-1.5">
              <MapPin className="size-4 text-slate-500" /> {m.venue}
            </span>
          )}
          {!m.locked && !c.done && (
            <span className="flex items-center gap-1.5 text-amber-200">
              <Lock className="size-4" /> Tippschluss in {c.days > 0 ? `${c.days} T ` : ""}
              {String(c.hours).padStart(2, "0")}:{String(c.minutes).padStart(2, "0")}:{String(c.seconds).padStart(2, "0")}
            </span>
          )}
          {final && m.result_source && <span className="text-xs text-slate-500">Ergebnis via {m.result_source === "AGENT" ? "ChatGPT" : "Admin"}</span>}
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Dein Tipp" accent="gold">
          {!m.home_team || !m.away_team ? (
            <EmptyState title="Paarung steht noch nicht fest">Tippe im Bracket zuerst die Vorrunde.</EmptyState>
          ) : !m.locked ? (
            <TipForm
              home={m.home_team}
              away={m.away_team}
              initial={d.my_pick}
              scoreTips={d.season.score_tips_enabled}
              submitLabel="Tipp speichern"
              busy={setTip.isPending}
              onSubmit={(tip) => setTip.mutate({ d, tip })}
            />
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-3 rounded-xl bg-white/[0.04] p-3">
                {d.my_pick ? (
                  <>
                    <TeamLogo team={teamById(d.my_pick.winner_team_id)} size={40} />
                    <div>
                      <p className="font-semibold text-white">{teamById(d.my_pick.winner_team_id)?.name ?? "Team nicht in dieser Partie"}</p>
                      <p className="text-xs text-slate-400">
                        {d.my_pick.winner_score != null ? `Endstand ${d.my_pick.winner_score}:${d.my_pick.loser_score}` : "ohne Endstand"}
                      </p>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-slate-400">Kein Tipp abgegeben.</p>
                )}
                <Badge tone="red" className="ml-auto">
                  <Lock className="size-3" /> gesperrt
                </Badge>
              </div>
              {cr && cr.status === "PENDING" ? (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">
                  <p className="font-semibold">Änderungsantrag offen</p>
                  <p className="text-xs">
                    Neu: {cr.new.winner_team?.short_name}
                    {cr.new.winner_score != null ? ` ${cr.new.winner_score}:${cr.new.loser_score}` : ""} · gestellt {dateTime(cr.created_at)}
                  </p>
                  <Button size="sm" variant="ghost" className="mt-2" onClick={() => cancel.mutate(cr.id)} loading={cancel.isPending}>
                    Antrag zurückziehen
                  </Button>
                </div>
              ) : !final && m.status !== "VOID" ? (
                <details className="group rounded-xl border border-white/8 p-3">
                  <summary className="flex cursor-pointer list-none items-center gap-2 font-semibold text-gold">
                    <FileEdit className="size-4" /> Änderung beantragen
                  </summary>
                  <div className="mt-4">
                    <TipForm
                      home={m.home_team}
                      away={m.away_team}
                      initial={d.my_pick}
                      scoreTips={d.season.score_tips_enabled}
                      submitLabel="Antrag stellen"
                      withReason
                      busy={request.isPending}
                      onSubmit={(tip, reason) => request.mutate({ tip, reason })}
                    />
                  </div>
                </details>
              ) : null}
              {cr && cr.status !== "PENDING" && (
                <p className="text-xs text-slate-400">
                  Letzter Antrag: <strong className={cr.status === "APPROVED" ? "text-emerald-300" : "text-red-300"}>{cr.status === "APPROVED" ? "genehmigt" : cr.status === "REJECTED" ? "abgelehnt" : "zurückgezogen"}</strong>
                  {cr.decision_note ? ` – „${cr.decision_note}“` : ""}
                </p>
              )}
            </div>
          )}
        </Card>

        <Card title="Community-Tipps">
          {d.revealed ? (
            <div className="space-y-4">
              <DistributionBar distribution={d.distribution} home={m.home_team} away={m.away_team} />
              <ul className="divide-y divide-white/5">
                {d.picks.map((p) => {
                  const t = teamById(p.pick?.winner_team_id);
                  return (
                    <li key={p.user.id} className="flex items-center gap-3 py-2">
                      <Avatar user={p.user} size={30} />
                      <span className="flex-1 truncate text-sm font-semibold text-slate-100">{p.user.display_name}</span>
                      {p.pick ? (
                        <span className="flex items-center gap-1.5 text-sm text-slate-200">
                          <TeamLogo team={t} size={20} /> {t?.short_name ?? "ungültig"}
                          {p.pick.winner_score != null && <span className="text-xs text-slate-500 tabular-nums">{p.pick.winner_score}:{p.pick.loser_score}</span>}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-500">kein Tipp</span>
                      )}
                      {p.points != null && (
                        <span className={clsx("w-12 text-right text-sm font-bold", p.exact_correct ? "text-gold" : p.points > 0 ? "text-emerald-300" : "text-slate-500")}>
                          +{p.points}
                          {p.exact_correct ? "🎯" : ""}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="flex items-center gap-2 text-sm text-slate-400">
                <EyeOff className="size-4" /> Tipps der anderen werden mit dem Tipp-Lock ({kickoffShort(m.lock_at ?? m.kickoff_at)}) aufgedeckt.
              </p>
              <div className="flex flex-wrap gap-2">
                {d.picks.map((p) => (
                  <span key={p.user.id} className={clsx("flex items-center gap-1.5 rounded-full px-2 py-1 text-xs", p.has_pick ? "bg-emerald-500/10 text-emerald-200" : "bg-white/5 text-slate-500")}>
                    <Avatar user={p.user} size={18} /> {p.user.display_name} {p.has_pick ? "✓" : "…"}
                  </span>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
