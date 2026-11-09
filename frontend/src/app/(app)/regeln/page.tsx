"use client";

import { ExternalLink, Search, X } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

const RULEBOOK_URL = "https://static.www.nfl.com/image/upload/fl_attachment/league/tqivdkzt9mu6wdgsh1ku.pdf";

export default function RulesPage() {
  const [input, setInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const documentUrl = useMemo(() => {
    const term = searchTerm.trim();
    return term ? `${RULEBOOK_URL}#search=${encodeURIComponent(term)}` : RULEBOOK_URL;
  }, [searchTerm]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearchTerm(input.trim());
  }

  function clearSearch() {
    setInput("");
    setSearchTerm("");
  }

  return (
    <div className="space-y-5">
      <section className="glass overflow-hidden rounded-3xl p-5 sm:p-7">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs font-bold tracking-[0.2em] text-gold uppercase">Offizielles Regelwerk 2026</p>
            <h1 className="display mt-2 text-3xl font-bold text-white sm:text-4xl">NFL Regeln</h1>
            <p className="mt-2 text-sm leading-6 text-slate-400 sm:text-base">
              Das vollständige offizielle NFL-Regelwerk. Suche nach Schlagwörtern wie „holding“, „overtime“
              oder „pass interference“.
            </p>
          </div>

          <a
            href={documentUrl}
            target="_blank"
            rel="noreferrer"
            className="focus-ring inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 text-sm font-semibold text-slate-200 transition hover:border-gold/40 hover:text-white"
          >
            Im Vollbild öffnen <ExternalLink className="size-4" />
          </a>
        </div>

        <form onSubmit={submitSearch} className="mt-6 flex flex-col gap-2 sm:flex-row" role="search">
          <label className="relative min-w-0 flex-1">
            <span className="sr-only">Regelwerk durchsuchen</span>
            <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-slate-500" />
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Schlagwort suchen …"
              className="focus-ring min-h-12 w-full rounded-xl border border-white/10 bg-ink-950/60 pr-12 pl-12 text-base text-white placeholder:text-slate-500"
            />
            {input && (
              <button
                type="button"
                onClick={clearSearch}
                className="focus-ring absolute top-1/2 right-2 flex size-9 -translate-y-1/2 items-center justify-center rounded-lg text-slate-400 hover:bg-white/5 hover:text-white"
                aria-label="Suche löschen"
              >
                <X className="size-4" />
              </button>
            )}
          </label>
          <button
            type="submit"
            className="focus-ring min-h-12 rounded-xl bg-gold px-6 text-sm font-bold text-ink-950 transition hover:brightness-110"
          >
            Suchen
          </button>
        </form>

        {searchTerm && (
          <p className="mt-3 text-sm text-slate-400" aria-live="polite">
            Treffer für <span className="font-semibold text-white">„{searchTerm}“</span> werden im Dokument markiert.
          </p>
        )}
      </section>

      <section className="glass overflow-hidden rounded-3xl">
        <div className="border-b border-white/5 px-5 py-3 text-xs text-slate-500 sm:px-6">
          Quelle: NFL Football Operations · 2026 NFL Rulebook · englisches Original
        </div>
        <iframe
          key={documentUrl}
          src={documentUrl}
          title="2026 NFL Rulebook"
          className="h-[72vh] min-h-[620px] w-full bg-white"
        />
        <div className="border-t border-white/5 px-5 py-4 text-sm text-slate-400 sm:hidden">
          Falls dein Mobilbrowser das Dokument nicht einbettet, nutze „Im Vollbild öffnen“.
        </div>
      </section>
    </div>
  );
}
