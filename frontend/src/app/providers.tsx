"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api";
import { AuthProvider } from "@/lib/auth";
import { RealtimeProvider } from "@/lib/realtime";
import { ToastProvider } from "@/lib/toast";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 20_000,
            refetchOnWindowFocus: true,
            // retry network/server errors, never client errors (401, 403, 404, 422 …)
            retry: (count, error) => count < 2 && !(error instanceof ApiError && error.status > 0 && error.status < 500),
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthProvider>
          <RealtimeProvider>{children}</RealtimeProvider>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
