"use client";

import { useMutation } from "@tanstack/react-query";
import clsx from "clsx";
import { Lock, RotateCcw, Unlock, Ban, Trophy } from "lucide-react";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/MatchBits";
import { TeamLogo } from "@/components/TeamLogo";
import { Badge, Button, Card, Input, Loading, Modal } from "@/components/ui";
import { patch, post } from "@/lib/api";
import { slotLabel } from "@/lib/bracket";
import { useToast } from "@/lib/toast";

import { errorText, fromLocalInput, toLocalInput, useAdminMatches, useInvalidateAdmin, type AdminMatch } from "./common";

function ResultModal({ match, onClose }: { match: AdminMatch | null; onClose: () => void }) {
  const toast = useToast();
  const invalidate = useInvalidateAdmin();
  const [home, setHome] = useState("");
  const [away, setAway] = useState("");
  useEffect(() => {
    setHome(match?.home_score?.toString() ?? "");
    setAway(match?.away_score?.toString() ?? "");
  }, [match]);
  const save = useMutation({
    mutationFn: () => post<{ correction: boolean; advanced: unknown[]; season_completed: boolean }>(`/api/admin/matches/${match!.id}/result`, { home_score: Number(home), away_score: Number(away) }),
    onSuccess: (r) => {
      invalidate();
      toast.success(
        r.correction ? "Ergebnis korrigiert – Punkte neu berechnet" : "Ergebnis gespeichert – Punkte vergeben",
        [r.advanced.length ? `${r.advanced.length} neue Paarung(en) erzeugt` : "", r.season_completed ? "Saison abgeschlossen – Hall of Fame aktualisiert 🏆" : ""].filter(Boolean).join("\n") || undefined,
      );
      onClose();
    },
    onError: (e) => toast.error("Ergebnis nicht gespeichert", errorText(e)),
  });
  if (!match) return null;
  return (
    <Modal open onClose={onClose} title={`${match.status === "FINAL" ? "Ergebnis korrigieren" : "Ergebnis eintragen"} · ${slotLabel(match.slot)}`}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        {[
          { team: match.home_team, value: home, set: setHome, label: "Heim" },
          { team: match.away_team, value: away, set: setAway, label: "Gast" },
        ].map((row) => (
          <label key={row.label} className="flex items-center gap-3 rounded-xl bg-white/[0.03] p-3">
            <TeamLogo team={row.team} size={44} />
            <span className="flex-1">
              <span className="block text-[11px] text-slate-400 uppercase">{row.label}</span>
              <span className="font-semibold text-white">{row.team?.name}</span>
            </span>
            <input
              type="number"
              min={0}
              max={99}
              required
              value={row.value}
              onChange={(e) => row.set(e.target.value)}
              className="focus-ring display h-14 w-20 rounded-xl border border-white/10 bg-ink-900 text-center text-3xl font-bold text-white"
              aria-label={`Punkte ${row.team?.short_name}`}
            />
          </label>
        ))}
        <p className="text-xs text-slate-400">
          Speichern setzt das Spiel auf FINAL, vergibt Punkte, aktualisiert die Rangliste, lässt den NFL Bot posten und erzeugt ggf. die nächste
          Runde. Korrekturen werden protokolliert und neu berechnet.
        </p>
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Abbrechen
          </Button>
          <Button type="submit" variant="primary" loading={save.isPending} data-testid="result-save">
            Speichern
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function MatchRow({ m, onResult }: { m: AdminMatch; onResult: () => void }) {
  const toast = useToast();
  const invalidate = useInvalidateAdmin();
  const [kickoff, setKickoff] = useState(toLocalInput(m.kickoff_at));
  const [lockAt, setLockAt] = useState(toLocalInput(m.lock_at));
  const [venue, setVenue] = useState(m.venue ?? "");
  useEffect(() => {
    setKickoff(toLocalInput(m.kickoff_at));
    setLockAt(toLocalInput(m.lock_at));
    setVenue(m.venue ?? "");
  }, [m.kickoff_at, m.lock_at, m.venue]);

  const update = useMutation({
    mutationFn: (body: Record<string, unknown>) => patch(`/api/admin/matches/${m.id}`, body),
    onSuccess: () => {
      invalidate();
      toast.success("Spiel aktualisiert");
    },
    onError: (e) => toast.error("Änderung fehlgeschlagen", errorText(e)),
  });
  const status = useMutation({
    mutationFn: (action: string) => post(`/api/admin/matches/${m.id}/status`, { action }),
    onSuccess: () => {
      invalidate();
      toast.success("Status geändert");
    },
    onError: (e) => toast.error("Statuswechsel fehlgeschlagen", errorText(e)),
  });
  const reset = useMutation({
    mutationFn: () => post(`/api/admin/matches/${m.id}/reset-result`),
    onSuccess: () => {
      invalidate();
      toast.success("Ergebnis zurückgesetzt", "Punkte wurden entfernt und die Rangliste neu berechnet.");
    },
    onError: (e) => toast.error("Zurücksetzen fehlgeschlagen", errorText(e)),
  });

  const timesChanged = kickoff !== toLocalInput(m.kickoff_at) || lockAt !== toLocalInput(m.lock_at) || venue !== (m.venue ?? "");
  return (
    <div className={clsx("rounded-2xl border bg-white/[0.02] p-3 sm:p-4", m.review_required ? "border-amber-500/40" : "border-white/8")}>
      <div className="flex flex-wrap items-center gap-3">
        <span className={clsx("w-40 text-sm font-semibold", m.conference === "AFC" ? "text-afc-soft" : m.conference === "NFC" ? "text-nfc-soft" : "text-gold")}>{slotLabel(m.slot)}</span>
        <span className="flex min-w-[240px] flex-1 items-center gap-2 text-sm">
          <TeamLogo team={m.home_team} size={26} /> <span className="font-semibold text-white">{m.home_team?.short_name ?? "TBD"}</span>
          <span className="display mx-1 font-bold text-slate-400 tabular-nums">{m.status === "FINAL" ? `${m.home_score} : ${m.away_score}` : "vs"}</span>
          <span className="font-semibold text-white">{m.away_team?.short_name ?? "TBD"}</span> <TeamLogo team={m.away_team} size={26} />
        </span>
        <StatusBadge match={m} />
        <Badge tone="neutral">{m.picks} Tipps</Badge>
        {m.review_required > 0 && <Badge tone="amber">Prüfung nötig</Badge>}
        {m.result_source && <Badge tone="neutral">via {m.result_source === "AGENT" ? "ChatGPT" : "Admin"}</Badge>}
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_auto]">
        <Input type="datetime-local" label="Kickoff" value={kickoff} onChange={(e) => setKickoff(e.target.value)} />
        <Input type="datetime-local" label="Tipp-Lock (Deadline)" value={lockAt} onChange={(e) => setLockAt(e.target.value)} />
        <Input label="Stadion" value={venue} onChange={(e) => setVenue(e.target.value)} maxLength={120} />
        <div className="flex items-end">
          <Button
            size="sm"
            className="min-h-11 w-full"
            disabled={!timesChanged}
            loading={update.isPending}
            onClick={() => {
              const body: Record<string, unknown> = { venue };
              if (kickoff !== toLocalInput(m.kickoff_at)) body.kickoff_at = fromLocalInput(kickoff);
              if (lockAt !== toLocalInput(m.lock_at)) body.lock_at = fromLocalInput(lockAt);
              update.mutate(body);
            }}
          >
            Termin speichern
          </Button>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {m.status === "OPEN" && (
          <Button size="sm" variant="danger" onClick={() => status.mutate("lock")} loading={status.isPending}>
            <Lock className="size-4" /> Sperren
          </Button>
        )}
        {(m.status === "LOCKED" || m.status === "VOID" || (m.status === "OPEN" && m.locked)) && (
          <Button size="sm" variant="success" onClick={() => status.mutate("reopen")} loading={status.isPending}>
            <Unlock className="size-4" /> Wieder öffnen
          </Button>
        )}
        {m.home_team && m.away_team && m.status !== "VOID" && (
          <Button size="sm" variant="primary" onClick={onResult} data-testid={`result-${m.slot}`}>
            <Trophy className="size-4" /> {m.status === "FINAL" ? "Ergebnis korrigieren" : "Ergebnis eintragen / abschließen"}
          </Button>
        )}
        {m.status === "FINAL" && (
          <Button size="sm" onClick={() => reset.mutate()} loading={reset.isPending}>
            <RotateCcw className="size-4" /> Ergebnis zurücksetzen
          </Button>
        )}
        {(m.status === "OPEN" || m.status === "LOCKED") && (
          <Button size="sm" variant="ghost" onClick={() => confirm("Spiel wirklich annullieren (VOID)? Es werden keine Punkte vergeben.") && status.mutate("void")}>
            <Ban className="size-4" /> Annullieren
          </Button>
        )}
      </div>
    </div>
  );
}

export function MatchesAdmin({ seasonId }: { seasonId: number }) {
  const matches = useAdminMatches(seasonId);
  const [resultFor, setResultFor] = useState<AdminMatch | null>(null);
  if (matches.isLoading) return <Loading />;
  return (
    <Card title="Spiele steuern">
      <p className="mb-4 text-xs text-slate-400">
        Status: OPEN → LOCKED (automatisch zur Deadline oder manuell) → FINAL (Ergebnis) · VOID = annulliert. Beim Wiederöffnen nach
        abgelaufener Deadline bleibt das Spiel offen, bis du es sperrst oder eine neue Deadline setzt.
      </p>
      <div className="space-y-3">
        {(matches.data ?? []).map((m) => (
          <MatchRow key={m.id} m={m} onResult={() => setResultFor(m)} />
        ))}
      </div>
      <ResultModal match={resultFor} onClose={() => setResultFor(null)} />
    </Card>
  );
}
