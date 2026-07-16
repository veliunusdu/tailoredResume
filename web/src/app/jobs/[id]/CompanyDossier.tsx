"use client";

import { useEffect, useState } from "react";
import { useSafeAuth } from "@/hooks/useSafeAuth";
import { apiGet } from "@/lib/api";
import { Loader2, Building, Newspaper, Heart, Layers, ArrowRight } from "lucide-react";
import { getErrorMessage } from "@/utils/errors";

interface CompanyValue {
  title: string;
  description: string;
}

interface CompanyDossierData {
  summary: string;
  recent_news: string[];
  culture_values: CompanyValue[];
  tech_stack_hints: string[];
}

export function CompanyDossier({ jobId }: { jobId: string }) {
  const { getToken } = useSafeAuth();
  const [dossier, setDossier] = useState<CompanyDossierData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchDossier() {
      try {
        const data = await apiGet<CompanyDossierData>(`/jobs/${jobId}/company-research`, getToken);
        setDossier(data);
      } catch (error: unknown) {
        setError(getErrorMessage(error, "Failed to research the company."));
      } finally {
        setLoading(false);
      }
    }
    fetchDossier();
  }, [jobId, getToken]);

  if (loading) {
    return (
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-6 flex flex-col items-center justify-center min-h-[250px]">
        <Loader2 className="w-8 h-8 animate-spin text-pink-500 mb-4" />
        <p className="text-sm text-[var(--muted-foreground)] font-medium">Researching company background...</p>
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

  if (!dossier) return null;

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl overflow-hidden">
      <div className="p-6 border-b border-[var(--border)] bg-gradient-to-r from-[var(--background)] to-[var(--background)]/50 flex items-center gap-4">
        <div className="p-3 bg-pink-500/10 rounded-xl border border-pink-500/20">
          <Building className="w-6 h-6 text-pink-400" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-[var(--foreground)]">Company Intelligence</h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">{dossier.summary}</p>
        </div>
      </div>

      <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="space-y-6">
          <div>
            <h3 className="text-sm font-bold text-[var(--foreground)] flex items-center gap-2 uppercase tracking-wider mb-4">
              <Newspaper className="w-4 h-4 text-sky-400" />
              Recent News & Initiatives
            </h3>
            <ul className="space-y-3">
              {dossier.recent_news.map((news, i) => (
                <li key={i} className="flex items-start gap-3 text-sm text-[var(--muted-foreground)]">
                  <ArrowRight className="w-4 h-4 text-sky-500/50 mt-0.5 shrink-0" />
                  <span>{news}</span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-bold text-[var(--foreground)] flex items-center gap-2 uppercase tracking-wider mb-4">
              <Layers className="w-4 h-4 text-indigo-400" />
              Inferred Tech Stack
            </h3>
            <div className="flex flex-wrap gap-2">
              {dossier.tech_stack_hints.map((tech, i) => (
                <span key={i} className="px-3 py-1.5 bg-indigo-500/10 text-indigo-400 text-xs font-bold rounded-lg border border-indigo-500/20">
                  {tech}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div>
          <h3 className="text-sm font-bold text-[var(--foreground)] flex items-center gap-2 uppercase tracking-wider mb-4">
            <Heart className="w-4 h-4 text-rose-400" />
            Culture & Values
          </h3>
          <div className="space-y-4">
            {dossier.culture_values.map((val, i) => (
              <div key={i} className="p-4 rounded-xl bg-[var(--background)] border border-[var(--border)]">
                <h4 className="font-bold text-[var(--foreground)] mb-1 text-sm">{val.title}</h4>
                <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">{val.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
