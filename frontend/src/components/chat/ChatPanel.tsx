"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ImagePlus, Loader2, SendHorizonal, Smile, Trash2, X } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

import { Avatar } from "@/components/Avatar";
import { del, get, post, upload } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { chatTime } from "@/lib/format";
import { useChat } from "@/lib/queries";
import { appendChatMessage } from "@/lib/realtime";
import { useToast } from "@/lib/toast";
import type { ChatMessage } from "@/lib/types";

import { BotMessage } from "./BotMessage";

const EMOJIS = [
  "🏈", "🏆", "🔥", "💪", "😂", "😅", "😎", "🤯", "😭", "😤", "🙈", "🤞", "👏", "🙌", "👀", "💯",
  "🎯", "✅", "❌", "⚡", "🍕", "🍺", "🧀", "🦅", "🦬", "🐻", "🦁", "🐬", "🏟️", "📣", "🤝", "🫡",
];

function UserMessage({ message, mine, canDelete, compact, onDelete }: {
  message: ChatMessage;
  mine: boolean;
  canDelete: boolean;
  compact?: boolean;
  onDelete: () => void;
}) {
  return (
    <div className={clsx("group flex gap-2.5", mine && "flex-row-reverse")}>
      <Avatar user={message.user} size={compact ? 30 : 36} />
      <div className={clsx("min-w-0 max-w-[85%]", mine && "items-end text-right")}>
        <div className={clsx("mb-0.5 flex items-baseline gap-2", mine && "flex-row-reverse")}>
          <span className={clsx("text-xs font-semibold", mine ? "text-gold" : "text-slate-200")}>{message.user.display_name}</span>
          <span className="text-[10px] text-slate-500">{chatTime(message.created_at)}</span>
          {canDelete && !message.deleted && (
            <button
              onClick={onDelete}
              className="rounded p-0.5 text-slate-600 opacity-0 transition group-hover:opacity-100 hover:text-red-400 focus:opacity-100"
              aria-label="Nachricht löschen"
            >
              <Trash2 className="size-3.5" />
            </button>
          )}
        </div>
        <div
          className={clsx(
            "inline-block rounded-2xl px-3 py-2 text-left text-sm break-words whitespace-pre-wrap",
            mine ? "rounded-tr-sm bg-gold/15 text-slate-100 ring-1 ring-gold/25" : "rounded-tl-sm bg-white/[0.06] text-slate-100",
            message.deleted && "italic text-slate-500",
          )}
        >
          {message.deleted ? "Nachricht gelöscht" : message.body}
          {message.image_url && !message.deleted && (
            <a href={message.image_url} target="_blank" rel="noreferrer" className="mt-1 block">
              <img src={message.image_url} alt="Bild im Chat" className="max-h-60 rounded-xl" loading="lazy" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export function ChatPanel({ compact, className }: { compact?: boolean; className?: string }) {
  const me = useMe();
  const qc = useQueryClient();
  const toast = useToast();
  const chat = useChat();
  const [text, setText] = useState("");
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [image, setImage] = useState<{ id: string; url: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasOlder, setHasOlder] = useState(true);
  const scroller = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const fileInput = useRef<HTMLInputElement>(null);
  const messages = chat.data ?? [];

  const send = useMutation({
    mutationFn: () => post<ChatMessage>("/api/chat/messages", { body: text, upload_id: image?.id ?? null }),
    onSuccess: (msg) => {
      appendChatMessage(qc, msg);
      setText("");
      setImage(null);
      stickToBottom.current = true;
    },
    onError: (err) => toast.error("Nachricht nicht gesendet", err instanceof Error ? err.message : undefined),
  });

  useLayoutEffect(() => {
    const el = scroller.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const onScroll = () => {
      stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    };
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  const loadOlder = async () => {
    if (!messages.length) return;
    setLoadingOlder(true);
    try {
      const el = scroller.current;
      const before = el?.scrollHeight ?? 0;
      const older = await get<ChatMessage[]>(`/api/chat/messages?before=${messages[0].id}&limit=50`);
      if (older.length < 50) setHasOlder(false);
      stickToBottom.current = false;
      qc.setQueryData<ChatMessage[]>(["chat"], (old) => [...older, ...(old ?? [])]);
      requestAnimationFrame(() => {
        if (el) el.scrollTop = el.scrollHeight - before;
      });
    } catch (err) {
      toast.error("Konnte ältere Nachrichten nicht laden", err instanceof Error ? err.message : undefined);
    } finally {
      setLoadingOlder(false);
    }
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    try {
      const res = await upload<{ id: string; url: string }>("/api/chat/uploads", file);
      setImage(res);
    } catch (err) {
      toast.error("Bild-Upload fehlgeschlagen", err instanceof Error ? err.message : undefined);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const remove = async (id: number) => {
    try {
      await del(`/api/chat/messages/${id}`);
      qc.invalidateQueries({ queryKey: ["chat"] });
    } catch (err) {
      toast.error("Löschen fehlgeschlagen", err instanceof Error ? err.message : undefined);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if ((text.trim() || image) && !send.isPending) send.mutate();
    }
  };

  return (
    <div className={clsx("flex min-h-0 flex-col", className)}>
      <div ref={scroller} className="scrollbar-thin min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-3 sm:px-4" data-testid="chat-messages">
        {!compact && hasOlder && messages.length >= 50 && (
          <div className="text-center">
            <button onClick={loadOlder} className="text-xs font-semibold text-slate-400 hover:text-white" disabled={loadingOlder}>
              {loadingOlder ? "Lädt …" : "Ältere Nachrichten laden"}
            </button>
          </div>
        )}
        {chat.isLoading && (
          <div className="flex justify-center py-6">
            <Loader2 className="size-5 animate-spin text-slate-500" />
          </div>
        )}
        {(compact ? messages.slice(-25) : messages).map((m) =>
          m.user.is_bot ? (
            <div key={m.id} className="flex gap-2.5">
              <Avatar user={m.user} size={compact ? 30 : 36} />
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-baseline gap-2">
                  <span className="text-xs font-bold text-gold">NFL Bot</span>
                  <span className="rounded bg-gold/15 px-1 text-[9px] font-bold text-gold">BOT</span>
                  <span className="text-[10px] text-slate-500">{chatTime(m.created_at)}</span>
                </div>
                <BotMessage message={m} compact={compact} />
              </div>
            </div>
          ) : (
            <UserMessage
              key={m.id}
              message={m}
              mine={m.user.id === me.id}
              canDelete={m.user.id === me.id || me.is_admin}
              compact={compact}
              onDelete={() => remove(m.id)}
            />
          ),
        )}
      </div>

      <div className="relative border-t border-white/5 p-2 sm:p-3">
        {image && (
          <div className="mb-2 flex items-center gap-2 rounded-xl bg-white/5 p-2">
            <img src={image.url} alt="Vorschau" className="size-12 rounded-lg object-cover" />
            <span className="flex-1 text-xs text-slate-300">Bild angehängt</span>
            <button onClick={() => setImage(null)} className="rounded p-1 text-slate-400 hover:text-white" aria-label="Bild entfernen">
              <X className="size-4" />
            </button>
          </div>
        )}
        {emojiOpen && (
          <div className="glass absolute right-2 bottom-full left-2 z-20 mb-2 grid grid-cols-8 gap-1 rounded-2xl p-2 sm:left-auto sm:w-80">
            {EMOJIS.map((e) => (
              <button
                key={e}
                onClick={() => {
                  setText((t) => t + e);
                  setEmojiOpen(false);
                }}
                className="flex size-9 items-center justify-center rounded-lg text-xl hover:bg-white/10"
              >
                {e}
              </button>
            ))}
          </div>
        )}
        <div className="flex items-end gap-1.5">
          <button
            onClick={() => setEmojiOpen((v) => !v)}
            className="focus-ring flex size-11 shrink-0 items-center justify-center rounded-xl text-slate-400 hover:bg-white/5 hover:text-gold"
            aria-label="Emoji einfügen"
          >
            <Smile className="size-5" />
          </button>
          <button
            onClick={() => fileInput.current?.click()}
            className="focus-ring flex size-11 shrink-0 items-center justify-center rounded-xl text-slate-400 hover:bg-white/5 hover:text-gold"
            aria-label="Bild anhängen"
            disabled={uploading}
          >
            {uploading ? <Loader2 className="size-5 animate-spin" /> : <ImagePlus className="size-5" />}
          </button>
          <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={(e) => onFile(e.target.files?.[0])} />
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, 1000))}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Nachricht schreiben …"
            className="focus-ring max-h-32 min-h-11 flex-1 resize-none rounded-xl border border-white/10 bg-ink-900/80 px-3 py-2.5 text-sm text-white placeholder:text-slate-500"
            aria-label="Chat-Nachricht"
            data-testid="chat-input"
          />
          <button
            onClick={() => send.mutate()}
            disabled={(!text.trim() && !image) || send.isPending}
            className="focus-ring flex size-11 shrink-0 items-center justify-center rounded-xl bg-gold text-ink-950 transition hover:brightness-110 disabled:opacity-40"
            aria-label="Senden"
            data-testid="chat-send"
          >
            {send.isPending ? <Loader2 className="size-5 animate-spin" /> : <SendHorizonal className="size-5" />}
          </button>
        </div>
      </div>
    </div>
  );
}
