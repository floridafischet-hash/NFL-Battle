"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, X } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { TeamLogo } from "@/components/TeamLogo";
import { Badge, Button, Card, EmptyState, Input, Loading, Tabs } from "@/components/ui";
import { get, post } from "@/lib/api";
import { slotLabel } from "@/lib/bracket";
import { dateTime } from "@/lib/format";
import { useToast } from "@/lib/toast";
import type { ChangeRequest, Team } from "@/lib/types";

import { errorText, useInvalidateAdmin } from "./common";

function TipView({ tip }: { tip: { winner_team: Team | null; winner_score: number | null; loser_score: number | null } | null }) {
  if (!tip) return <span className="text-sm text-slate-500">kein Tipp</span>;
  return (
    <span className="flex items-center gap-2">
      <TeamLogo team={tip.winner_team} size={28} />
      <span className="font-semibold text-white">{tip.winner_team?.short_name}</span>
      {tip.winner_score != null && <span className="text-sm text-slate-400 tabular-nums">{tip.winner_score}:{tip.loser_score}</span>}
    </span>
  );
}

export function RequestsAdmin() {
  const toast = useToast();
  const invalidate = useInvalidateAdmin();
  const [filter, setFilter] = useState<"PENDING" | "ALL">("PENDING");
  const [notes, setNotes] = useState<Record<number, string>>({});
  const list = useQuery({
    queryKey: ["admin-change-requests", filter],
    queryFn: () => get<ChangeRequest[]>(`/api/admin/change-requests${filter === "PENDING" ? "?status=PENDING" : ""}`),
  });
  const decide = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "approve" | "reject" }) => post(`/api/admin/change-requests/${id}/${action}`, { note: notes[id] || null }),
    onSuccess: (_, v) => {
      invalidate();
      list.refetch();
      toast.success(v.action === "approve" ? "Antrag genehmigt" : "Antrag abgelehnt", "Der Benutzer wurde benachrichtigt, die Entscheidung protokolliert.");
    },
    onError: (e) => toast.error("Entscheidung fehlgeschlagen", errorText(e)),
  });

  return (
    <Card title="Änderungsanträge">
      <Tabs tabs={[{ value: "PENDING", label: "Offen" }, { value: "ALL", label: "Alle" }]} value={filter} onChange={setFilter} className="mb-4 w-fit" />
      {list.isLoading && <Loading />}
      {list.data?.length === 0 && <EmptyState title="Keine Anträge">Nach dem Tipp-Lock können Spieler hier Änderungen beantragen.</EmptyState>}
      <div className="space-y-3">
        {list.data?.map((cr) => (
          <div key={cr.id} className="rounded-2xl border border-white/8 bg-white/[0.02] p-4">
            <div className="flex flex-wrap items-center gap-3">
              <Avatar user={cr.user} size={36} />
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-white">{cr.user.display_name}</p>
                <p className="text-xs text-slate-400">
                  {slotLabel(cr.slot)} · {cr.match.home_team?.short_name} vs {cr.match.away_team?.short_name} · {dateTime(cr.created_at)}
                </p>
              </div>
              <Badge tone={cr.status === "PENDING" ? "amber" : cr.status === "APPROVED" ? "green" : "red"}>
                {cr.status === "PENDING" ? "offen" : cr.status === "APPROVED" ? "genehmigt" : cr.status === "REJECTED" ? "abgelehnt" : "zurückgezogen"}
              </Badge>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-4 rounded-xl bg-black/20 p-3">
              <div>
                <p className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Alter Tipp</p>
                <TipView tip={cr.old} />
              </div>
              <ArrowRight className="size-5 text-slate-500" />
              <div>
                <p className="text-[10px] font-bold tracking-widest text-gold uppercase">Neuer Tipp</p>
                <TipView tip={cr.new} />
              </div>
              {cr.reason && <p className="w-full text-sm text-slate-300">Begründung: „{cr.reason}“</p>}
            </div>
            {cr.status === "PENDING" ? (
              <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
                <Input label="Notiz (optional)" value={notes[cr.id] ?? ""} onChange={(e) => setNotes({ ...notes, [cr.id]: e.target.value })} maxLength={500} />
                <div className="flex shrink-0 gap-2">
                  <Button variant="success" onClick={() => decide.mutate({ id: cr.id, action: "approve" })} loading={decide.isPending}>
                    <Check className="size-4" /> Genehmigen
                  </Button>
                  <Button variant="danger" onClick={() => decide.mutate({ id: cr.id, action: "reject" })} loading={decide.isPending}>
                    <X className="size-4" /> Ablehnen
                  </Button>
                </div>
              </div>
            ) : (
              <p className="mt-2 text-xs text-slate-400">
                {cr.decided_by ? `von ${cr.decided_by} ` : ""}
                {cr.decided_at ? `am ${dateTime(cr.decided_at)}` : ""}
                {cr.decision_note ? ` – „${cr.decision_note}“` : ""}
              </p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
