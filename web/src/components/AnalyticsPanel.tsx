"use client";

import React from "react";
import { BarChart3, TrendingUp, Compass, Award, Globe } from "lucide-react";
import { Job, Stats } from "../types";

interface AnalyticsPanelProps {
  jobs: Job[];
  stats: Stats | null;
}

export function AnalyticsPanel({ jobs, stats }: AnalyticsPanelProps) {
  if (!jobs || jobs.length === 0) {
    return (
      <div className="glass p-8 rounded-2xl border border-[var(--border)] text-center">
        <BarChart3 className="w-12 h-12 text-[var(--muted-foreground)] mx-auto mb-4 opacity-50" />
        <h3 className="text-lg font-bold mb-2">No Analytics Data Available</h3>
        <p className="text-sm text-[var(--muted-foreground)]">
          Sync your job pipeline first to populate career intelligence analytics.
        </p>
      </div>
    );
  }

  // 1. Calculate Score Distribution
  const buckets = {
    perfect: { label: "Perfect Fits (8-10)", count: 0, color: "bg-emerald-500", textColor: "text-emerald-400" },
    strong: { label: "Strong Fits (6-7)", count: 0, color: "bg-teal-500", textColor: "text-teal-400" },
    maybe: { label: "Potential Leads (4-5)", count: 0, color: "bg-amber-500", textColor: "text-amber-400" },
    unsuitable: { label: "Not Suitable (0-3)", count: 0, color: "bg-rose-500", textColor: "text-rose-400" }
  };

  jobs.forEach(job => {
    const score = job.score || 0;
    if (score >= 8) buckets.perfect.count++;
    else if (score >= 6) buckets.strong.count++;
    else if (score >= 4) buckets.maybe.count++;
    else buckets.unsuitable.count++;
  });

  const maxBucketCount = Math.max(
    buckets.perfect.count,
    buckets.strong.count,
    buckets.maybe.count,
    buckets.unsuitable.count,
    1
  );

  // 2. Calculate Job Boards Ingestion share
  const boardsShare: Record<string, number> = {};
  jobs.forEach(job => {
    const site = job.site || "Web";
    boardsShare[site] = (boardsShare[site] || 0) + 1;
  });

  const sortedBoards = Object.entries(boardsShare)
    .map(([name, count]) => ({
      name,
      count,
      percentage: Math.round((count / jobs.length) * 100)
    }))
    .sort((a, b) => b.count - a.count);

  // 3. Match Efficiency metric
  const perfectMatchRatio = Math.round(((buckets.perfect.count + buckets.strong.count) / jobs.length) * 100);

  return (
    <div className="space-y-6">
      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        {[
          {
            icon: <Award className="w-5 h-5 text-emerald-400" />,
            label: "Pipeline Match Rate",
            value: `${perfectMatchRatio}%`,
            subValue: "Ratio of high-scoring matches"
          },
          {
            icon: <TrendingUp className="w-5 h-5 text-indigo-400" />,
            label: "Average Match Quality",
            value: `${stats?.avg_score || 0}/10`,
            subValue: "Overall pipeline fit score"
          },
          {
            icon: <Compass className="w-5 h-5 text-teal-400" />,
            label: "Active Channels",
            value: sortedBoards.length.toString(),
            subValue: "Scraped platforms"
          }
        ].map((item, idx) => (
          <div key={idx} className="glass p-5 rounded-2xl border border-[var(--border)] bg-gradient-to-br from-indigo-500/5 to-transparent flex items-center gap-4">
            <div className="p-3 bg-[var(--background)] border border-[var(--border)] rounded-xl">
              {item.icon}
            </div>
            <div>
              <p className="text-[10px] uppercase font-black tracking-wider text-[var(--muted-foreground)]">{item.label}</p>
              <h4 className="text-2xl font-black text-[var(--foreground)] mt-0.5">{item.value}</h4>
              <p className="text-[10px] text-[var(--muted-foreground)] font-medium mt-0.5">{item.subValue}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Score Distribution Chart */}
        <div className="glass p-6 rounded-2xl border border-[var(--border)] flex flex-col justify-between">
          <div>
            <h3 className="text-lg font-bold flex items-center gap-2.5 mb-2">
              <BarChart3 className="w-5 h-5 text-indigo-500" />
              Fit Score Distribution
            </h3>
            <p className="text-xs text-[var(--muted-foreground)] font-semibold mb-6">
              Evaluation metrics bucketed by fit compatibility score
            </p>
          </div>

          <div className="space-y-4">
            {Object.entries(buckets).map(([key, bucket]) => {
              const widthPct = (bucket.count / maxBucketCount) * 100;
              return (
                <div key={key} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="text-[var(--foreground)]">{bucket.label}</span>
                    <span className={`${bucket.textColor} font-bold`}>{bucket.count} jobs</span>
                  </div>
                  <div className="w-full bg-[var(--background)] border border-[var(--border)] rounded-full h-3 overflow-hidden shadow-inner">
                    <div
                      className={`h-full ${bucket.color} rounded-full transition-all duration-1000`}
                      style={{ width: `${widthPct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Platform Share Chart */}
        <div className="glass p-6 rounded-2xl border border-[var(--border)] flex flex-col justify-between">
          <div>
            <h3 className="text-lg font-bold flex items-center gap-2.5 mb-2">
              <Globe className="w-5 h-5 text-teal-500" />
              Channel Share Breakdown
            </h3>
            <p className="text-xs text-[var(--muted-foreground)] font-semibold mb-6">
              Percentage share of job opportunities by board
            </p>
          </div>

          <div className="space-y-4">
            {sortedBoards.slice(0, 5).map((board) => (
              <div key={board.name} className="space-y-1">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="text-[var(--foreground)] flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-indigo-500/40 border border-indigo-500" />
                    {board.name}
                  </span>
                  <span className="text-[var(--muted-foreground)]">
                    {board.count} jobs ({board.percentage}%)
                  </span>
                </div>
                <div className="w-full bg-[var(--background)] border border-[var(--border)] rounded-full h-2.5 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500/60 to-indigo-500 rounded-full transition-all duration-1000"
                    style={{ width: `${board.percentage}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
