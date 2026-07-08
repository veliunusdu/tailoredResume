"use client";

import React, { useEffect, useState } from "react";
import {
  Briefcase,
  CheckCircle2,
  HelpCircle,
  Search,
  Filter,
  LayoutDashboard,
  Target,
  TrendingUp,
  Moon,
  Sun,
  Settings,
  FileText,
  X,
  RefreshCw,
  Loader2,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { UserButton } from "@clerk/nextjs";
import { useSafeAuth, isClerkConfigured } from "../hooks/useSafeAuth";
import { Job, Stats } from "../types";
import { JobCard } from "../components/JobCard";
import { StatCard } from "../components/StatCard";
import { FilterButton } from "../components/FilterButton";
import { ResumeUploader } from "../components/ResumeUploader";
import { SearchConfigPanel } from "../components/SearchConfigPanel";
import { apiGet, apiPost } from "@/lib/api";
import { createClient } from "../utils/supabase/client";
import { DiscoveryFunnel } from "../components/DiscoveryFunnel";

export const runtime = "edge";

export default function Dashboard() {
  const { getToken } = useSafeAuth();

  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [theme, setTheme] = useState("dark");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activeSettingsTab, setActiveSettingsTab] = useState<"resume" | "search">("resume");
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [jobsData, statsData] = await Promise.all([
        apiGet<Job[]>("/jobs", getToken),
        apiGet<Stats>("/stats", getToken),
      ]);
      setJobs(jobsData);
      setStats(statsData);
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  };

  const handleSyncJobs = async () => {
    setSyncing(true);
    setSyncStatus("Sync queued...");
    try {
      const res = await apiPost<{ status: string; task_id: string }>("/jobs/sync", {}, getToken);
      setSyncStatus("Starting sync...");
      
      const supabase = createClient();
      const channel = supabase
        .channel(`sync-task-${res.task_id}`)
        .on(
          "postgres_changes",
          {
            event: "UPDATE",
            schema: "public",
            table: "task_progress",
            filter: `task_id=eq.${res.task_id}`,
          },
          async (payload: any) => {
            const data = payload.new;
            if (data.status === "running") {
              setSyncStatus(data.message);
            } else if (data.status === "success") {
              setSyncStatus("✅ Sync completed successfully!");
              setTimeout(() => {
                setSyncing(false);
                setSyncStatus(null);
              }, 3000);
              channel.unsubscribe();
              await fetchData();
            } else if (data.status === "failed") {
              setSyncStatus(`❌ Sync failed: ${data.message || "Unknown error"}`);
              setTimeout(() => {
                setSyncing(false);
                setSyncStatus(null);
              }, 4000);
              channel.unsubscribe();
            }
          }
        )
        .subscribe();

      // Fallback polling in case WebSockets fail/disconnect
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        if (attempts >= 15) { // 45 seconds max
          clearInterval(interval);
          channel.unsubscribe();
          setSyncing(false);
          setSyncStatus(null);
          return;
        }
        
        try {
          const statsRes = await apiGet<Stats>("/stats", getToken);
          if (statsRes.total !== stats?.total) {
            await fetchData();
          }
        } catch (e) {
          console.error("Error fallback polling sync data:", e);
        }
      }, 3000);
    } catch (error) {
      console.error("Error syncing jobs:", error);
      setSyncStatus("Failed");
      setTimeout(() => {
        setSyncing(false);
        setSyncStatus(null);
      }, 2000);
    }
  };

  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme]);

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  useEffect(() => {
    const initFetch = async () => {
      await fetchData();
      setLoading(false);
    };
    initFetch();
  }, [getToken]);

  const filteredJobs = jobs.filter((job) => {
    const matchesSearch =
      job.title.toLowerCase().includes(search.toLowerCase()) ||
      job.company.toLowerCase().includes(search.toLowerCase());
    const matchesFilter =
      filter === "all" ||
      (filter === "strong" && job.score >= 7) ||
      (filter === "maybe" && job.score >= 4 && job.score < 7);
    return matchesSearch && matchesFilter;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="bg-blobs" />
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-[var(--primary)] border-t-transparent rounded-full animate-spin" />
          <p className="text-[var(--muted-foreground)] animate-pulse font-medium">
            Initializing Dashboard…
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen text-[var(--foreground)] p-6 lg:p-10 relative z-10">
      {/* Animated Background */}
      <div className="bg-blobs" />

      {/* Header */}
      <header className="max-w-7xl mx-auto mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="bg-gradient-to-br from-indigo-500 to-pink-500 p-2.5 rounded-xl shadow-lg shadow-indigo-500/20">
              <Target className="text-white w-6 h-6" />
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-gradient">
              TailoredResume
            </h1>
          </div>
          <p className="text-[var(--muted-foreground)] font-medium">
            Your autonomous career intelligence command center.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Sync Jobs Button */}
          <button
            id="sync-jobs-btn"
            onClick={handleSyncJobs}
            disabled={syncing}
            className="glass px-4 py-3 rounded-xl flex items-center gap-2 hover:scale-105 transition-all disabled:opacity-50 disabled:scale-100"
          >
            {syncing ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
                <span className="text-sm font-bold text-indigo-400">{syncStatus}</span>
              </>
            ) : (
              <>
                <RefreshCw className="w-5 h-5 text-indigo-400 animate-pulse" />
                <span className="text-sm font-bold text-indigo-300">Sync Jobs</span>
              </>
            )}
          </button>

          {/* Theme Toggle */}
          <button
            id="theme-toggle-btn"
            onClick={toggleTheme}
            className="glass p-3 rounded-xl flex items-center justify-center text-[var(--foreground)] hover:scale-105 transition-transform"
            aria-label="Toggle Theme"
          >
            {theme === "dark" ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>

          {/* Settings Button */}
          <button
            id="settings-btn"
            onClick={() => setSettingsOpen(true)}
            className="glass p-3 rounded-xl flex items-center justify-center text-[var(--foreground)] hover:scale-105 transition-transform"
            aria-label="Settings"
          >
            <Settings className="w-5 h-5" />
          </button>

          {/* API Status */}
          <div className="glass px-5 py-3 rounded-xl flex items-center gap-3 shadow-lg shadow-black/5">
            <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.8)]" />
            <span className="text-sm font-bold tracking-wide">API Operational</span>
          </div>

          {/* Clerk User Menu */}
          {isClerkConfigured && (
            <div className="glass p-1.5 rounded-xl">
              <UserButton
                appearance={{
                  elements: {
                    avatarBox: "w-8 h-8",
                  },
                }}
              />
            </div>
          )}
        </div>
      </header>

      {/* Stats Grid */}
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
        <StatCard
          icon={<LayoutDashboard className="w-6 h-6 text-blue-500" />}
          label="Discovered Jobs"
          value={stats?.total || 0}
          subValue="Across all platforms"
          color="blue"
        />
        <StatCard
          icon={<CheckCircle2 className="w-6 h-6 text-emerald-500" />}
          label="Strong Matches"
          value={stats?.strong || 0}
          subValue="Score ≥ 7/10"
          color="emerald"
        />
        <StatCard
          icon={<HelpCircle className="w-6 h-6 text-amber-500" />}
          label="Potential Leads"
          value={stats?.maybe || 0}
          subValue="Score 4-6/10"
          color="amber"
        />
        <StatCard
          icon={<TrendingUp className="w-6 h-6 text-indigo-500" />}
          label="Avg Fit Score"
          value={`${stats?.avg_score || 0}/10`}
          subValue="AI-powered analysis"
          color="indigo"
        />
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto">
        <DiscoveryFunnel stats={stats} />
        <div className="flex flex-col lg:flex-row gap-8">
          {/* Sidebar / Filters */}
          <aside className="w-full lg:w-80 space-y-6">
            <div className="glass p-6 rounded-2xl shadow-xl shadow-black/5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-2xl -mr-10 -mt-10" />

              <h2 className="text-xl font-bold mb-6 flex items-center gap-2 relative z-10">
                <Filter className="w-5 h-5 text-indigo-500" />
                Refine Pipeline
              </h2>

              <div className="space-y-6 relative z-10">
                <div className="relative">
                  <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted-foreground)]" />
                  <input
                    id="job-search-input"
                    type="text"
                    placeholder="Search roles or companies…"
                    className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl py-3 pl-10 pr-4 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all shadow-inner"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>

                <div className="space-y-3">
                  <label className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest">
                    Quality Tier
                  </label>
                  <div className="grid grid-cols-1 gap-2.5">
                    <FilterButton
                      active={filter === "all"}
                      onClick={() => setFilter("all")}
                      label="All Discovered"
                    />
                    <FilterButton
                      active={filter === "strong"}
                      onClick={() => setFilter("strong")}
                      label="Strong Matches"
                      count={stats?.strong}
                      color="emerald"
                    />
                    <FilterButton
                      active={filter === "maybe"}
                      onClick={() => setFilter("maybe")}
                      label="Potential Leads"
                      count={stats?.maybe}
                      color="amber"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Settings Quick Action */}
            <div className="glass p-6 rounded-2xl border-l-4 border-l-indigo-500 shadow-lg shadow-indigo-500/10 bg-gradient-to-br from-indigo-500/5 to-transparent relative overflow-hidden">
              <h3 className="font-bold text-lg mb-2 flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-500" />
                Your Resumes
              </h3>
              <p className="text-sm text-[var(--muted-foreground)] font-medium mb-4 leading-relaxed">
                Upload your resume and configure your job search preferences.
              </p>
              <button
                id="open-settings-sidebar-btn"
                onClick={() => setSettingsOpen(true)}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl py-2.5 text-sm font-semibold transition-colors flex items-center justify-center gap-2"
              >
                <Settings className="w-4 h-4" />
                Open Settings
              </button>
            </div>
          </aside>

          {/* Job Feed */}
          <div className="flex-1 space-y-4">
            <div className="flex items-center justify-between mb-4 glass px-6 py-4 rounded-2xl shadow-sm">
              <h2 className="text-2xl font-bold flex items-center gap-3">
                <Briefcase className="w-6 h-6 text-indigo-500" />
                Opportunity Feed
              </h2>
              <span className="bg-[var(--secondary)] text-[var(--foreground)] px-4 py-1.5 rounded-full text-sm font-bold shadow-inner">
                {filteredJobs.length} matches
              </span>
            </div>

            <AnimatePresence mode="popLayout">
              {filteredJobs.length > 0 ? (
                filteredJobs.map((job, index) => (
                  <JobCard key={job.id} job={job} index={index} />
                ))
              ) : (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="glass rounded-2xl p-20 text-center border-2 border-dashed border-[var(--border)] bg-gradient-to-b from-[var(--secondary)]/30 to-transparent"
                >
                  <div className="bg-[var(--background)] w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl shadow-black/5">
                    <Search className="w-10 h-10 text-[var(--muted-foreground)]" />
                  </div>
                  <h3 className="text-2xl font-bold mb-3">No matches found</h3>
                  <p className="text-[var(--muted-foreground)] font-medium text-lg">
                    Try adjusting your filters or search terms.
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </main>

      {/* Settings Modal */}
      <AnimatePresence>
        {settingsOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
              onClick={() => setSettingsOpen(false)}
            />

            {/* Panel */}
            <motion.div
              initial={{ opacity: 0, x: "100%" }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 280 }}
              className="fixed right-0 top-0 h-full w-full max-w-lg bg-[var(--card)] border-l border-[var(--border)] z-50 overflow-y-auto shadow-2xl"
            >
              {/* Modal Header */}
              <div className="sticky top-0 bg-[var(--card)] border-b border-[var(--border)] px-6 py-5 flex items-center justify-between z-10">
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <Settings className="w-5 h-5 text-indigo-400" />
                  Settings
                </h2>
                <button
                  id="close-settings-btn"
                  onClick={() => setSettingsOpen(false)}
                  className="p-2 rounded-xl hover:bg-[var(--secondary)] transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-[var(--border)]">
                <button
                  id="settings-tab-resume"
                  onClick={() => setActiveSettingsTab("resume")}
                  className={`flex-1 py-4 text-sm font-semibold transition-colors flex items-center justify-center gap-2 ${
                    activeSettingsTab === "resume"
                      ? "text-indigo-400 border-b-2 border-indigo-400"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  }`}
                >
                  <FileText className="w-4 h-4" />
                  Resumes
                </button>
                <button
                  id="settings-tab-search"
                  onClick={() => setActiveSettingsTab("search")}
                  className={`flex-1 py-4 text-sm font-semibold transition-colors flex items-center justify-center gap-2 ${
                    activeSettingsTab === "search"
                      ? "text-indigo-400 border-b-2 border-indigo-400"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  }`}
                >
                  <Search className="w-4 h-4" />
                  Search Config
                </button>
              </div>

              {/* Tab Content */}
              <div className="p-6 space-y-6">
                {activeSettingsTab === "resume" && (
                  <div className="space-y-4">
                    <p className="text-sm text-[var(--muted-foreground)]">
                      Upload one or more resumes. The AI will automatically select the best
                      one for each job when tailoring.
                    </p>
                    <ResumeUploader
                      onUploadSuccess={(resume) => {
                        console.log("Resume uploaded:", resume);
                      }}
                    />
                  </div>
                )}

                {activeSettingsTab === "search" && (
                  <div className="space-y-4">
                    <p className="text-sm text-[var(--muted-foreground)]">
                      Configure your job search preferences. These settings apply to all
                      future pipeline runs.
                    </p>
                    <SearchConfigPanel />
                  </div>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
