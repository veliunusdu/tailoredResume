"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, X, Sparkles } from "lucide-react";
import { SearchConfigPanel } from "./SearchConfigPanel";

interface FloatingCopilotProps {
  onConfigSaved: () => void;
}

export function FloatingCopilot({ onConfigSaved }: FloatingCopilotProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-24 right-6 w-[400px] z-50 shadow-2xl rounded-2xl overflow-hidden border border-[var(--border)] bg-[var(--background)] flex flex-col max-h-[80vh]"
          >
            <div className="bg-gradient-to-r from-indigo-500 to-purple-600 p-4 flex justify-between items-center text-white">
              <div className="flex items-center gap-2 font-bold">
                <Sparkles className="w-5 h-5" />
                <span>Search Copilot</span>
              </div>
              <button 
                onClick={() => setIsOpen(false)}
                className="p-1 hover:bg-white/20 rounded-md transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="overflow-y-auto p-4 flex-1">
              {/* SearchConfigPanel handles its own state and AI saving */}
              <SearchConfigPanel onConfigSaved={() => {
                // When config is saved, we optionally could close the panel, 
                // but keeping it open lets them see the visualizer update.
                onConfigSaved();
              }} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-gradient-to-tr from-indigo-600 to-purple-600 text-white rounded-full flex justify-center items-center shadow-lg shadow-indigo-500/25 z-50 border-[3px] border-[var(--background)]"
        title="Open Search Copilot"
      >
        {isOpen ? <X className="w-6 h-6" /> : <Bot className="w-6 h-6" />}
      </motion.button>
    </>
  );
}
