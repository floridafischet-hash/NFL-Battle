"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ChevronRight } from "lucide-react";
import { Fragment, useState } from "react";

import { Badge, Button, Card, Input, Loading, Select } from "@/components/ui";
import { get } from "@/lib/api";
import { dateTime } from "@/lib/format";

interface AuditItem {
  id: number;
  created_at: string;
  actor_type: string;
  actor_label: string;
  action: string;
  object_type: string;
  object_id: string | null;
  old_value: unknown;
  new_value: unknown;
  source: string;
  ip_address: string | null;
}
interface AuditPage {
  items: AuditItem[];
  next_before: number | null;
  actions: string[];
}

const ACTOR_TONE: Record<string, "neutral" | "gold" | "nfc" | "afc"> = { USER: "neutral", ADMIN: "gold", AGENT: "nfc", SYSTEM: "afc" };

export function AuditAdmin() {
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const query = useInfiniteQuery({
    queryKey: ["audit", action, actor, q],
    initialPageParam: null as number | null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: "50" });
      if (action) params.set("action", action);
      if (actor) params.set("actor_type", actor);
      if (q) params.set("q", q);
      if (pageParam) params.set("before", String(pageParam));
      return get<AuditPage>(`/api/admin/audit?${params}`);
    },
    getNextPageParam: (last) => last.next_before,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  const actions = query.data?.pages[0]?.actions ?? [];

  return (
    <Card title="Audit-Log (unveränderlich)">
      <div className="mb-4 grid gap-2 sm:grid-cols-3">
        <Select value={action} onChange={(e) => setAction(e.target.value)} aria-label="Aktion filtern">
          <option value="">Alle Aktionen</option>
          {actions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </Select>
        <Select value={actor} onChange={(e) => setActor(e.target.value)} aria-label="Akteur filtern">
          <option value="">Alle Akteure</option>
          <option value="USER">Benutzer</option>
          <option value="ADMIN">Admin</option>
          <option value="AGENT">ChatGPT-Agent</option>
          <option value="SYSTEM">System</option>
        </Select>
        <Input placeholder="Suche (Name, Aktion, Objekt-ID)" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {query.isLoading && <Loading />}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="text-[11px] tracking-wider text-slate-500 uppercase">
            <tr className="border-b border-white/5">
              <th className="w-6" />
              <th className="px-2 py-2 text-left">Zeitpunkt</th>
              <th className="px-2 py-2 text-left">Wer</th>
              <th className="px-2 py-2 text-left">Aktion</th>
              <th className="px-2 py-2 text-left">Objekt</th>
              <th className="px-2 py-2 text-left">Quelle</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <Fragment key={a.id}>
                <tr className="cursor-pointer border-b border-white/5 hover:bg-white/[0.03]" onClick={() => setOpen(open === a.id ? null : a.id)}>
                  <td className="pl-2">
                    <ChevronRight className={clsx("size-4 text-slate-500 transition", open === a.id && "rotate-90")} />
                  </td>
                  <td className="px-2 py-2 text-xs whitespace-nowrap text-slate-400">{dateTime(a.created_at)}</td>
                  <td className="px-2 py-2">
                    <span className="flex items-center gap-2">
                      <Badge tone={ACTOR_TONE[a.actor_type] ?? "neutral"}>{a.actor_type}</Badge>
                      <span className="text-slate-200">{a.actor_label}</span>
                    </span>
                  </td>
                  <td className="px-2 py-2 font-mono text-xs text-white">{a.action}</td>
                  <td className="px-2 py-2 text-xs text-slate-400">
                    {a.object_type}
                    {a.object_id ? ` #${a.object_id}` : ""}
                  </td>
                  <td className="px-2 py-2 text-xs text-slate-400">{a.source}</td>
                </tr>
                {open === a.id && (
                  <tr className="border-b border-white/5 bg-black/20">
                    <td />
                    <td colSpan={5} className="px-2 py-3">
                      <div className="grid gap-3 md:grid-cols-2">
                        <div>
                          <p className="mb-1 text-[10px] font-bold tracking-widest text-slate-500 uppercase">Vorher</p>
                          <pre className="scrollbar-thin max-h-60 overflow-auto rounded-lg bg-black/40 p-2 text-[11px] text-slate-300">{JSON.stringify(a.old_value, null, 2) ?? "–"}</pre>
                        </div>
                        <div>
                          <p className="mb-1 text-[10px] font-bold tracking-widest text-slate-500 uppercase">Nachher</p>
                          <pre className="scrollbar-thin max-h-60 overflow-auto rounded-lg bg-black/40 p-2 text-[11px] text-slate-300">{JSON.stringify(a.new_value, null, 2) ?? "–"}</pre>
                        </div>
                      </div>
                      {a.ip_address && <p className="mt-2 text-[11px] text-slate-500">IP: {a.ip_address}</p>}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {query.hasNextPage && (
        <div className="mt-4 text-center">
          <Button onClick={() => query.fetchNextPage()} loading={query.isFetchingNextPage}>
            Ältere Einträge laden
          </Button>
        </div>
      )}
    </Card>
  );
}
