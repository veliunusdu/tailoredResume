"use client";

import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Settings2,
  Plus,
  X,
  Save,
  Loader2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useSafeAuth } from "../hooks/useSafeAuth";
import { apiGet, apiPut } from "@/lib/api";

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
  results_per_site: number;
  hours_old: number;
}

const AVAILABLE_BOARDS = [
  { id: "indeed", label: "Indeed" },
  { id: "linkedin", label: "LinkedIn" },
  { id: "glassdoor", label: "Glassdoor" },
  { id: "zip_recruiter", label: "ZipRecruiter" },
  { id: "google", label: "Google Jobs" },
];

const TIER_COLORS: Record<number, string> = {
  1: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  2: "bg-indigo-500/20 text-indigo-400 border-indigo-500/30",
  3: "bg-amber-500/20 text-amber-400 border-amber-500/30",
};

export function SearchConfigPanel() {
  const { getToken } = useSafeAuth();
  const [config, setConfig] = useState<SearchConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [newQuery, setNewQuery] = useState("");
  const [newQueryTier, setNewQueryTier] = useState<1 | 2 | 3>(1);
  const [newLocation, setNewLocation] = useState("");
  const [newLocationRemote, setNewLocationRemote] = useState(false);
  const [newExclude, setNewExclude] = useState("");
  const [expanded, setExpanded] = useState(true);

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

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await apiPut("/search-config", config, getToken);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error("Failed to save search config:", err);
    } finally {
      setSaving(false);
    }
  };

  const addQuery = () => {
    if (!newQuery.trim() || !config) return;
    setConfig({
      ...config,
      queries: [...config.queries, { query: newQuery.trim(), tier: newQueryTier }],
    });
    setNewQuery("");
  };

  const removeQuery = (index: number) => {
    if (!config) return;
    setConfig({ ...config, queries: config.queries.filter((_, i) => i !== index) });
  };

  const addLocation = () => {
    if (!newLocation.trim() || !config) return;
    setConfig({
      ...config,
      locations: [
        ...config.locations,
        { location: newLocation.trim(), remote: newLocationRemote },
      ],
    });
    setNewLocation("");
    setNewLocationRemote(false);
  };

  const removeLocation = (index: number) => {
    if (!config) return;
    setConfig({ ...config, locations: config.locations.filter((_, i) => i !== index) });
  };

  const toggleBoard = (board: string) => {
    if (!config) return;
    const boards = config.boards.includes(board)
      ? config.boards.filter((b) => b !== board)
      : [...config.boards, board];
    setConfig({ ...config, boards });
  };

  const addExclude = () => {
    if (!newExclude.trim() || !config) return;
    setConfig({
      ...config,
      exclude_titles: [...config.exclude_titles, newExclude.trim()],
    });
    setNewExclude("");
  };

  const removeExclude = (index: number) => {
    if (!config) return;
    setConfig({
      ...config,
      exclude_titles: config.exclude_titles.filter((_, i) => i !== index),
    });
  };

  if (loading) {
    return (
      <div className="glass rounded-2xl p-6 flex items-center gap-3">
        <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
        <span className="text-[var(--muted-foreground)] text-sm">Loading search config…</span>
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
          <Settings2 className="w-5 h-5 text-indigo-400" />
          Search Configuration
        </h2>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-[var(--muted-foreground)]" />
        ) : (
          <ChevronDown className="w-4 h-4 text-[var(--muted-foreground)]" />
        )}
      </button>

      {expanded && (
        <div className="px-6 pb-6 space-y-6 border-t border-[var(--border)]">
          {/* Search Queries */}
          <section className="pt-5">
            <h3 className="text-sm font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-3">
              Search Queries
            </h3>
            <div className="flex flex-wrap gap-2 mb-3 min-h-[36px]">
              {config.queries.map((q, i) => (
                <span
                  key={i}
                  className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border ${TIER_COLORS[q.tier]}`}
                >
                  T{q.tier} · {q.query}
                  <button
                    onClick={() => removeQuery(i)}
                    id={`remove-query-${i}`}
                    className="hover:opacity-60 transition-opacity"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                id="new-query-input"
                type="text"
                placeholder="e.g. backend engineer"
                value={newQuery}
                onChange={(e) => setNewQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addQuery()}
                className="flex-1 bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              />
              <select
                id="new-query-tier"
                value={newQueryTier}
                onChange={(e) => setNewQueryTier(Number(e.target.value) as 1 | 2 | 3)}
                className="bg-[var(--background)] border border-[var(--border)] rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              >
                <option value={1}>Tier 1</option>
                <option value={2}>Tier 2</option>
                <option value={3}>Tier 3</option>
              </select>
              <button
                id="add-query-btn"
                onClick={addQuery}
                className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl px-3 py-2 transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          </section>

          {/* Locations */}
          <section>
            <h3 className="text-sm font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-3">
              Target Locations
            </h3>
            <div className="flex flex-wrap gap-2 mb-3">
              {config.locations.map((loc, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20"
                >
                  {loc.remote ? "🌐" : "📍"} {loc.location}
                  <button
                    onClick={() => removeLocation(i)}
                    id={`remove-location-${i}`}
                    className="hover:opacity-60 transition-opacity"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2 items-center">
              <input
                id="new-location-input"
                type="text"
                placeholder="e.g. San Francisco, CA"
                value={newLocation}
                onChange={(e) => setNewLocation(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addLocation()}
                className="flex-1 bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              />
              <label className="flex items-center gap-2 text-sm text-[var(--muted-foreground)] cursor-pointer select-none">
                <input
                  id="new-location-remote"
                  type="checkbox"
                  checked={newLocationRemote}
                  onChange={(e) => setNewLocationRemote(e.target.checked)}
                  className="rounded"
                />
                Remote
              </label>
              <button
                id="add-location-btn"
                onClick={addLocation}
                className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl px-3 py-2 transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          </section>

          {/* Job Boards */}
          <section>
            <h3 className="text-sm font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-3">
              Job Boards
            </h3>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_BOARDS.map((board) => {
                const active = config.boards.includes(board.id);
                return (
                  <button
                    key={board.id}
                    id={`board-toggle-${board.id}`}
                    onClick={() => toggleBoard(board.id)}
                    className={`px-4 py-2 rounded-xl text-sm font-semibold border transition-all ${
                      active
                        ? "bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-500/20"
                        : "bg-transparent border-[var(--border)] text-[var(--muted-foreground)] hover:border-indigo-500/50"
                    }`}
                  >
                    {board.label}
                  </button>
                );
              })}
            </div>
          </section>

          {/* Numeric Settings */}
          <section className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-2 block">
                Results / Site
              </label>
              <input
                id="results-per-site-input"
                type="number"
                min={5}
                max={200}
                value={config.results_per_site}
                onChange={(e) =>
                  setConfig({ ...config, results_per_site: Number(e.target.value) })
                }
                className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              />
            </div>
            <div>
              <label className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-2 block">
                Hours Old (max)
              </label>
              <input
                id="hours-old-input"
                type="number"
                min={1}
                max={720}
                value={config.hours_old}
                onChange={(e) =>
                  setConfig({ ...config, hours_old: Number(e.target.value) })
                }
                className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              />
            </div>
          </section>

          {/* Exclude Titles */}
          <section>
            <h3 className="text-sm font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-3">
              Exclude Title Keywords
            </h3>
            <div className="flex flex-wrap gap-2 mb-3">
              {config.exclude_titles.map((title, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20"
                >
                  {title}
                  <button
                    onClick={() => removeExclude(i)}
                    id={`remove-exclude-${i}`}
                    className="hover:opacity-60 transition-opacity"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                id="new-exclude-input"
                type="text"
                placeholder="e.g. intern, VP"
                value={newExclude}
                onChange={(e) => setNewExclude(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addExclude()}
                className="flex-1 bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              />
              <button
                id="add-exclude-btn"
                onClick={addExclude}
                className="bg-red-600 hover:bg-red-500 text-white rounded-xl px-3 py-2 transition-colors"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          </section>

          {/* Save Button */}
          <button
            id="save-search-config-btn"
            onClick={handleSave}
            disabled={saving}
            className={`w-full py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-lg ${
              saved
                ? "bg-emerald-600 shadow-emerald-500/20 text-white"
                : "bg-indigo-600 hover:bg-indigo-500 shadow-indigo-500/20 text-white"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {saving ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Saving…</>
            ) : saved ? (
              <><CheckCircle2 className="w-4 h-4" /> Saved!</>
            ) : (
              <><Save className="w-4 h-4" /> Save Configuration</>
            )}
          </button>
        </div>
      )}
    </motion.div>
  );
}
