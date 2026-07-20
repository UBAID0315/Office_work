import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, X } from 'lucide-react';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export function ExpandableInput({ value, onChange, label }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [localValue, setLocalValue] = useState(value);
  const containerRef = useRef(null);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  const handleSave = () => {
    onChange(localValue);
    setIsExpanded(false);
  };

  const handleCancel = () => {
    setLocalValue(value);
    setIsExpanded(false);
  };

  // Allow Escape to cancel, Cmd/Ctrl+Enter to save
  useEffect(() => {
    if (!isExpanded) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') handleCancel();
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleSave();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded, localValue]);

  return (
    <div className="relative w-full h-10" ref={containerRef}>
      {/* Base compact input */}
      <input
        type="text"
        className={cn(
          "absolute inset-0 w-full h-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/20",
          "border-outline bg-surface text-textMain transition-all shadow-sm",
          isExpanded ? "opacity-0 pointer-events-none" : "opacity-100 cursor-text hover:border-primary/50"
        )}
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onFocus={() => setIsExpanded(true)}
      />

      {/* Centered modal overlay */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[50] bg-textMain/10 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={handleCancel}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ type: "spring", stiffness: 350, damping: 25 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md p-5 bg-surface border border-outline rounded-xl shadow-2xl"
            >
              <div className="flex justify-between items-center mb-3">
                <label className="text-[11px] font-bold uppercase tracking-wider text-textMuted">
                  Editing {label}
                </label>
              </div>

              <textarea
                autoFocus
                className="w-full min-h-[140px] p-3 text-sm border border-outline rounded-md focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-y bg-surface text-textMain"
                value={localValue}
                onChange={(e) => setLocalValue(e.target.value)}
              />

              <div className="flex justify-end gap-2 mt-4">
                <button
                  onClick={handleCancel}
                  className="px-3 py-1.5 text-sm font-medium text-textMuted bg-surface border border-outline rounded-md hover:bg-background hover:text-textMain transition-colors flex items-center gap-1"
                >
                  <X size={14} /> Cancel
                </button>
                <button
                  onClick={handleSave}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-primary rounded-md hover:bg-primary-hover shadow-sm transition-all flex items-center gap-1"
                >
                  <Check size={14} /> Save
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}