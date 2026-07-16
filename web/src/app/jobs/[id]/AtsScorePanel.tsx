"use client";

import { useEffect, useState } from "react";
import { useSafeAuth } from "@/hooks/useSafeAuth";
import { apiGet } from "@/lib/api";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";

interface KeywordAnalysis {
  found: string[];
  missing: string[];
  score: number;
}

export function AtsScorePanel({ jobId }: { jobId: string }) {
  const { getToken } = useSafeAuth();
  const [analysis, setAnalysis] = useState<KeywordAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchKeywords() {
      try {
        const data = await apiGet<KeywordAnalysis>(`/jobs/${jobId}/keywords`, getToken);
        setAnalysis(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchKeywords();
  }, [jobId, getToken]);

  if (loading) {
    return (
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 flex flex-col items-center justify-center min-h-[300px]">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mb-4" />
        <p className="text-sm text-[var(--muted-foreground)] font-medium">Analyzing ATS Match...</p>
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

  if (!analysis) return null;

  // Calculate circumference for the SVG circle
  const radius = 48;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (analysis.score / 100) * circumference;

  let scoreColor = "text-red-500";
  let strokeColor = "stroke-red-500";
  if (analysis.score >= 80) {
    scoreColor = "text-green-500";
    strokeColor = "stroke-green-500";
  } else if (analysis.score >= 50) {
    scoreColor = "text-yellow-500";
    strokeColor = "stroke-yellow-500";
  }

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 space-y-6">
      <div className="text-center">
        <div className="mb-6">
          <h2 className="text-xl font-bold text-[var(--foreground)]">ATS Keyword Score</h2>
          <p className="text-xs text-[var(--muted-foreground)] mt-2 max-w-xs mx-auto">
            Measures strict keyword overlap using your base resume. (Different from the holistic Fit Score). 
            <br/><span className="text-indigo-400 font-semibold">Tailor your application to boost this!</span>
          </p>
        </div>
        
        <div className="relative inline-flex items-center justify-center">
          <svg className="w-32 h-32 transform -rotate-90">
            <circle
              className="text-[var(--border)]"
              strokeWidth="8"
              stroke="currentColor"
              fill="transparent"
              r={radius}
              cx="64"
              cy="64"
            />
            <circle
              className={`${strokeColor} transition-all duration-1000 ease-out`}
              strokeWidth="8"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              stroke="currentColor"
              fill="transparent"
              r={radius}
              cx="64"
              cy="64"
            />
          </svg>
          <div className="absolute flex flex-col items-center justify-center">
            <span className={`text-4xl font-black ${scoreColor}`}>{analysis.score}</span>
            <span className="text-xs text-[var(--muted-foreground)] font-medium uppercase tracking-wider">out of 100</span>
          </div>
        </div>
      </div>

      <div className="space-y-4 pt-4 border-t border-[var(--border)]">
        <div>
          <h3 className="text-sm font-bold text-[var(--foreground)] mb-2 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-500" />
            Found Keywords ({analysis.found.length})
          </h3>
          <div className="flex flex-wrap gap-2">
            {analysis.found.map((kw, i) => (
              <span key={i} className="px-2 py-1 bg-green-500/10 text-green-400 text-xs font-semibold rounded-md border border-green-500/20">
                {kw}
              </span>
            ))}
          </div>
        </div>

        <div>
          <h3 className="text-sm font-bold text-[var(--foreground)] mb-2 flex items-center gap-2 mt-4">
            <XCircle className="w-4 h-4 text-red-500" />
            Missing Keywords ({analysis.missing.length})
          </h3>
          <div className="flex flex-wrap gap-2">
            {analysis.missing.map((kw, i) => (
              <span key={i} className="px-2 py-1 bg-red-500/10 text-red-400 text-xs font-semibold rounded-md border border-red-500/20">
                {kw}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
