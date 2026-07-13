"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { apiGet } from "@/lib/api";
import { Loader2, Lightbulb, Map, Clock, Zap } from "lucide-react";

interface RoadmapStep {
  skill: string;
  action_items: string[];
  estimated_time: string;
}

interface SkillGapRoadmap {
  summary: string;
  steps: RoadmapStep[];
}

export function RoadmapPanel({ jobId }: { jobId: string }) {
  const { getToken } = useAuth();
  const [roadmap, setRoadmap] = useState<SkillGapRoadmap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchRoadmap() {
      try {
        const data = await apiGet<SkillGapRoadmap>(`/jobs/${jobId}/roadmap`, getToken);
        setRoadmap(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchRoadmap();
  }, [jobId, getToken]);

  if (loading) {
    return (
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 flex flex-col items-center justify-center min-h-[250px]">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mb-4" />
        <p className="text-sm text-[var(--muted-foreground)] font-medium">AI Coach is generating your learning roadmap...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[var(--card)] border border-red-900/50 rounded-2xl p-6 text-center">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  if (!roadmap) return null;

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 space-y-6">
      <div className="flex items-start gap-3">
        <div className="p-2 bg-indigo-500/10 rounded-xl border border-indigo-500/20">
          <Map className="w-6 h-6 text-indigo-400" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-[var(--foreground)]">Learning Roadmap</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">{roadmap.summary}</p>
        </div>
      </div>

      {roadmap.steps.length > 0 ? (
        <div className="relative border-l border-[var(--border)] ml-5 space-y-8 pb-4">
          {roadmap.steps.map((step, idx) => (
            <div key={idx} className="relative pl-6">
              <span className="absolute -left-3 top-1 w-6 h-6 rounded-full bg-indigo-500/20 border-2 border-indigo-500 flex items-center justify-center text-[10px] font-black text-indigo-400">
                {idx + 1}
              </span>
              
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-bold text-[var(--foreground)]">{step.skill}</h3>
                <span className="flex items-center gap-1 text-xs font-semibold px-2 py-1 bg-[var(--background)] rounded-md border border-[var(--border)] text-amber-400">
                  <Clock className="w-3 h-3" /> {step.estimated_time}
                </span>
              </div>
              
              <ul className="space-y-2 mt-3">
                {step.action_items.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[var(--muted-foreground)]">
                    <Zap className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center gap-3">
          <Lightbulb className="w-6 h-6 text-emerald-400" />
          <p className="text-sm font-medium text-emerald-500">You already have all the core skills required for this job!</p>
        </div>
      )}
    </div>
  );
}
