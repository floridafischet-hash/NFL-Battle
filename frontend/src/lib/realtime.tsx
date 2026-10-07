"use client";

import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { getToken } from "./api";
import { useAuth } from "./auth";
import { useToast } from "./toast";
import type { ChatMessage } from "./types";

interface RealtimeEvent {
  type: string;
  [key: string]: unknown;
}

const RealtimeContext = createContext<{ connected: boolean }>({ connected: false });

function wsUrl(): string {
  const configured = process.env.NEXT_PUBLIC_WS_URL;
  if (configured) return configured;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}

const MATCH_KEYS = ["matches", "match", "bracket", "dashboard", "admin-matches", "distribution", "compare", "brackets"];

function invalidate(qc: QueryClient, keys: string[]) {
  for (const key of keys) qc.invalidateQueries({ queryKey: [key] });
}

export function appendChatMessage(qc: QueryClient, message: ChatMessage) {
  qc.setQueryData<ChatMessage[]>(["chat"], (old) => {
    if (!old) return old;
    if (old.some((m) => m.id === message.id)) return old;
    return [...old, message].slice(-300);
  });
}

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [connected, setConnected] = useState(false);
  const toastRef = useRef(toast);
  toastRef.current = toast;

  useEffect(() => {
    if (status !== "authenticated") return;
    let socket: WebSocket | null = null;
    let stopped = false;
    let retry = 0;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let pingTimer: ReturnType<typeof setInterval> | undefined;

    const handle = (event: RealtimeEvent) => {
      switch (event.type) {
        case "chat_message": {
          const message = event.message as ChatMessage;
          appendChatMessage(qc, message);
          const sys = message.system?.type;
          if (sys === "FINAL" || sys === "CORRECTION" || sys === "CHAMPION" || sys === "NEXT_ROUND") {
            const [title, ...rest] = message.body.split("\n");
            toastRef.current.info(`NFL Bot · ${title}`, rest.filter(Boolean).slice(0, 2).join("\n"));
            invalidate(qc, ["stats", "hall-of-fame", "seasons"]);
          }
          break;
        }
        case "chat_message_deleted":
          invalidate(qc, ["chat"]);
          break;
        case "notification":
          invalidate(qc, ["notifications"]);
          break;
        case "leaderboard_updated":
          invalidate(qc, ["leaderboard", "dashboard", "brackets", "stats"]);
          break;
        case "match_updated":
          invalidate(qc, MATCH_KEYS);
          break;
        case "bracket_updated":
          invalidate(qc, ["brackets", "dashboard"]);
          break;
        case "season_updated":
          invalidate(qc, ["seasons", "dashboard", "hall-of-fame", "admin-seasons", "season-teams"]);
          break;
        case "teams_updated":
          invalidate(qc, ["teams", ...MATCH_KEYS]);
          break;
        case "presence":
          invalidate(qc, ["online"]);
          break;
        case "change_request_updated":
          invalidate(qc, ["change-requests", "admin-change-requests", "match", "bracket", "admin-summary"]);
          break;
      }
    };

    const connect = () => {
      const token = getToken();
      if (!token || stopped) return;
      socket = new WebSocket(wsUrl());
      socket.onopen = () => socket?.send(JSON.stringify({ type: "auth", token }));
      socket.onmessage = (msg) => {
        let event: RealtimeEvent;
        try {
          event = JSON.parse(msg.data);
        } catch {
          return;
        }
        if (event.type === "ready") {
          setConnected(true);
          // catch up on anything missed while disconnected
          if (retry > 0) invalidate(qc, ["chat", "notifications", ...MATCH_KEYS, "leaderboard"]);
          retry = 0;
          return;
        }
        handle(event);
      };
      socket.onclose = () => {
        setConnected(false);
        if (stopped) return;
        retry += 1;
        const delay = Math.min(30_000, 1000 * 2 ** Math.min(retry, 5)) + Math.random() * 500;
        retryTimer = setTimeout(connect, delay);
      };
    };

    connect();
    pingTimer = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) socket.send("ping");
    }, 25_000);
    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      clearInterval(pingTimer);
      socket?.close();
      setConnected(false);
    };
  }, [status, qc]);

  return <RealtimeContext.Provider value={{ connected }}>{children}</RealtimeContext.Provider>;
}

export function useRealtime() {
  return useContext(RealtimeContext);
}
