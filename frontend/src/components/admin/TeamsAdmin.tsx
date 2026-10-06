"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { TeamLogo } from "@/components/TeamLogo";
import { Button, Card, Input, Loading, Modal, Select, Tabs } from "@/components/ui";
import { post, put, upload } from "@/lib/api";
import { useTeams } from "@/lib/queries";
import { useToast } from "@/lib/toast";
import type { Team } from "@/lib/types";

import { errorText } from "./common";

type TeamForm = Omit<Team, "id" | "seed">;

const EMPTY: TeamForm = {
  name: "",
  short_name: "",
  abbreviation: "",
  city: "",
  conference: "AFC",
  division: "",
  logo_url: "",
  primary_color: "#334155",
  secondary_color: "#94a3b8",
  is_active: true,
};

function TeamModal({ team, onClose }: { team: Team | "new" | null; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const file = useRef<HTMLInputElement>(null);
  const editing = team && team !== "new" ? team : null;
  const [form, setForm] = useState<TeamForm>(editing ? { ...editing, city: editing.city ?? "", division: editing.division ?? "", logo_url: editing.logo_url ?? "" } : EMPTY);
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["teams"] });
    qc.invalidateQueries({ queryKey: ["season-teams"] });
  };
  const save = useMutation({
    mutationFn: () => {
      const body = { ...form, city: form.city || null, division: form.division || null, logo_url: form.logo_url || null };
      return editing ? put(`/api/admin/teams/${editing.id}`, body) : post("/api/admin/teams", body);
    },
    onSuccess: () => {
      refresh();
      toast.success("Team gespeichert");
      onClose();
    },
    onError: (e) => toast.error("Speichern fehlgeschlagen", errorText(e)),
  });
  const logo = useMutation({
    mutationFn: (f: File) => upload<Team>(`/api/admin/teams/${editing!.id}/logo`, f),
    onSuccess: (t) => {
      setForm((old) => ({ ...old, logo_url: t.logo_url ?? "" }));
      refresh();
      toast.success("Logo hochgeladen");
    },
    onError: (e) => toast.error("Upload fehlgeschlagen", errorText(e)),
  });
  const field = (key: keyof TeamForm, label: string, extra: Record<string, unknown> = {}) => (
    <Input label={label} value={String(form[key] ?? "")} onChange={(e) => setForm({ ...form, [key]: e.target.value })} {...extra} />
  );
  return (
    <Modal open={!!team} onClose={onClose} title={editing ? `${editing.name} bearbeiten` : "Team anlegen"} wide>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <div className="flex items-center gap-4 rounded-xl bg-white/[0.03] p-3">
          <TeamLogo team={{ ...form, logo_url: form.logo_url || null } as Team} size={72} glow />
          <div className="flex-1 space-y-2">
            {field("logo_url", "Logo-URL (/logos/KC.svg oder https://…)")}
            {editing && (
              <Button type="button" size="sm" onClick={() => file.current?.click()} loading={logo.isPending}>
                <Upload className="size-4" /> Logo hochladen (PNG/JPEG/WebP)
              </Button>
            )}
            <input ref={file} type="file" hidden accept="image/png,image/jpeg,image/webp,image/gif" onChange={(e) => e.target.files?.[0] && logo.mutate(e.target.files[0])} />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {field("name", "Teamname", { required: true })}
          {field("short_name", "Kurzname", { required: true })}
          {field("abbreviation", "Kürzel (2–4 Buchstaben)", { required: true, maxLength: 4, pattern: "[A-Za-z]{2,4}" })}
          {field("city", "Stadt")}
          <Select label="Conference" value={form.conference} onChange={(e) => setForm({ ...form, conference: e.target.value as Team["conference"] })}>
            <option value="AFC">AFC</option>
            <option value="NFC">NFC</option>
          </Select>
          {field("division", "Division")}
          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-slate-400">Primärfarbe</span>
            <input type="color" value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} className="h-11 w-full rounded-xl border border-white/10 bg-ink-900" />
          </label>
          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-slate-400">Sekundärfarbe</span>
            <input type="color" value={form.secondary_color} onChange={(e) => setForm({ ...form, secondary_color: e.target.value })} className="h-11 w-full rounded-xl border border-white/10 bg-ink-900" />
          </label>
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Abbrechen
          </Button>
          <Button type="submit" variant="primary" loading={save.isPending}>
            Speichern
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function TeamsAdmin() {
  const teams = useTeams();
  const [conf, setConf] = useState<"AFC" | "NFC">("AFC");
  const [editing, setEditing] = useState<Team | "new" | null>(null);
  if (teams.isLoading) return <Loading />;
  const list = (teams.data ?? []).filter((t) => t.conference === conf).sort((a, b) => (a.division ?? "").localeCompare(b.division ?? "") || a.name.localeCompare(b.name));
  return (
    <Card
      title="Teams"
      action={
        <Button size="sm" variant="primary" onClick={() => setEditing("new")}>
          <Plus className="size-4" /> Team anlegen
        </Button>
      }
    >
      <Tabs tabs={[{ value: "AFC", label: "AFC" }, { value: "NFC", label: "NFC" }]} value={conf} onChange={setConf} className="mb-4 w-fit" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {list.map((t) => (
          <button
            key={t.id}
            onClick={() => setEditing(t)}
            className="focus-ring flex items-center gap-3 rounded-xl border border-white/8 bg-white/[0.03] p-3 text-left transition hover:border-white/20"
          >
            <TeamLogo team={t} size={44} />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-semibold text-white">{t.name}</span>
              <span className="block text-xs text-slate-400">
                {t.abbreviation} · {t.conference} {t.division}
              </span>
            </span>
            <span className="flex gap-1">
              <span className="size-4 rounded-full ring-1 ring-white/20" style={{ background: t.primary_color }} />
              <span className="size-4 rounded-full ring-1 ring-white/20" style={{ background: t.secondary_color }} />
            </span>
          </button>
        ))}
      </div>
      {editing && <TeamModal key={editing === "new" ? "new" : editing.id} team={editing} onClose={() => setEditing(null)} />}
    </Card>
  );
}
