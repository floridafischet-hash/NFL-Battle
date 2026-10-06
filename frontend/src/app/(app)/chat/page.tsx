"use client";

import { MessageSquare } from "lucide-react";

import { Avatar } from "@/components/Avatar";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { Card } from "@/components/ui";
import { useOnline } from "@/lib/queries";
import { useRealtime } from "@/lib/realtime";

export default function ChatPage() {
  const online = useOnline();
  const { connected } = useRealtime();
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
      <Card
        title={
          <span className="flex items-center gap-2">
            <MessageSquare className="size-4 text-gold" /> Playoff Chat
          </span>
        }
        action={<span className="text-xs text-slate-400">{connected ? "Live verbunden" : "Verbindung wird aufgebaut …"}</span>}
        bodyClassName="p-0"
      >
        <ChatPanel className="h-[calc(100dvh-210px)] min-h-[420px]" />
      </Card>
      <Card title={`Online (${online.data?.length ?? 0})`} className="hidden xl:block">
        <ul className="space-y-2">
          {(online.data ?? []).map((u) => (
            <li key={u.id} className="flex items-center gap-3">
              <span className="relative">
                <Avatar user={u} size={32} />
                <span className="absolute -right-0.5 -bottom-0.5 size-3 rounded-full border-2 border-ink-900 bg-emerald-400" />
              </span>
              <span className="text-sm font-semibold text-slate-100">{u.display_name}</span>
            </li>
          ))}
          {!online.data?.length && <li className="text-sm text-slate-500">Niemand online</li>}
        </ul>
      </Card>
    </div>
  );
}
