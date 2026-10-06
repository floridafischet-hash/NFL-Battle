"use client";

import { useMutation } from "@tanstack/react-query";
import { Calculator, Play, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, Button, Card, Input, Loading } from "@/components/ui";
import { patch, post } from "@/lib/api";
import { useToast } from "@/lib/toast";
import type { Season } from "@/lib/types";

import { errorText, useAdminSeasons, useInvalidateAdmin } from "./common";

function ScoringForm({ season }: { season: Season }) {
  const toast = useToast();
  const invalidate = useInvalidateAdmin();
  const [form, setForm] = useState({
    winner_points: season.winner_points,
    exact_score_points: season.exact_score_points,
    champion_bonus: season.champion_bonus,
    score_tips_enabled: season.score_tips_enabled,
    lock_minutes_before_kickoff: season.lock_minutes_before_kickoff,
  });
  useEffect(() => {
    setForm({
      winner_points: season.winner_points,
      exact_score_points: season.exact_score_points,
      champion_bonus: season.champion_bonus,
      score_tips_enabled: season.score_tips_enabled,
      lock_minutes_before_kickoff: season.lock_minutes_before_kickoff,
    });
  }, [season]);
  const save = useMutation({
    mutationFn: () => patch(`/api/admin/seasons/${season.id}`, form),
    onSuccess: () => {
      invalidate();
      toast.success("Punktesystem gespeichert", "Tipp: „Punkte neu berechnen“ wendet die Werte auf gewertete Spiele an.");
    },
    onError: (e) => toast.error("Speichern fehlgeschlagen", errorText(e)),
  });
  const recalc = useMutation({
    mutationFn: () => post<{ matches_scored: number; total_points_before: number; total_points_after: number }>(`/api/admin/seasons/${season.id}/recalculate`),
    onSuccess: (r) => {
      invalidate();
      toast.success("Punkte neu berechnet", `${r.matches_scored} Spiele · Gesamtpunkte ${r.total_points_before} → ${r.total_points_after}`);
    },
    onError: (e) => toast.error("Neuberechnung fehlgeschlagen", errorText(e)),
  });
  const num = (key: keyof typeof form, label: string, max = 100) => (
    <Input
      label={label}
      type="number"
      min={0}
      max={max}
      value={String(form[key])}
      onChange={(e) => setForm({ ...form, [key]: Number(e.target.value) })}
    />
  );
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {num("winner_points", "Richtiger Sieger")}
        {num("exact_score_points", "Exakter Endstand")}
        {num("champion_bonus", "Super-Bowl-Bonus")}
        {num("lock_minutes_before_kickoff", "Tipp-Lock Minuten vor Kickoff", 10080)}
      </div>
      <label className="flex items-center gap-3 text-sm text-slate-200">
        <input
          type="checkbox"
          checked={form.score_tips_enabled}
          onChange={(e) => setForm({ ...form, score_tips_enabled: e.target.checked })}
          className="size-5 accent-[#f5c451]"
        />
        Endstand-Tipps aktiv (exakter Endstand bringt Bonuspunkte)
      </label>
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={() => save.mutate()} loading={save.isPending}>
          Speichern
        </Button>
        <Button onClick={() => recalc.mutate()} loading={recalc.isPending}>
          <Calculator className="size-4" /> Punkte neu berechnen
        </Button>
      </div>
    </div>
  );
}

export function SeasonsAdmin() {
  const toast = useToast();
  const invalidate = useInvalidateAdmin();
  const seasons = useAdminSeasons();
  const nextYear = new Date().getFullYear();
  const [form, setForm] = useState({ name: `${nextYear}/${nextYear + 1}`, year: nextYear });
  const create = useMutation({
    mutationFn: () => post("/api/admin/seasons", form),
    onSuccess: () => {
      invalidate();
      toast.success("Saison erstellt", "Als Nächstes: Setzliste im Bracket-Setup füllen und Saison aktivieren.");
    },
    onError: (e) => toast.error("Saison nicht erstellt", errorText(e)),
  });
  const activate = useMutation({
    mutationFn: (id: number) => post(`/api/admin/seasons/${id}/activate`),
    onSuccess: () => {
      invalidate();
      toast.success("Saison aktiviert");
    },
    onError: (e) => toast.error("Aktivieren fehlgeschlagen", errorText(e)),
  });

  if (seasons.isLoading) return <Loading />;
  return (
    <div className="space-y-5">
      <Card title="Neue Saison">
        <form
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <Input label="Name (z. B. 2026/2027)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} pattern="\d{4}/\d{4}" required />
          <Input label="Startjahr" type="number" value={form.year} onChange={(e) => setForm({ ...form, year: Number(e.target.value) })} required />
          <Button type="submit" variant="primary" loading={create.isPending} className="shrink-0">
            <Plus className="size-4" /> Saison erstellen
          </Button>
        </form>
      </Card>
      {(seasons.data ?? []).map((s) => (
        <Card
          key={s.id}
          title={
            <span className="flex items-center gap-3">
              Saison {s.name}
              <Badge tone={s.status === "ACTIVE" ? "green" : s.status === "COMPLETED" ? "gold" : "neutral"}>
                {s.status === "ACTIVE" ? "aktiv" : s.status === "COMPLETED" ? "abgeschlossen" : "Entwurf"}
              </Badge>
            </span>
          }
          action={
            s.status === "DRAFT" && (
              <Button size="sm" variant="success" onClick={() => activate.mutate(s.id)} loading={activate.isPending}>
                <Play className="size-4" /> Aktivieren
              </Button>
            )
          }
        >
          <p className="mb-3 text-xs tracking-wider text-slate-500 uppercase">Punktesystem</p>
          <ScoringForm season={s} />
        </Card>
      ))}
    </div>
  );
}
