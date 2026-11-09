"use client";

import clsx from "clsx";
import { Download, Share } from "lucide-react";
import { useState } from "react";

import { useInstallPrompt } from "@/lib/pwa";

export function PwaInstallButton({ className }: { className?: string }) {
  const pwa = useInstallPrompt();
  const [showIosHelp, setShowIosHelp] = useState(false);

  if (pwa.installed || (!pwa.canInstall && !pwa.iosHint)) return null;

  return (
    <div className={className}>
      <button
        type="button"
        onClick={() => (pwa.canInstall ? void pwa.install() : setShowIosHelp((value) => !value))}
        className="focus-ring flex min-h-11 w-full items-center gap-3 rounded-xl border border-gold/20 bg-gold/8 px-3 text-left text-sm font-semibold text-gold transition hover:border-gold/40 hover:bg-gold/12"
        aria-expanded={pwa.iosHint ? showIosHelp : undefined}
      >
        {pwa.canInstall ? <Download className="size-5 shrink-0" /> : <Share className="size-5 shrink-0" />}
        {pwa.canInstall ? "App installieren" : "Als App installieren"}
      </button>
      {showIosHelp && (
        <p className={clsx("mt-2 rounded-xl bg-white/5 p-3 text-xs leading-relaxed text-slate-300")}>
          Auf dem iPhone in Safari auf <strong>Teilen</strong> tippen und danach <strong>„Zum Home-Bildschirm“</strong> wählen.
        </p>
      )}
    </div>
  );
}
