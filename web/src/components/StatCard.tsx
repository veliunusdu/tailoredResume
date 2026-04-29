"use client";

import React from "react";
import { motion } from "framer-motion";

export function StatCard({ 
  icon, 
  label, 
  value, 
  subValue, 
  color 
}: { 
  icon: React.ReactNode, 
  label: string, 
  value: string | number, 
  subValue: string, 
  color: string 
}) {
  const bgColors: Record<string, string> = {
    blue: "bg-blue-500/10",
    emerald: "bg-emerald-500/10",
    amber: "bg-amber-500/10",
    indigo: "bg-indigo-500/10",
  };
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass p-6 rounded-2xl group hover:-translate-y-1 transition-all duration-300 relative overflow-hidden shadow-lg shadow-black/5"
    >
      <div className={`absolute top-0 right-0 w-24 h-24 rounded-full blur-2xl -mr-10 -mt-10 opacity-50 transition-opacity group-hover:opacity-100 ${bgColors[color]}`}></div>
      
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-5 ${bgColors[color]} relative z-10`}>
        {icon}
      </div>
      <p className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest mb-2 relative z-10">{label}</p>
      <h3 className="text-4xl font-extrabold text-[var(--foreground)] mb-2 tracking-tight relative z-10">{value}</h3>
      <p className="text-sm font-medium text-[var(--muted-foreground)] relative z-10">{subValue}</p>
    </motion.div>
  );
}
