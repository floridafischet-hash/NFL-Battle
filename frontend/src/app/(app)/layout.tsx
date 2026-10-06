"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { AppShell } from "@/components/AppShell";
import { BrandMark } from "@/components/Brand";
import { useAuth } from "@/lib/auth";

export default function AppLayout({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);
  if (status !== "authenticated") {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <div className="stadium-bg" aria-hidden />
        <BrandMark size={64} className="animate-pulse" />
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}
