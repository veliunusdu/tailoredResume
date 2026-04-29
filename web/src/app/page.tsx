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
  Sun
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Job, Stats } from "../types";
import { JobCard } from "../components/JobCard";
import { StatCard } from "../components/StatCard";
import { FilterButton } from "../components/FilterButton";

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [theme, setTheme] = useState("dark"); // Default to dark mode

  useEffect(() => {
    // Apply theme class to html element
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [jobsRes, statsRes] = await Promise.all([
          fetch("http://localhost:8000/jobs"),
          fetch("http://localhost:8000/stats")
        ]);
        const jobsData = await jobsRes.json();
        const statsData = await statsRes.json();
        setJobs(jobsData);
        setStats(statsData);
      } catch (error) {
        console.error("Error fetching data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const filteredJobs = jobs.filter(job => {
    const matchesSearch = job.title.toLowerCase().includes(search.toLowerCase()) || 
                          job.company.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = filter === "all" || 
                          (filter === "strong" && job.score >= 7) ||
                          (filter === "maybe" && job.score >= 4 && job.score < 7);
    return matchesSearch && matchesFilter;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="bg-blobs" />
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-[var(--primary)] border-t-transparent rounded-full animate-spin"></div>
          <p className="text-[var(--muted-foreground)] animate-pulse font-medium">Initializing Dashboard...</p>
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
            <h1 className="text-4xl font-extrabold tracking-tight text-gradient">TailoredResume</h1>
          </div>
          <p className="text-[var(--muted-foreground)] font-medium">Your autonomous career intelligence command center.</p>
        </div>
        
        <div className="flex items-center gap-4">
          <button 
            onClick={toggleTheme}
            className="glass p-3 rounded-xl flex items-center justify-center text-[var(--foreground)] hover:scale-105 transition-transform"
            aria-label="Toggle Theme"
          >
            {theme === "dark" ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
          <div className="glass px-5 py-3 rounded-xl flex items-center gap-3 shadow-lg shadow-black/5">
            <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.8)]"></span>
            <span className="text-sm font-bold tracking-wide">API Operational</span>
          </div>
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
        <div className="flex flex-col lg:flex-row gap-8">
          
          {/* Sidebar / Filters */}
          <aside className="w-full lg:w-80 space-y-6">
            <div className="glass p-6 rounded-2xl shadow-xl shadow-black/5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
              
              <h2 className="text-xl font-bold mb-6 flex items-center gap-2 relative z-10">
                <Filter className="w-5 h-5 text-indigo-500" />
                Refine Pipeline
              </h2>
              
              <div className="space-y-6 relative z-10">
                <div className="relative">
                  <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted-foreground)]" />
                  <input 
                    type="text" 
                    placeholder="Search roles or companies..."
                    className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl py-3 pl-10 pr-4 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/50 transition-all shadow-inner"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                
                <div className="space-y-3">
                  <label className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Quality Tier</label>
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

            <div className="glass p-6 rounded-2xl border-l-4 border-l-pink-500 shadow-lg shadow-pink-500/10 bg-gradient-to-br from-pink-500/5 to-transparent relative overflow-hidden">
              <h3 className="font-bold text-lg mb-2 flex items-center gap-2">
                <LayoutDashboard className="w-5 h-5 text-pink-500" />
                Autonomous Mode
              </h3>
              <p className="text-sm text-[var(--muted-foreground)] font-medium mb-4 leading-relaxed">
                Run the background engine to refresh your pipeline with new opportunities.
              </p>
              <code className="block bg-[var(--background)] p-3 rounded-xl text-xs text-pink-500 font-mono mb-2 border border-pink-500/20 shadow-inner">
                python main.py run
              </code>
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
                  <p className="text-[var(--muted-foreground)] font-medium text-lg">Try adjusting your filters or search terms.</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </main>
    </div>
  );
}
