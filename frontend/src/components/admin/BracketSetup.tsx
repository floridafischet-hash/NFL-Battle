"use client";

import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useMutation } from "@tanstack/react-query";
import clsx from "clsx";
import { Megaphone, Save, Search, Wand2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { TeamLogo } from "@/components/TeamLogo";
import { Badge, Button, Card, Input, Loading, Select, Tabs } from "@/components/ui";
import { patch, post, put } from "@/lib/api";
import { ROUND_TITLES, slotLabel } from "@/lib/bracket";
import { useTeams } from "@/lib/queries";
import { useToast } from "@/lib/toast";
import type { Conference, Team } from "@/lib/types";

import { errorText, useAdminMatches, useInvalidateAdmin, useSeasonTeams, type AdminMatch } from "./common";

type Seeds = Record<Conference, (number | null)[]>;
const emptySeeds = (): Seeds => ({ AFC: Array(7).fill(null), NFC: Array(7).fill(null) });

function ChipView({ team, seed, className }: { team: Team; seed?: number; className?: string }) {
  return (
    <div className={clsx("flex min-h-11 items-center gap-2 rounded-xl border border-white/10 bg-ink-800 px-2 py-1.5 select-none", className)}>
      <TeamLogo team={team} size={30} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-white">{team.short_name}</span>
        <span className="block text-[10px] text-slate-500">{team.abbreviation}</span>
      </span>
      {seed != null && <Badge tone={team.conference === "AFC" ? "afc" : "nfc"}>#{seed}</Badge>}
    </div>
  );
}

function TeamChip({ team, seed }: { team: Team; seed?: number }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: `team:${team.id}`, data: { team } });
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={clsx("cursor-grab touch-none active:cursor-grabbing", isDragging && "opacity-30")}
      aria-label={`${team.name} ziehen`}
      data-testid={`team-chip-${team.abbreviation}`}
    >
      <ChipView team={team} seed={seed} />
    </div>
  );
}

function DropSlot({
  id,
  team,
  label,
  conference,
  disabled,
  onClear,
  options,
  onSelect,
}: {
  id: string;
  team: Team | null | undefined;
  label: string;
  conference: Conference | null;
  disabled?: boolean;
  onClear?: () => void;
  options: Team[];
  onSelect: (teamId: number | null) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id, disabled });
  const color = conference === "AFC" ? "border-afc/60 bg-afc/10" : conference === "NFC" ? "border-nfc/60 bg-nfc/10" : "border-gold/60 bg-gold/10";
  return (
    <div
      ref={setNodeRef}
      className={clsx(
        "rounded-xl border border-dashed p-1.5 transition",
        isOver ? color : "border-white/12",
        disabled && "opacity-60",
      )}
      data-dropzone={id}
      data-testid={id}
    >
      <div className="flex min-h-10 items-center gap-2 px-1">
        <span className="w-14 shrink-0 text-[10px] font-bold tracking-wider text-slate-500 uppercase">{label}</span>
        {team ? (
          <>
            <TeamLogo team={team} size={26} />
            <span className="flex-1 truncate text-sm font-semibold text-white">{team.short_name}</span>
            {onClear && !disabled && (
              <button onClick={onClear} className="rounded p-1 text-slate-500 hover:text-red-300" aria-label={`${team.short_name} entfernen`}>
                <X className="size-4" />
              </button>
            )}
          </>
        ) : (
          <span className="flex-1 text-xs text-slate-500">Team hierher ziehen</span>
        )}
      </div>
      <Select
        value={team?.id ?? ""}
        disabled={disabled}
        onChange={(e) => onSelect(e.target.value ? Number(e.target.value) : null)}
        className="mt-1 min-h-8 py-0.5 text-xs"
        aria-label={`${label} auswählen`}
      >
        <option value="">– auswählen –</option>
        {options.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
            {t.seed ? ` (#${t.seed})` : ""}
          </option>
        ))}
      </Select>
    </div>
  );
}

export function BracketSetup({ seasonId }: { seasonId: number }) {
  const toast = useToast();
  const invalidate = useInvalidateAdmin();
  const teams = useTeams();
  const seasonTeams = useSeasonTeams(seasonId);
  const matches = useAdminMatches(seasonId);
  const [seeds, setSeeds] = useState<Seeds>(emptySeeds);
  const [dirty, setDirty] = useState(false);
  const [active, setActive] = useState<Team | null>(null);
  const [filter, setFilter] = useState<"AFC" | "NFC">("AFC");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!seasonTeams.data || dirty) return;
    const next = emptySeeds();
    for (const t of seasonTeams.data) if (t.seed) next[t.conference][t.seed - 1] = t.id;
    setSeeds(next);
  }, [seasonTeams.data, dirty]);

  const teamById = useMemo(() => new Map((teams.data ?? []).map((t) => [t.id, t])), [teams.data]);
  const seedOf = (teamId: number): number | undefined => {
    for (const conf of ["AFC", "NFC"] as const) {
      const i = seeds[conf].indexOf(teamId);
      if (i >= 0) return i + 1;
    }
    return undefined;
  };
  const seededTeams = useMemo(
    () =>
      (seasonTeams.data ?? []).map((t) => ({ ...t })).sort((a, b) => a.conference.localeCompare(b.conference) || (a.seed ?? 9) - (b.seed ?? 9)),
    [seasonTeams.data],
  );

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 6 } }),
    useSensor(KeyboardSensor),
  );

  const saveSeeds = useMutation({
    mutationFn: () => {
      const entries: { team_id: number; seed: number }[] = [];
      for (const conf of ["AFC", "NFC"] as const) seeds[conf].forEach((id, i) => id && entries.push({ team_id: id, seed: i + 1 }));
      return put(`/api/admin/seasons/${seasonId}/teams`, entries);
    },
    onSuccess: () => {
      setDirty(false);
      invalidate();
      toast.success("Setzliste gespeichert");
    },
    onError: (e) => toast.error("Setzliste nicht gespeichert", errorText(e)),
  });
  const generate = useMutation({
    mutationFn: () => post(`/api/admin/seasons/${seasonId}/generate-wildcard`),
    onSuccess: () => {
      invalidate();
      toast.success("Wild-Card-Paarungen erzeugt", "2 vs 7, 3 vs 6, 4 vs 5 – der NFL Bot hat die Paarungen gepostet.");
    },
    onError: (e) => toast.error("Paarungen nicht erzeugt", errorText(e)),
  });
  const announce = useMutation({
    mutationFn: () => post<{ announced: number }>(`/api/admin/seasons/${seasonId}/announce`),
    onSuccess: (r) => toast.success("Paarungen veröffentlicht", `${r.announced} Spiele im Chat angekündigt.`),
    onError: (e) => toast.error("Veröffentlichen fehlgeschlagen", errorText(e)),
  });
  const assign = useMutation({
    mutationFn: ({ match, side, teamId }: { match: AdminMatch; side: "home" | "away"; teamId: number | null }) =>
      patch(`/api/admin/matches/${match.id}`, { [`${side}_team_id`]: teamId }),
    onSuccess: () => invalidate(),
    onError: (e) => toast.error("Zuordnung nicht möglich", errorText(e)),
  });

  const setSeed = (conf: Conference, index: number, teamId: number | null) => {
    setSeeds((old) => {
      const next: Seeds = { AFC: [...old.AFC], NFC: [...old.NFC] };
      if (teamId != null) {
        const team = teamById.get(teamId);
        if (team && team.conference !== conf) {
          toast.error(`${team.short_name} spielt in der ${team.conference}`);
          return old;
        }
        for (const c of ["AFC", "NFC"] as const) next[c] = next[c].map((id) => (id === teamId ? null : id));
      }
      next[conf][index] = teamId;
      return next;
    });
    setDirty(true);
  };

  const onDragStart = (e: DragStartEvent) => setActive((e.active.data.current?.team as Team) ?? null);
  const onDragEnd = (e: DragEndEvent) => {
    setActive(null);
    const team = e.active.data.current?.team as Team | undefined;
    const target = e.over?.id ? String(e.over.id) : null;
    if (!team || !target) return;
    const [kind, a, b] = target.split(":");
    if (kind === "seed") setSeed(a as Conference, Number(b) - 1, team.id);
    if (kind === "match") {
      const match = matches.data?.find((m) => m.id === Number(a));
      if (match) assign.mutate({ match, side: b as "home" | "away", teamId: team.id });
    }
  };

  if (teams.isLoading || matches.isLoading) return <Loading />;
  const pool = (teams.data ?? [])
    .filter((t) => t.conference === filter && t.is_active)
    .filter((t) => !search || `${t.name} ${t.abbreviation}`.toLowerCase().includes(search.toLowerCase()));
  const rounds = ["WILD_CARD", "DIVISIONAL", "CONFERENCE", "SUPER_BOWL"];

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setActive(null)}>
      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Card title="Teams (ziehen)" className="xl:sticky xl:top-20 xl:self-start">
          <Tabs tabs={[{ value: "AFC", label: "AFC" }, { value: "NFC", label: "NFC" }]} value={filter} onChange={setFilter} className="mb-3" />
          <div className="mb-3 flex items-center gap-2 rounded-xl border border-white/10 bg-ink-900/80 px-3">
            <Search className="size-4 text-slate-500" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Team suchen" className="h-10 w-full bg-transparent text-sm text-white outline-none" aria-label="Team suchen" />
          </div>
          <div className="scrollbar-thin grid max-h-[60vh] grid-cols-2 gap-2 overflow-y-auto pr-1 xl:grid-cols-1">
            {pool.map((t) => (
              <TeamChip key={t.id} team={t} seed={seedOf(t.id)} />
            ))}
          </div>
        </Card>

        <div className="min-w-0 space-y-5">
          <Card
            title="Setzliste (Seeds)"
            action={
              <div className="flex gap-2">
                <Button size="sm" variant="primary" onClick={() => saveSeeds.mutate()} loading={saveSeeds.isPending} disabled={!dirty}>
                  <Save className="size-4" /> Speichern
                </Button>
                <Button size="sm" onClick={() => generate.mutate()} loading={generate.isPending} disabled={dirty}>
                  <Wand2 className="size-4" /> Wild Card erzeugen
                </Button>
              </div>
            }
          >
            <div className="grid gap-4 md:grid-cols-2">
              {(["AFC", "NFC"] as const).map((conf) => (
                <div key={conf} className="space-y-2">
                  <p className={clsx("display text-sm font-bold tracking-widest", conf === "AFC" ? "text-afc-soft" : "text-nfc-soft")}>{conf}</p>
                  {seeds[conf].map((teamId, i) => (
                    <DropSlot
                      key={i}
                      id={`seed:${conf}:${i + 1}`}
                      label={`Seed ${i + 1}`}
                      conference={conf}
                      team={teamId ? teamById.get(teamId) : null}
                      onClear={() => setSeed(conf, i, null)}
                      options={(teams.data ?? []).filter((t) => t.conference === conf)}
                      onSelect={(id) => setSeed(conf, i, id)}
                    />
                  ))}
                </div>
              ))}
            </div>
            {dirty && <p className="mt-3 text-xs text-amber-300">Ungespeicherte Änderungen an der Setzliste.</p>}
          </Card>

          <Card
            title="Paarungen (Match-Slots)"
            action={
              <Button size="sm" onClick={() => announce.mutate()} loading={announce.isPending}>
                <Megaphone className="size-4" /> Paarungen veröffentlichen
              </Button>
            }
          >
            <p className="mb-4 text-xs text-slate-400">
              Teams aus der Liste auf Heim/Gast ziehen oder per Auswahl setzen. Folgerunden werden nach den Ergebnissen automatisch
              (mit NFL-Reseeding) befüllt – hier kannst du sie bei Bedarf manuell überschreiben.
            </p>
            <div className="space-y-5">
              {rounds.map((round) => {
                const list = (matches.data ?? []).filter((m) => m.round === round);
                return (
                  <div key={round}>
                    <p className="mb-2 text-xs font-bold tracking-widest text-slate-400 uppercase">{ROUND_TITLES[round]}</p>
                    <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
                      {list.map((m) => {
                        const locked = m.status === "FINAL" || m.locked;
                        const options = seededTeams.filter((t) => !m.conference || t.conference === m.conference);
                        return (
                          <div key={m.id} className="rounded-2xl border border-white/8 bg-white/[0.02] p-3">
                            <div className="mb-2 flex items-center justify-between">
                              <span className={clsx("text-sm font-semibold", m.conference === "AFC" ? "text-afc-soft" : m.conference === "NFC" ? "text-nfc-soft" : "text-gold")}>
                                {slotLabel(m.slot)}
                              </span>
                              <Badge tone={m.status === "OPEN" && !m.locked ? "green" : "neutral"}>{m.status}</Badge>
                            </div>
                            <div className="space-y-2">
                              {(["home", "away"] as const).map((side) => (
                                <DropSlot
                                  key={side}
                                  id={`match:${m.id}:${side}`}
                                  label={side === "home" ? "Heim" : "Gast"}
                                  conference={m.conference}
                                  team={side === "home" ? m.home_team : m.away_team}
                                  disabled={locked}
                                  onClear={() => assign.mutate({ match: m, side, teamId: null })}
                                  options={options}
                                  onSelect={(id) => assign.mutate({ match: m, side, teamId: id })}
                                />
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      </div>
      <DragOverlay dropAnimation={null}>{active ? <ChipView team={active} className="rotate-2 shadow-2xl ring-2 ring-gold" /> : null}</DragOverlay>
    </DndContext>
  );
}
