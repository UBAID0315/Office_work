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
    <div className="relative w-full h-12" ref={containerRef}>
      {/* Base compact input */}
      <input
        type="text"
        className={cn(
          "absolute inset-0 w-full h-full px-4 py-3 text-base border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/50",
          "border-outline bg-surface/80 text-textMain transition-all shadow-inner text-ellipsis overflow-hidden whitespace-nowrap",
          isExpanded ? "opacity-0 pointer-events-none" : "opacity-100 cursor-text hover:border-primary/50"
        )}
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onFocus={() => setIsExpanded(true)}
        aria-label={label}
      />

      {/* Centered modal overlay */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[50] bg-background/80 backdrop-blur-md flex items-center justify-center p-4 sm:p-6"
            onClick={handleCancel}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ type: "spring", stiffness: 350, damping: 25 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-lg p-6 bg-surface border border-outline/50 rounded-2xl shadow-2xl"
            >
              <div className="flex justify-between items-center mb-4">
                <label className="text-xs font-bold uppercase tracking-widest text-primary font-display">
                  Editing: {label}
                </label>
              </div>

              <textarea
                autoFocus
                className="w-full min-h-[160px] p-4 text-base leading-relaxed border border-outline/50 rounded-xl focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/50 resize-y bg-background text-textMain shadow-inner transition-all"
                value={localValue}
                onChange={(e) => setLocalValue(e.target.value)}
                aria-label={`Edit ${label}`}
              />

              <div className="flex justify-end gap-3 mt-6">
                <button
                  onClick={handleCancel}
                  className="px-5 py-2.5 text-sm font-semibold text-textMuted bg-surface border border-outline/50 rounded-xl hover:bg-white/5 hover:text-textMain transition-all focus-visible:ring-2 focus-visible:ring-outline focus-visible:outline-none flex items-center gap-2"
                >
                  <X size={16} /> Cancel
                </button>
                <button
                  onClick={handleSave}
                  className="px-5 py-2.5 text-sm font-semibold text-white bg-primary rounded-xl hover:bg-primary-hover shadow-lg shadow-primary/20 transition-all focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none flex items-center gap-2"
                >
                  <Check size={16} /> Save Changes
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}