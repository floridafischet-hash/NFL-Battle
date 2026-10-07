"use client";

import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { Button, Card, Input, PageHeader } from "@/components/ui";
import { del, patch, post, upload } from "@/lib/api";
import { useAuth, useMe } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import type { Me } from "@/lib/types";

export default function ProfilePage() {
  const me = useMe();
  const { setUser, setSession } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(me.display_name);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const file = useRef<HTMLInputElement>(null);

  const saveName = useMutation({
    mutationFn: () => patch<Me>("/api/me", { display_name: name }),
    onSuccess: (u) => {
      setUser(u);
      toast.success("Profil gespeichert");
    },
    onError: (e) => toast.error("Speichern fehlgeschlagen", e instanceof Error ? e.message : undefined),
  });
  const avatar = useMutation({
    mutationFn: (f: File) => upload<Me>("/api/me/avatar", f),
    onSuccess: (u) => {
      setUser(u);
      toast.success("Avatar aktualisiert");
    },
    onError: (e) => toast.error("Upload fehlgeschlagen", e instanceof Error ? e.message : undefined),
  });
  const removeAvatar = useMutation({
    mutationFn: () => del<Me>("/api/me/avatar"),
    onSuccess: (u) => setUser(u),
  });
  const password = useMutation({
    mutationFn: () => post<{ access_token: string; user: Me }>("/api/me/password", { current_password: current, new_password: next }),
    onSuccess: (res) => {
      setSession(res.access_token, res.user);
      setCurrent("");
      setNext("");
      setRepeat("");
      toast.success("Passwort geändert", "Andere Geräte wurden abgemeldet.");
    },
    onError: (e) => toast.error("Passwort nicht geändert", e instanceof Error ? e.message : undefined),
  });

  return (
    <div className="max-w-3xl space-y-5">
      <PageHeader title="Profil" subtitle={`Angemeldet als ${me.username}${me.is_admin ? " · Admin" : ""}`} />
      <Card title="Avatar & Anzeigename">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
          <div className="flex items-center gap-4">
            <Avatar user={me} size={84} ring />
            <div className="flex flex-col gap-2">
              <Button size="sm" onClick={() => file.current?.click()} loading={avatar.isPending}>
                Bild hochladen
              </Button>
              {me.avatar_url && (
                <Button size="sm" variant="ghost" onClick={() => removeAvatar.mutate()}>
                  Entfernen
                </Button>
              )}
              <input ref={file} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={(e) => e.target.files?.[0] && avatar.mutate(e.target.files[0])} />
            </div>
          </div>
          <form
            className="flex flex-1 items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              saveName.mutate();
            }}
          >
            <Input label="Anzeigename" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required />
            <Button type="submit" variant="primary" loading={saveName.isPending} disabled={name.trim() === me.display_name}>
              Speichern
            </Button>
          </form>
        </div>
      </Card>
      <Card title="Passwort ändern">
        <form
          className="grid gap-3 sm:grid-cols-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (next !== repeat) return toast.error("Die neuen Passwörter stimmen nicht überein");
            password.mutate();
          }}
        >
          <Input label="Aktuelles Passwort" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
          <Input label="Neues Passwort (min. 6 Zeichen)" type="password" autoComplete="new-password" minLength={6} value={next} onChange={(e) => setNext(e.target.value)} required />
          <Input label="Wiederholen" type="password" autoComplete="new-password" minLength={6} value={repeat} onChange={(e) => setRepeat(e.target.value)} required />
          <div className="sm:col-span-3">
            <Button type="submit" variant="primary" loading={password.isPending}>
              Passwort ändern
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
