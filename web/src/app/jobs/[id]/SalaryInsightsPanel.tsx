"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { apiGet } from "@/lib/api";
import { Loader2, DollarSign } from "lucide-react";

interface SalaryInsights {
  listed_salary: string;
  estimated_market_rate: string;
  negotiation_leverage: "High" | "Medium" | "Low";
  recommendation: string;
}

export function SalaryInsightsPanel({ jobId }: { jobId: string }) {
  const { getToken } = useAuth();
  const [insights, setInsights] = useState<SalaryInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchInsights() {
      try {
        const data = await apiGet<SalaryInsights>(`/jobs/${jobId}/salary-insights`, getToken);
        setInsights(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchInsights();
  }, [jobId, getToken]);

  if (loading) {
    return (
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 flex flex-col items-center justify-center min-h-[200px]">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500 mb-4" />
        <p className="text-sm text-[var(--muted-foreground)] font-medium">Analyzing Salary Data...</p>
      </div>
    );
  }

  if (error || !insights) {
    return null; // Silent fail if the endpoint isn't ready or errors out
  }

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 space-y-4">
      <h2 className="text-xl font-bold text-[var(--foreground)] flex items-center gap-2">
        <DollarSign className="w-5 h-5 text-emerald-500" />
        Salary & Negotiation Insights
      </h2>
      
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-[var(--background)] rounded-xl p-4 border border-[var(--border)]">
          <p className="text-xs text-[var(--muted-foreground)] font-medium uppercase tracking-wider mb-1">Listed Salary</p>
          <p className="text-lg font-bold text-[var(--foreground)]">{insights.listed_salary || "Unknown"}</p>
        </div>
        <div className="bg-emerald-500/10 rounded-xl p-4 border border-emerald-500/20">
          <p className="text-xs text-emerald-500/70 font-medium uppercase tracking-wider mb-1">Estimated Market Rate</p>
          <p className="text-lg font-bold text-emerald-400">{insights.estimated_market_rate}</p>
        </div>
      </div>

      <div className="pt-2">
        <p className="text-sm font-medium text-[var(--foreground)] mb-1 flex items-center justify-between">
          <span>Leverage: <span className={insights.negotiation_leverage === "High" ? "text-emerald-500" : insights.negotiation_leverage === "Medium" ? "text-amber-500" : "text-rose-500"}>{insights.negotiation_leverage}</span></span>
        </p>
        <p className="text-sm text-[var(--muted-foreground)]">
          {insights.recommendation}
        </p>
      </div>
    </div>
  );
}
