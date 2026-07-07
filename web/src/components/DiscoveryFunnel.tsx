"use client";

import React from "react";
import { motion } from "framer-motion";
import { 
  Globe, 
  Cpu, 
  CheckCircle, 
  SlidersHorizontal,
  ChevronRight,
  Clock,
  Briefcase
} from "lucide-react";
import { Stats } from "../types";

export function DiscoveryFunnel({ stats }: { stats: Stats | null }) {
  if (!stats?.last_discovery) {
    return null;
  }

  const {
    raw_scraped_count,
    filtered_count,
    scored_count,
    strong_count,
    maybe_count,
    timestamp
  } = stats.last_discovery;

  const dateString = new Date(timestamp * 1000).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  const funnelStages = [
    {
      id: "scraped",
      title: "Scraped Jobs",
      count: raw_scraped_count,
      description: "Aggregated from LinkedIn, Indeed, Kariyer.net, and Techcareer.net.",
      icon: <Globe className="w-5 h-5 text-blue-400" />,
      color: "from-blue-500/20 to-blue-600/5",
      borderColor: "border-blue-500/20 hover:border-blue-500/50",
      textColor: "text-blue-400"
    },
    {
      id: "filtered",
      title: "Rule Filtered",
      count: filtered_count,
      description: "Passed keyword blocklist, seniority exclusion, and location rules.",
      icon: <SlidersHorizontal className="w-5 h-5 text-purple-400" />,
      color: "from-purple-500/20 to-purple-600/5",
      borderColor: "border-purple-500/20 hover:border-purple-500/50",
      textColor: "text-purple-400"
    },
    {
      id: "scored",
      title: "AI Evaluated",
      count: scored_count,
      description: "Deep-analyzed by Gemini AI against your professional experiences.",
      icon: <Cpu className="w-5 h-5 text-amber-400" />,
      color: "from-amber-500/20 to-amber-600/5",
      borderColor: "border-amber-500/20 hover:border-amber-500/50",
      textColor: "text-amber-400"
    },
    {
      id: "strong",
      title: "Perfect Matches",
      count: strong_count,
      description: "Strong compatibility scores (≥ 7/10) with tailored fits.",
      icon: <CheckCircle className="w-5 h-5 text-emerald-400" />,
      color: "from-emerald-500/20 to-emerald-600/5",
      borderColor: "border-emerald-500/20 hover:border-emerald-500/50",
      textColor: "text-emerald-400",
      highlight: true
    }
  ];

  return (
    <motion.div 
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="glass p-6 rounded-3xl border border-[var(--border)] relative overflow-hidden shadow-xl shadow-black/5 bg-gradient-to-br from-indigo-500/5 to-transparent mb-10"
    >
      <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full blur-3xl -mr-20 -mt-20"></div>
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8 pb-4 border-b border-[var(--border)]">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2.5">
            <Briefcase className="w-5 h-5 text-indigo-500 animate-pulse" />
            Job Discovery & Match Pipeline
          </h2>
          <p className="text-xs text-[var(--muted-foreground)] font-medium mt-1">
            Analyzing market opportunities to match your experience
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-bold text-[var(--muted-foreground)] bg-[var(--secondary)] px-3.5 py-2 rounded-xl shadow-inner border border-[var(--border)] w-fit">
          <Clock className="w-3.5 h-3.5 text-indigo-500" />
          <span>Last Run: {dateString}</span>
        </div>
      </div>

      {/* Funnel Flow Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 relative">
        {funnelStages.map((stage, idx) => (
          <React.Fragment key={stage.id}>
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.1, duration: 0.4 }}
              className={`relative glass p-5 rounded-2xl border ${stage.borderColor} bg-gradient-to-b ${stage.color} group hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between`}
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="p-2.5 rounded-xl bg-[var(--background)] border border-[var(--border)] shadow-md group-hover:scale-110 transition-transform">
                    {stage.icon}
                  </div>
                  <span className={`text-3xl font-extrabold tracking-tight ${stage.textColor}`}>
                    {stage.count}
                  </span>
                </div>
                <h3 className="font-bold text-base mb-1.5 text-[var(--foreground)] group-hover:text-indigo-400 transition-colors">
                  {stage.title}
                </h3>
                <p className="text-xs text-[var(--muted-foreground)] font-medium leading-relaxed">
                  {stage.description}
                </p>
              </div>

              {stage.highlight && (
                <div className="mt-4 pt-3 border-t border-emerald-500/10 flex items-center justify-between">
                  <span className="text-[10px] uppercase font-black tracking-widest text-emerald-400">
                    Fit Conversion Rate
                  </span>
                  <span className="text-xs font-black text-emerald-400">
                    {raw_scraped_count > 0 
                      ? `${Math.round((strong_count / raw_scraped_count) * 100)}%` 
                      : "0%"}
                  </span>
                </div>
              )}
            </motion.div>
            
            {/* Connection arrow between columns on desktop */}
            {idx < 3 && (
              <div className="hidden md:flex absolute top-1/2 -translate-y-1/2 w-6 h-6 justify-center items-center text-[var(--muted-foreground)] z-20 pointer-events-none opacity-50"
                   style={{ left: `calc(${(idx + 1) * 25}% - 12px)` }}>
                <ChevronRight className="w-5 h-5 animate-pulse text-indigo-500" />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </motion.div>
  );
}
