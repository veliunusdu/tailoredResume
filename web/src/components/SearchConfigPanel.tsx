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
}

const TIER_COLORS: Record<number, string> = {
  1: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  2: "bg-indigo-500/20 text-indigo-400 border-indigo-500/30",
  3: "bg-amber-500/20 text-amber-400 border-amber-500/30",
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
          <section className="pt-5 pb-5">
            <h3 className="text-sm font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-purple-400" />
              Tell me what you're looking for
            </h3>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. Remote senior backend engineer in Python, but no frontend roles..."
                value={aiIntentText}
                onChange={(e) => setAiIntentText(e.target.value)}
                className="flex-1 px-4 py-3 bg-black/20 border border-[var(--border)] rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
                onKeyDown={(e) => e.key === "Enter" && handleParseIntent()}
              />
              <button
                onClick={handleParseIntent}
                disabled={parsingIntent || !aiIntentText.trim()}
                className="px-6 py-3 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 border border-purple-500/30 rounded-xl text-sm font-semibold transition-colors disabled:opacity-50 flex items-center gap-2 whitespace-nowrap"
              >
                {parsingIntent ? <Loader2 className="w-4 h-4 animate-spin" /> : "Update Search"}
              </button>
            </div>
            {saveSuccess && (
              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-emerald-400 text-xs mt-2 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Updated successfully
              </motion.p>
            )}
          </section>

          {/* Active Config Visualizer */}
          <section className="pt-4 border-t border-[var(--border)] grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-3">
                Active Queries
              </h3>
              <div className="flex flex-wrap gap-2">
                {config.queries.length === 0 ? (
                  <span className="text-xs text-[var(--muted-foreground)]">None</span>
                ) : (
                  config.queries.map((q, i) => (
                    <span
                      key={i}
                      className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border ${TIER_COLORS[q.tier] || TIER_COLORS[1]}`}
                    >
                      {q.query}
                    </span>
                  ))
                )}
              </div>
            </div>

            <div>
              <h3 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-3">
                Locations
              </h3>
              <div className="flex flex-wrap gap-2">
                {config.locations.length === 0 ? (
                  <span className="text-xs text-[var(--muted-foreground)]">None</span>
                ) : (
                  config.locations.map((loc, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20"
                    >
                      {loc.remote ? "🌐" : "📍"} {loc.location}
                    </span>
                  ))
                )}
              </div>
            </div>

            {config.exclude_titles.length > 0 && (
              <div className="md:col-span-2">
                <h3 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-3">
                  Excluded Titles
                </h3>
                <div className="flex flex-wrap gap-2">
                  {config.exclude_titles.map((title, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20"
                    >
                      {title}
                    </span>
                  ))}
                </div>
              </div>
            )}
            
            {config.profile_notes && (
              <div className="md:col-span-2">
                <h3 className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-2">
                  Agent Notes
                </h3>
                <p className="text-sm text-[var(--foreground)] bg-black/20 p-3 rounded-lg border border-[var(--border)]">
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
