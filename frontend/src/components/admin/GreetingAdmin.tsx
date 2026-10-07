"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Crown } from "lucide-react";
import { useEffect, useState } from "react";

import type { GreetingData } from "@/components/dashboard/Greeting";
import { Button, Card, Input } from "@/components/ui";
import { get, put } from "@/lib/api";
import { useToast } from "@/lib/toast";

import { errorText } from "./common";

/** Admin: who is shown as the reigning "König" in the dashboard greeting. */
export function GreetingAdmin() {
  const toast = useToast();
  const qc = useQueryClient();
  const data = useQuery({ queryKey: ["admin-greeting"], queryFn: () => get<GreetingData>("/api/admin/greeting") });
  const [name, setName] = useState("");
  const [title, setTitle] = useState("König");
  useEffect(() => {
    if (data.data) {
      setName(data.data.king_name ?? "");
      setTitle(data.data.king_title);
    }
  }, [data.data]);
  const save = useMutation({
    mutationFn: () => put<GreetingData>("/api/admin/greeting", { king_name: name, king_title: title }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["greeting"] });
      qc.invalidateQueries({ queryKey: ["admin-greeting"] });
      toast.success("Begrüßung gespeichert");
    },
    onError: (e) => toast.error("Nicht gespeichert", errorText(e)),
  });
  return (
    <Card title={<span className="flex items-center gap-2"><Crown className="size-4 text-gold" /> Begrüßung & König</span>}>
      <form
        className="grid gap-3 sm:grid-cols-[1fr_200px_auto] sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Input label="Gewinner des letzten Jahres" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="z. B. Dennis" />
        <Input label="Titel" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={40} />
        <Button type="submit" variant="primary" loading={save.isPending}>
          Speichern
        </Button>
      </form>
      <p className="mt-2 text-xs text-slate-500">Erscheint oben auf dem Dashboard neben der Begrüßung. Leer lassen, um nichts anzuzeigen.</p>
    </Card>
  );
}
