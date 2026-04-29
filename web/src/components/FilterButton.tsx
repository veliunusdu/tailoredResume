"use client";

import React from "react";

export function FilterButton({ 
  active, 
  onClick, 
  label, 
  count, 
  color = "indigo" 
}: { 
  active: boolean, 
  onClick: () => void, 
  label: string, 
  count?: number, 
  color?: string 
}) {
  const colorStyles: Record<string, string> = {
    indigo: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 border-indigo-500/30",
    emerald: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
    amber: "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30",
  };

  return (
    <button 
      onClick={onClick}
      className={`w-full text-left px-4 py-3 rounded-xl text-sm font-bold transition-all duration-300 flex items-center justify-between border ${
        active 
          ? `${colorStyles[color]} shadow-md` 
          : "border-transparent text-[var(--muted-foreground)] hover:bg-[var(--secondary)]"
      }`}
    >
      {label}
      {count !== undefined && (
        <span className={`text-[10px] px-2.5 py-1 rounded-full font-black ${active ? "bg-[var(--background)]" : "bg-[var(--background)]"}`}>
          {count}
        </span>
      )}
    </button>
  );
}
