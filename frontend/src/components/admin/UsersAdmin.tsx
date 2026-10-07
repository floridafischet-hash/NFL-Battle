"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { KeyRound, ListChecks, Trash2, UserPlus } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { TeamLogo } from "@/components/TeamLogo";
import { Badge, Button, Card, Input, Loading, Modal, Select } from "@/components/ui";
import { del, get, patch, post } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { slotLabel } from "@/lib/bracket";
import { dateTime, relativeTime } from "@/lib/format";
import { useToast } from "@/lib/toast";
import type { Team } from "@/lib/types";

import { errorText, useAdminSeasons } from "./common";

interface AdminUser {
  id: string;
  username: string;
  display_name: string;
  avatar_url: string | null;
  role: "USER" | "ADMIN";
  is_active: boolean;
  is_superuser?: boolean;
  created_at: string;
  last_login_at: string | null;
  last_seen_at: string | null;
}

function CreateUserModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({ username: "", display_name: "", password: "", role: "USER" });
  const create = useMutation({
    mutationFn: () => post("/api/admin/users", form),
    onSuccess: () => {
      toast.success("Benutzer angelegt", `${form.display_name} kann sich jetzt mit „${form.username.toLowerCase()}“ anmelden.`);
      setForm({ username: "", display_name: "", password: "", role: "USER" });
      onDone();
      onClose();
    },
    onError: (e) => toast.error("Anlegen fehlgeschlagen", errorText(e)),
  });
  return (
    <Modal open={open} onClose={onClose} title="Benutzer anlegen">
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Input label="Benutzername (Login)" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required minLength={2} maxLength={32} pattern="[A-Za-z0-9._\-]+" autoComplete="off" />
        <Input label="Anzeigename" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} required maxLength={80} />
        <Input label="Passwort (min. 6 Zeichen)" type="text" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={6} autoComplete="off" />
        <Select label="Rolle" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
          <option value="USER">Spieler</option>
          <option value="ADMIN">Admin</option>
        </Select>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" onClick={onClose}>
            Abbrechen
          </Button>
          <Button type="submit" variant="primary" loading={create.isPending}>
            Anlegen
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function PredictionsModal({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  const seasons = useAdminSeasons();
  const [seasonId, setSeasonId] = useState<number | null>(null);
  const sid = seasonId ?? seasons.data?.[0]?.id ?? null;
  const data = useQuery({
    queryKey: ["admin-predictions", user?.id, sid],
    queryFn: () =>
      get<{ predictions: { match: { slot: string; status: string; home_team: Team | null; away_team: Team | null }; winner_team: Team; winner_score: number | null; loser_score: number | null; updated_at: string; updated_via: string }[] }>(
        `/api/admin/users/${user!.id}/predictions?season_id=${sid}`,
      ),
    enabled: !!user && sid != null,
  });
  return (
    <Modal open={!!user} onClose={onClose} title={`Tipps von ${user?.display_name ?? ""}`} wide>
      <div className="mb-3 max-w-xs">
        <Select value={sid ?? ""} onChange={(e) => setSeasonId(Number(e.target.value))} aria-label="Saison">
          {(seasons.data ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      </div>
      {data.isLoading ? (
        <Loading />
      ) : (
        <table className="w-full text-sm">
          <thead className="text-[11px] text-slate-500 uppercase">
            <tr>
              <th className="py-2 text-left">Spiel</th>
              <th className="py-2 text-left">Tipp</th>
              <th className="py-2 text-left">Geändert</th>
            </tr>
          </thead>
          <tbody>
            {data.data?.predictions.map((p) => (
              <tr key={p.match.slot} className="border-t border-white/5">
                <td className="py-2">
                  {slotLabel(p.match.slot)} <span className="text-xs text-slate-500">({p.match.status})</span>
                </td>
                <td className="py-2">
                  <span className="flex items-center gap-2">
                    <TeamLogo team={p.winner_team} size={20} /> {p.winner_team.short_name}
                    {p.winner_score != null && <span className="text-xs text-slate-400">{p.winner_score}:{p.loser_score}</span>}
                  </span>
                </td>
                <td className="py-2 text-xs text-slate-400">
                  {dateTime(p.updated_at)} · {p.updated_via}
                </td>
              </tr>
            ))}
            {data.data?.predictions.length === 0 && (
              <tr>
                <td colSpan={3} className="py-4 text-center text-slate-500">
                  Keine Tipps
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </Modal>
  );
}

export function UsersAdmin() {
  const me = useMe();
  const owner = !!me.is_superuser; // only the instance owner manages users
  const toast = useToast();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => get<AdminUser[]>("/api/admin/users") });
  const [creating, setCreating] = useState(false);
  const [resetUser, setResetUser] = useState<AdminUser | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [tipsUser, setTipsUser] = useState<AdminUser | null>(null);
  const [deleteUser, setDeleteUser] = useState<AdminUser | null>(null);

  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) => patch(`/api/admin/users/${id}`, body),
    onSuccess: () => {
      users.refetch();
      toast.success("Benutzer aktualisiert");
    },
    onError: (e) => toast.error("Änderung fehlgeschlagen", errorText(e)),
  });
  const reset = useMutation({
    mutationFn: () => post(`/api/admin/users/${resetUser!.id}/password`, { password: newPassword }),
    onSuccess: () => {
      toast.success("Passwort zurückgesetzt", "Der Benutzer wurde auf allen Geräten abgemeldet.");
      setResetUser(null);
      setNewPassword("");
    },
    onError: (e) => toast.error("Zurücksetzen fehlgeschlagen", errorText(e)),
  });
  const remove = useMutation({
    mutationFn: () => del(`/api/admin/users/${deleteUser!.id}`),
    onSuccess: () => {
      toast.success("Benutzer gelöscht", `${deleteUser?.display_name ?? "Der Benutzer"} wurde dauerhaft entfernt.`);
      setDeleteUser(null);
      users.refetch();
    },
    onError: (e) => toast.error("Löschen fehlgeschlagen", errorText(e)),
  });

  return (
    <Card
      title="Benutzer"
      action={
        owner ? (
          <Button size="sm" variant="primary" onClick={() => setCreating(true)}>
            <UserPlus className="size-4" /> Benutzer anlegen
          </Button>
        ) : (
          <span className="text-xs text-slate-400">Benutzer verwaltet nur der Inhaber der Instanz.</span>
        )
      }
      bodyClassName="p-0"
    >
      {users.isLoading ? (
        <Loading />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead className="text-[11px] tracking-wider text-slate-500 uppercase">
              <tr className="border-b border-white/5">
                <th className="px-4 py-3 text-left">Benutzer</th>
                <th className="px-3 py-3 text-left">Rolle</th>
                <th className="px-3 py-3 text-left">Status</th>
                <th className="px-3 py-3 text-left">Letzter Login</th>
                <th className="px-4 py-3 text-right">Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {users.data?.map((u) => (
                <tr key={u.id} className={clsx("border-b border-white/5 last:border-0", !u.is_active && "opacity-60")}>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-3">
                      <Avatar user={u} size={32} />
                      <span>
                        <span className="block font-semibold text-white">{u.display_name}</span>
                        <span className="block text-xs text-slate-500">@{u.username}</span>
                      </span>
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <Select
                      value={u.role}
                      disabled={!owner || u.id === me.id || !!u.is_superuser}
                      onChange={(e) => update.mutate({ id: u.id, body: { role: e.target.value } })}
                      className="min-h-9 w-32 py-1"
                      aria-label={`Rolle von ${u.display_name}`}
                    >
                      <option value="USER">Spieler</option>
                      <option value="ADMIN">Admin</option>
                    </Select>
                  </td>
                  <td className="px-3 py-3">{u.is_active ? <Badge tone="green">aktiv</Badge> : <Badge tone="red">gesperrt</Badge>}</td>
                  <td className="px-3 py-3 text-xs text-slate-400">{u.last_login_at ? relativeTime(u.last_login_at) : "nie"}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1.5">
                      <Button size="sm" variant="ghost" onClick={() => setTipsUser(u)} title="Tipps ansehen">
                        <ListChecks className="size-4" /> Tipps
                      </Button>
                      {owner && (
                        <Button size="sm" variant="ghost" onClick={() => setResetUser(u)} title="Passwort zurücksetzen">
                          <KeyRound className="size-4" /> Passwort
                        </Button>
                      )}
                      {owner && u.id !== me.id && !u.is_superuser &&
                        (u.is_active ? (
                          <Button size="sm" variant="danger" onClick={() => update.mutate({ id: u.id, body: { is_active: false } })}>
                            Sperren
                          </Button>
                        ) : (
                          <Button size="sm" variant="success" onClick={() => update.mutate({ id: u.id, body: { is_active: true } })}>
                            Aktivieren
                          </Button>
                        ))}
                      {u.id !== me.id && (
                        <Button size="sm" variant="danger" onClick={() => setDeleteUser(u)} title="Benutzer dauerhaft löschen">
                          <Trash2 className="size-4" /> Löschen
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <CreateUserModal open={creating} onClose={() => setCreating(false)} onDone={() => users.refetch()} />
      <Modal open={!!resetUser} onClose={() => setResetUser(null)} title={`Passwort für ${resetUser?.display_name ?? ""}`}>
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            reset.mutate();
          }}
        >
          <Input label="Neues Passwort (min. 6 Zeichen)" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} minLength={6} required autoComplete="off" />
          <div className="flex justify-end gap-2">
            <Button type="button" onClick={() => setResetUser(null)}>
              Abbrechen
            </Button>
            <Button type="submit" variant="primary" loading={reset.isPending}>
              Setzen
            </Button>
          </div>
        </form>
      </Modal>
      <Modal open={!!deleteUser} onClose={() => setDeleteUser(null)} title={`Benutzer ${deleteUser?.display_name ?? ""} löschen?`}>
        <div className="space-y-4">
          <p className="text-sm text-slate-300">
            Der Benutzer <strong className="text-white">@{deleteUser?.username}</strong> sowie seine Tipps, Punkte,
            Chatnachrichten und Benachrichtigungen werden dauerhaft gelöscht. Die Audit-Historie bleibt erhalten.
          </p>
          <p className="text-sm font-semibold text-red-300">Diese Aktion kann nicht rückgängig gemacht werden.</p>
          <div className="flex justify-end gap-2">
            <Button type="button" onClick={() => setDeleteUser(null)}>
              Abbrechen
            </Button>
            <Button type="button" variant="danger" loading={remove.isPending} onClick={() => remove.mutate()}>
              Dauerhaft löschen
            </Button>
          </div>
        </div>
      </Modal>
      <PredictionsModal user={tipsUser} onClose={() => setTipsUser(null)} />
    </Card>
  );
}
