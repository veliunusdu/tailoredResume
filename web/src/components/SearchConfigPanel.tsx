"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Settings2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Loader2,
  Bot
} from "lucide-react";
import { useSafeAuth } from "../hooks/useSafeAuth";
import { apiGet, apiPost } from "@/lib/api";

interface SearchQuery {
  query: string;
  tier: 1 | 2 | 3;
}

interface SearchLocation {
  location: string;
  remote: boolean;
}

interface SearchConfig {
  queries: SearchQuery[];
  locations: SearchLocation[];
  boards: string[];
  exclude_titles: string[];
  seniority_levels: string[];
  profile_notes: string;
  results_per_site: number;
  hours_old: number;
  employment_types: string[];
  experience_levels: string[];
  remote_only: boolean;
  target_countries: string[];
  current_country: string;
  has_us_work_authorization: boolean;
  requires_sponsorship: boolean;
  student_status: boolean;
  graduation_year?: number;
  visa_sponsorship: boolean;
}

const TIER_COLORS: Record<number, string> = {
  1: "bg-emerald-500/10 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border-emerald-500/25 dark:border-emerald-500/30",
  2: "bg-indigo-500/10 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 border-indigo-500/25 dark:border-indigo-500/30",
  3: "bg-amber-500/10 dark:bg-amber-500/20 text-amber-600 dark:text-amber-400 border-amber-500/25 dark:border-amber-500/30",
};

export function SearchConfigPanel({ onConfigSaved }: { onConfigSaved?: () => void }) {
  const { getToken } = useSafeAuth();
  const [config, setConfig] = useState<SearchConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(true);

  const [aiIntentText, setAiIntentText] = useState("");
  const [parsingIntent, setParsingIntent] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const data = await apiGet<SearchConfig>("/search-config", getToken);
        setConfig(data);
      } catch (err) {
        console.error("Failed to load search config:", err);
      } finally {
        setLoading(false);
      }
    })();
  }, [getToken]);

  const handleParseIntent = async () => {
    if (!aiIntentText.trim()) return;
    setParsingIntent(true);
    setSaveSuccess(false);
    try {
      const res = await apiPost<any>("/search-config/chat", { text: aiIntentText }, getToken);
      if (res.config) {
        setConfig(res.config);
        setSaveSuccess(true);
        setAiIntentText("");
        setTimeout(() => setSaveSuccess(false), 3000);
        if (onConfigSaved) onConfigSaved();
      }
    } catch (err) {
      console.error("Failed to parse and save intent:", err);
    } finally {
      setParsingIntent(false);
    }
  };

  if (loading) {
    return (
      <div className="glass rounded-2xl p-6 flex items-center gap-3">
        <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
        <span className="text-[var(--muted-foreground)] text-sm">Loading Job Search Agent…</span>
      </div>
    );
  }

  if (!config) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-2xl overflow-hidden"
    >
      {/* Header */}
      <button
        id="search-config-toggle"
        className="w-full flex items-center justify-between p-6 text-left hover:bg-white/5 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <h2 className="text-lg font-bold flex items-center gap-2">
          <Bot className="w-5 h-5 text-indigo-400" />
          Job Search Agent
        </h2>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-[var(--muted-foreground)]" />
        ) : (
          <ChevronDown className="w-4 h-4 text-[var(--muted-foreground)]" />
        )}
      </button>

      {expanded && (
        <div className="px-6 pb-6 space-y-6 border-t border-[var(--border)]">
          {/* Conversational Chat Input */}
          <section className="pt-5 pb-2">
            <h3 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider mb-3 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
              Describe your ideal search
            </h3>
            <div className="relative flex items-center">
              <input
                type="text"
                placeholder="e.g. Remote senior backend Go, but no Python..."
                value={aiIntentText}
                onChange={(e) => setAiIntentText(e.target.value)}
                className="w-full pl-4 pr-32 py-3.5 bg-black/10 dark:bg-white/5 border border-[var(--border)] rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500/50 transition-all text-[var(--foreground)] placeholder-[var(--muted-foreground)]"
                onKeyDown={(e) => e.key === "Enter" && handleParseIntent()}
              />
              <button
                onClick={handleParseIntent}
                disabled={parsingIntent || !aiIntentText.trim()}
                className="absolute right-1.5 px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-500 hover:from-indigo-600 hover:to-purple-600 text-white rounded-lg text-xs font-bold transition-all disabled:opacity-40 disabled:pointer-events-none flex items-center gap-1.5 shadow-md shadow-indigo-500/20"
              >
                {parsingIntent ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                {parsingIntent ? "Parsing..." : "Ask Agent"}
              </button>
            </div>
            {saveSuccess && (
              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-emerald-500 dark:text-emerald-400 text-xs mt-2 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Search updated successfully!
              </motion.p>
            )}
          </section>

          {/* Active Config Visualizer */}
          <section className="pt-4 border-t border-[var(--border)] space-y-5">
            <div className="grid grid-cols-1 gap-4">
              <div>
                <h3 className="text-[10px] font-black text-[var(--muted-foreground)] uppercase tracking-wider mb-2 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Active Roles
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {config.queries.length === 0 ? (
                    <span className="text-xs text-[var(--muted-foreground)] italic">No specific roles set</span>
                  ) : (
                    config.queries.map((q, i) => (
                      <span
                        key={i}
                        className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${TIER_COLORS[q.tier] || TIER_COLORS[1]}`}
                      >
                        {q.query}
                      </span>
                    ))
                  )}
                </div>
              </div>

              <div>
                <h3 className="text-[10px] font-black text-[var(--muted-foreground)] uppercase tracking-wider mb-2 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span> Locations
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {config.locations.length === 0 ? (
                    <span className="text-xs text-[var(--muted-foreground)] italic">Any Location</span>
                  ) : (
                    config.locations.map((loc, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-500/10 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 border border-blue-500/20 dark:border-blue-500/30"
                      >
                        {loc.remote ? "🌐" : "📍"} {loc.location}
                      </span>
                    ))
                  )}
                </div>
              </div>
            </div>

            {config.exclude_titles.length > 0 && (
              <div>
                <h3 className="text-[10px] font-black text-[var(--muted-foreground)] uppercase tracking-wider mb-2 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span> Excluded Titles
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {config.exclude_titles.map((title, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-rose-500/10 dark:bg-rose-500/20 text-rose-600 dark:text-rose-400 border border-rose-500/20 dark:border-rose-500/30"
                    >
                      {title}
                    </span>
                  ))}
                </div>
              </div>
            )}
            
            {(config.employment_types?.length > 0 || config.experience_levels?.length > 0 || config.student_status) && (
              <div>
                <h3 className="text-[10px] font-black text-[var(--muted-foreground)] uppercase tracking-wider mb-2 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500"></span> Profile Details
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {config.student_status && (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-600 border border-purple-500/20">
                      🎓 Student {config.graduation_year ? `(Class of ${config.graduation_year})` : ""}
                    </span>
                  )}
                  {config.employment_types?.map((type, i) => (
                    <span key={`emp-${i}`} className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/20">
                      💼 {type}
                    </span>
                  ))}
                  {config.experience_levels?.map((lvl, i) => (
                    <span key={`exp-${i}`} className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/20">
                      📈 {lvl}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {(config.visa_sponsorship || config.requires_sponsorship || config.has_us_work_authorization) && (
              <div>
                <h3 className="text-[10px] font-black text-[var(--muted-foreground)] uppercase tracking-wider mb-2 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span> Work Authorization
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {(config.visa_sponsorship || config.requires_sponsorship) && (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-600 border border-amber-500/20">
                      🛂 Requires Sponsorship
                    </span>
                  )}
                  {config.has_us_work_authorization && (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                      🇺🇸 US Work Authorized
                    </span>
                  )}
                </div>
              </div>
            )}
            
            {config.profile_notes && (
              <div className="pt-2">
                <h3 className="text-[10px] font-black text-[var(--muted-foreground)] uppercase tracking-wider mb-2">
                  Agent Constraints & Notes
                </h3>
                <p className="text-xs text-[var(--foreground)]/80 leading-relaxed bg-black/10 dark:bg-black/20 p-3 rounded-lg border border-[var(--border)] font-medium">
                  {config.profile_notes}
                </p>
              </div>
            )}
          </section>
        </div>
      )}
    </motion.div>
  );
}
