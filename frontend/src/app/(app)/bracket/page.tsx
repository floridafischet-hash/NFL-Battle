"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleAlert, Info, Send } from "lucide-react";

import { BracketEditor } from "@/components/bracket/BracketEditor";
import { Badge, Button, Card, EmptyState, Loading, PageHeader, StatTile } from "@/components/ui";
import { post } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useBracket, useCurrentSeason } from "@/lib/queries";
import { useToast } from "@/lib/toast";
import type { BracketView } from "@/lib/types";

export default function MyBracketPage() {
  const season = useCurrentSeason();
  const bracket = useBracket(season.data?.id ?? null, "me");
  const qc = useQueryClient();
  const toast = useToast();
  const submit = useMutation({
    mutationFn: () => post<BracketView>(`/api/seasons/${season.data!.id}/bracket/me/submit`),
    onSuccess: (data) => {
      qc.setQueryData(["bracket", season.data!.id, "me"], data);
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Bracket abgegeben!", "Viel Glück – deine Freunde sehen deine Tipps erst nach dem Tipp-Lock.");
    },
    onError: (err) => toast.error("Abgabe nicht möglich", err instanceof Error ? err.message : undefined),
  });

  if (season.isLoading) return <Loading />;
  if (!season.data) {
    return (
      <Card>
        <EmptyState title="Keine aktive Saison">Sobald ein Admin eine Saison startet, kannst du hier deinen Tippbaum bauen.</EmptyState>
      </Card>
    );
  }
  const s = season.data;
  const view = bracket.data;
  const missing = view?.missing_open_picks ?? 0;
  const completed = s.status === "COMPLETED";

  return (
    <div className="space-y-5">
      <PageHeader
        title="Mein Bracket"
        subtitle={`Saison ${s.name} · Klicke auf ein Team, um es weiterkommen zu lassen. Der Sieger rückt automatisch in die nächste Runde.`}
      >
        {view?.submitted_at ? (
          <Badge tone="green" className="px-2.5 py-1 text-[11px]">
            <CheckCircle2 className="size-3.5" /> Abgegeben {dateTime(view.submitted_at)}
          </Badge>
        ) : null}
        {!completed && (
          <Button
            variant="primary"
            onClick={() => submit.mutate()}
            loading={submit.isPending}
            disabled={!view || missing > 0}
            title={missing > 0 ? `Es fehlen noch ${missing} Tipps` : undefined}
            data-testid="submit-bracket"
          >
            <Send className="size-4" /> {view?.submitted_at ? "Erneut bestätigen" : "Tipp abgeben"}
          </Button>
        )}
      </PageHeader>

      {view && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label="Getippte Spiele" value={`${view.picks_count} / 13`} />
          <StatTile
            label="Offene Tipps"
            value={missing}
            tone={missing > 0 ? "afc" : "green"}
            hint={missing > 0 ? "noch nicht gesperrte Spiele" : "alles getippt"}
          />
          <StatTile label="Punkte" value={view.points} tone="gold" />
          <StatTile label="Rang" value={view.rank ? `#${view.rank}` : "–"} />
        </div>
      )}

      {missing > 0 && !completed && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          <CircleAlert className="mt-0.5 size-4 shrink-0" />
          <p>
            Dir fehlen noch <strong>{missing}</strong> gültige Tipps. Ausgeschiedene Teams sind mit „raus“ markiert – solange
            ein Spiel offen ist, kannst du neu tippen.
          </p>
        </div>
      )}

      <Card accent="gold" bodyClassName="p-3 sm:p-5">
        {bracket.isLoading ? <Loading label="Bracket lädt …" /> : <BracketEditor season={s} />}
      </Card>

      <Card title="So funktioniert's">
        <ul className="grid gap-3 text-sm text-slate-300 md:grid-cols-2 xl:grid-cols-4">
          <li className="flex gap-2">
            <Info className="mt-0.5 size-4 shrink-0 text-gold" />
            <span>
              Richtiger Sieger: <strong className="text-white">{s.winner_points}</strong> · exakter Endstand:{" "}
              <strong className="text-white">{Math.max(s.exact_score_points, s.winner_points)}</strong> · Super-Bowl-Bonus:{" "}
              <strong className="text-white">+{s.champion_bonus}</strong>
            </span>
          </li>
          <li className="flex gap-2">
            <Info className="mt-0.5 size-4 shrink-0 text-gold" />
            <span>Nach Wild Card wird neu gesetzt: Seed 1 trifft auf den schlechtesten verbliebenen Seed.</span>
          </li>
          <li className="flex gap-2">
            <Info className="mt-0.5 size-4 shrink-0 text-gold" />
            <span>Mit dem Stift-Symbol tippst du den Endstand. Tipps sind bis zum Kickoff änderbar.</span>
          </li>
          <li className="flex gap-2">
            <Info className="mt-0.5 size-4 shrink-0 text-gold" />
            <span>Nach dem Lock: Spiel anklicken und „Änderung beantragen“ – ein Admin entscheidet.</span>
          </li>
        </ul>
      </Card>
    </div>
  );
}
