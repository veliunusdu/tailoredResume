"use client";

import React, { useState } from "react";
import { Job } from "../types";
import { JobCard } from "./JobCard";
import { apiPut } from "@/lib/api";
import { useSafeAuth } from "../hooks/useSafeAuth";

const COLUMNS = [
  { id: "saved", label: "Saved for Later", color: "border-slate-500/30 bg-slate-500/5 text-slate-400" },
  { id: "queued", label: "Ready to Tailor", color: "border-indigo-500/30 bg-indigo-500/5 text-indigo-400" },
  { id: "applied", label: "Applied", color: "border-emerald-500/30 bg-emerald-500/5 text-emerald-400" },
  { id: "interview", label: "Interviewing", color: "border-amber-500/30 bg-amber-500/5 text-amber-400" },
  { id: "rejected", label: "Rejected", color: "border-rose-500/30 bg-rose-500/5 text-rose-400" },
];

export function KanbanBoard({ jobs, setJobs }: { jobs: Job[], setJobs: React.Dispatch<React.SetStateAction<Job[]>> }) {
  const { getToken } = useSafeAuth();
  const [draggedJobId, setDraggedJobId] = useState<string | null>(null);

  const handleDragStart = (e: React.DragEvent, jobId: string) => {
    setDraggedJobId(jobId);
    // Needed for Firefox
    e.dataTransfer.setData("text/plain", jobId);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDrop = async (e: React.DragEvent, statusId: string) => {
    e.preventDefault();
    if (!draggedJobId) return;

    const jobId = draggedJobId;
    const jobToUpdate = jobs.find(j => j.id === jobId);
    if (!jobToUpdate || jobToUpdate.status === statusId) {
      setDraggedJobId(null);
      return;
    }

    // Optimistic update
    const previousStatus = jobToUpdate.status;
    setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: statusId } : j));
    setDraggedJobId(null);

    // Persist
    try {
      await apiPut(`/jobs/${jobId}/status`, { status: statusId }, getToken);
    } catch (err) {
      console.error("Failed to update job status", err);
      // Revert on error
      setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: previousStatus } : j));
    }
  };

  return (
    <div className="flex gap-4 overflow-x-auto pb-8 snap-x">
      {COLUMNS.map(col => {
        const columnJobs = jobs.filter(j => (j.status || "saved") === col.id);

        return (
          <div 
            key={col.id} 
            className="flex-shrink-0 w-80 lg:w-96 flex flex-col gap-3 snap-center"
            onDragOver={handleDragOver}
            onDrop={(e) => handleDrop(e, col.id)}
          >
            {/* Column Header */}
            <div className={`p-3 rounded-xl border ${col.color} font-bold flex justify-between items-center`}>
              <span>{col.label}</span>
              <span className="bg-black/20 px-2 py-0.5 rounded-md text-xs">{columnJobs.length}</span>
            </div>

            {/* Column Body */}
            <div className="flex-1 min-h-[200px] bg-black/10 rounded-2xl p-3 border border-[var(--border)] border-dashed flex flex-col gap-3">
              {columnJobs.map((job, idx) => (
                <div
                  key={job.id}
                  draggable
                  onDragStart={(e) => handleDragStart(e, job.id)}
                  className={`cursor-grab active:cursor-grabbing transition-transform ${draggedJobId === job.id ? 'opacity-50 scale-95' : ''}`}
                >
                  {/* Reuse JobCard but slightly scaled down via CSS or just as is */}
                  <div className="pointer-events-none md:pointer-events-auto">
                    <JobCard job={job} index={idx} />
                  </div>
                </div>
              ))}
              {columnJobs.length === 0 && (
                <div className="text-center text-sm font-semibold text-[var(--muted-foreground)] my-auto p-4 opacity-50">
                  Drop jobs here
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
