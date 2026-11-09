"use client";

import { BookOpenText, ExternalLink, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { RULE_CHAPTERS } from "./rules";

const QUICK_SEARCHES = ["Holding", "Pass Interference", "Overtime", "Touchdown", "Kickoff", "Replay"];
const normalize = (value: string) => value.toLocaleLowerCase("de-DE").normalize("NFD").replace(/[\u0300-\u036f]/g, "");

export default function RulesPage() {
  const [query, setQuery] = useState("");
  const search = normalize(query.trim());
  const chapters = useMemo(() => {
    if (!search) return RULE_CHAPTERS;
    return RULE_CHAPTERS.filter((chapter) => normalize([
      chapter.title, chapter.summary, ...chapter.keywords,
      ...chapter.sections.flatMap((section) => [section.title, section.text]),
    ].join(" ")).includes(search));
  }, [search]);

  const clearSearch = () => setQuery("");

  return (
    <div className="space-y-5">
      <section className="glass overflow-hidden rounded-3xl p-5 sm:p-7">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-bold tracking-[0.2em] text-gold uppercase">NFL-Regelguide 2026 · Deutsch</p>
            <h1 className="display mt-2 text-3xl font-bold text-white sm:text-4xl">NFL Regeln verständlich erklärt</h1>
            <p className="mt-2 text-sm leading-6 text-slate-400 sm:text-base">
              Alle 19 Regelbereiche des offiziellen NFL-Regelwerks – kompakt auf Deutsch, durchsuchbar und für Fans erklärt.
            </p>
          </div>
          <a href="https://operations.nfl.com/rules-officiating/2026-nfl-rulebook" target="_blank" rel="noreferrer" className="focus-ring inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 text-sm font-semibold text-slate-200 transition hover:border-gold/40 hover:text-white">
            Offizielles Regelwerk (EN) <ExternalLink className="size-4" />
          </a>
        </div>

        <div className="relative mt-6">
          <Search className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-slate-500" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Regel, Begriff oder Strafe suchen …" className="focus-ring min-h-13 w-full rounded-xl border border-white/10 bg-ink-950/60 pr-12 pl-12 text-base text-white placeholder:text-slate-500" aria-label="Regelwerk durchsuchen" type="search" />
          {query && <button type="button" onClick={clearSearch} className="focus-ring absolute top-1/2 right-2 flex size-9 -translate-y-1/2 items-center justify-center rounded-lg text-slate-400 hover:bg-white/5 hover:text-white" aria-label="Suche löschen"><X className="size-4" /></button>}
        </div>
        <div className="mt-3 flex flex-wrap gap-2" aria-label="Beliebte Suchbegriffe">
          {QUICK_SEARCHES.map((term) => <button key={term} type="button" onClick={() => setQuery(term)} className="focus-ring rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-semibold text-slate-300 transition hover:border-gold/40 hover:text-white">{term}</button>)}
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[230px_minmax(0,1fr)]">
        <aside className="glass hidden self-start rounded-2xl p-3 lg:sticky lg:top-20 lg:block">
          <p className="px-3 pb-2 text-[11px] font-bold tracking-wider text-slate-500 uppercase">Kapitel</p>
          <nav className="scrollbar-thin max-h-[calc(100vh-8rem)] overflow-y-auto" aria-label="Regelkapitel">
            {RULE_CHAPTERS.map((chapter) => <a key={chapter.number} href={`#regel-${chapter.number}`} className="focus-ring flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold text-slate-400 transition hover:bg-white/5 hover:text-white"><span className="w-5 text-right text-gold/80">{chapter.number}</span><span className="truncate">{chapter.title}</span></a>)}
          </nav>
        </aside>

        <main className="space-y-4">
          <div className="flex items-center justify-between px-1">
            <p className="text-sm text-slate-400" aria-live="polite">
              {search ? <><span className="font-bold text-white">{chapters.length}</span> Kapitel zu „{query.trim()}“</> : <><span className="font-bold text-white">19</span> Regelkapitel</>}
            </p>
            {search && <button onClick={clearSearch} className="text-xs font-semibold text-gold hover:underline">Alle anzeigen</button>}
          </div>

          {chapters.length === 0 && <section className="glass rounded-3xl px-6 py-14 text-center"><Search className="mx-auto size-9 text-slate-600" /><h2 className="mt-4 text-lg font-bold text-white">Keine passende Regel gefunden</h2><p className="mt-2 text-sm text-slate-400">Versuche einen englischen Fachbegriff oder ein kürzeres Schlagwort.</p><button onClick={clearSearch} className="mt-5 rounded-xl bg-gold px-4 py-2 text-sm font-bold text-ink-950">Suche zurücksetzen</button></section>}

          {chapters.map((chapter) => (
            <article id={`regel-${chapter.number}`} key={chapter.number} className="glass scroll-mt-20 overflow-hidden rounded-3xl">
              <header className="border-b border-white/5 bg-white/[0.025] p-5 sm:p-6">
                <div className="flex items-start gap-4">
                  <div className="display flex size-11 shrink-0 items-center justify-center rounded-xl bg-gold text-xl font-bold text-ink-950 shadow-[0_0_24px_rgb(251_191_36/0.18)]">{chapter.number}</div>
                  <div><h2 className="display text-xl font-bold text-white sm:text-2xl">{chapter.title}</h2><p className="mt-1 text-sm leading-6 text-slate-400">{chapter.summary}</p></div>
                </div>
              </header>
              <div className="divide-y divide-white/5">
                {chapter.sections.map((section) => <section key={section.title} className="p-5 sm:px-6"><h3 className="flex items-center gap-2 text-sm font-bold text-slate-100 sm:text-base"><BookOpenText className="size-4 shrink-0 text-gold" /> {section.title}</h3><p className="mt-2 text-sm leading-7 text-slate-300">{section.text}</p></section>)}
              </div>
            </article>
          ))}

          <section className="rounded-2xl border border-white/5 bg-white/[0.02] p-5 text-xs leading-6 text-slate-500">
            <p><strong className="text-slate-300">Quellen:</strong>{" "}<a className="text-gold hover:underline" href="https://operations.nfl.com/rules-officiating/2026-nfl-rulebook" target="_blank" rel="noreferrer">NFL Rulebook 2026</a>{" · "}<a className="text-gold hover:underline" href="https://www.rtl.de/cms/super-bowl-so-lernt-ihr-die-wichtigsten-regeln-auch-kurz-vor-dem-kickoff-5039544.html" target="_blank" rel="noreferrer">RTL: Grundregeln</a></p>
            <p>Diese deutsche Fan-Zusammenfassung ist keine amtliche Übersetzung. Bei Sonderfällen gilt das englische NFL-Regelwerk.</p>
          </section>
        </main>
      </div>
    </div>
  );
}
