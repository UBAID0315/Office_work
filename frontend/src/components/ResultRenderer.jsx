import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ExpandableInput } from './ExpandableInput';
import { 
  Loader2,
  OctagonAlert, 
  ThumbsDown,
  CheckCircle2, 
  FileText, 
  Check, 
  ExternalLink,
  Bot,
  Cpu
} from 'lucide-react';

const formatName = (key) => {
  return key
    .toString()
    .replace(/^section_\d+_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (l) => l.toUpperCase());
};

const LOW_CONF_THRESHOLD = 0.8;

const ConfidenceBadge = ({ confidence }) => {
  if (confidence === null || confidence === undefined) {
    return <span className="inline-flex items-center px-2 py-0.5 rounded text-sm font-semibold bg-surface border border-outline text-textMuted font-display">N/A</span>;
  }
  const pct = (confidence * 100).toFixed(1);
  let cls = "bg-emerald-500/10 text-emerald-500 border-emerald-500/30";
  if (confidence < 0.5) cls = "bg-red-500/15 text-red-400 border-red-500/30 font-bold";
  else if (confidence < LOW_CONF_THRESHOLD) cls = "bg-amber-500/15 text-amber-400 border-amber-500/30 font-bold";
  
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-sm font-semibold border tabular-nums font-display ${cls}`}>
      {pct}%
    </span>
  );
};

// Left Panel: Document Viewer Component (Expanded Width ~540px)
const DocumentViewer = ({ fileUrls }) => {
  const activeFile = fileUrls && fileUrls.length > 0 ? fileUrls[0] : null;

  return (
    <div className="w-full lg:w-[48%] xl:w-[50%] 2xl:w-[50%] flex-shrink-0 flex flex-col bg-surface border-b lg:border-b-0 lg:border-r border-outline/50 h-[420px] sm:h-[500px] lg:h-full sticky top-0 z-10 transition-all shadow-md">
      {/* Panel Header */}
      <div className="px-5 py-3.5 border-b border-outline/50 flex items-center justify-between bg-surface shrink-0">
        <div className="flex items-center gap-2.5">
          <FileText size={20} className="text-primary" />
          <span className="font-display font-bold text-lg font-bold text-textMain truncate max-w-[260px]" title={activeFile?.name || 'Document Preview'}>
            {activeFile?.name || 'Uploaded Document'}
          </span>
        </div>
        {activeFile?.url && (
          <a
            href={activeFile.url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 text-textMuted hover:text-textMain hover:bg-outline/20 rounded-xl transition-colors flex items-center gap-1.5 text-sm font-semibold"
            title="Open original document in new window"
          >
            <ExternalLink size={15} /> Open Full PDF
          </a>
        )}
      </div>

      {/* Embedded Document View */}
      <div className="flex-1 overflow-auto bg-background/60 p-4 flex items-center justify-center relative">
        {activeFile?.url ? (
          activeFile.type?.includes('pdf') ? (
            <iframe
              src={activeFile.url}
              className="w-full h-full rounded-xl border border-outline/50 bg-white shadow-sm"
              title="Document PDF Preview"
            />
          ) : (
            <div className="w-full h-full overflow-auto flex items-center justify-center">
              <img
                src={activeFile.url}
                alt="Document Preview"
                className="max-w-full max-h-full object-contain rounded-xl shadow-lg border border-outline/50 transition-all duration-300"
              />
            </div>
          )
        ) : (
          <div className="flex flex-col items-center justify-center p-8 text-center text-textMuted gap-3">
            <FileText size={52} className="opacity-40" />
            <p className="text-base font-semibold">Source Document Preview</p>
            <p className="text-sm text-textMuted/70 max-w-[240px] leading-relaxed">
              Uploaded document will render here for live cross-verification.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

// Smart Field Row: Full Comparison Card layout for both Agreed and Disagreed states
const SmartFieldRow = ({ label, fieldObj, path, onUpdate }) => {
  let azure = (fieldObj && fieldObj.azure) ? fieldObj.azure : (fieldObj && (fieldObj.value !== undefined || fieldObj.options) ? fieldObj : {});
  let glm = (fieldObj && fieldObj.glm) ? fieldObj.glm : {};
  let corrected = (fieldObj && fieldObj.corrected) ? fieldObj.corrected : {};

  let azureVal = azure.value !== undefined ? String(azure.value).trim() : (azure.selected !== undefined ? String(azure.selected).trim() : '');
  let glmVal = glm.value !== undefined && glm.value !== null ? String(glm.value).trim() : '';

  let defaultVal = corrected.value !== undefined 
    ? corrected.value 
    : (corrected.selected !== undefined 
      ? corrected.selected 
      : (azureVal || glmVal));

  let isGlmLoading = glm.status === 'processing';

  // Determine agreement state
  let hasBothValues = azureVal && glmVal && glmVal !== '—' && glmVal !== 'unreadable' && !isGlmLoading;
  let isDisagreed = hasBothValues && azureVal.toLowerCase() !== glmVal.toLowerCase();
  
  // Check Azure confidence threshold (Azure is the official OCR confidence provider)
  let isLowConfidence = azure.confidence !== undefined && azure.confidence !== null && azure.confidence < LOW_CONF_THRESHOLD;
  
  // Track if human edited the field
  let isHumanEdited = corrected.value !== undefined || corrected.selected !== undefined;

  let needsReview = isDisagreed || isLowConfidence;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-20px" }}
      transition={{ duration: 0.3, ease: [0.25, 0.1, 0.25, 1.0] }}
      className="mb-4"
    >
      {needsReview ? (
        /* EXPANDED WARNING STATE: Expanded Warning Card with Side-by-Side Comparison */
        <div className={`p-4 sm:p-5 rounded-2xl border-2 shadow-lg relative overflow-hidden transition-all ${isDisagreed ? 'border-amber-500/50 bg-amber-500/[0.05]' : 'border-red-500/40 bg-red-500/[0.03]'}`}>
          {/* Card Title & Status Header (Icon-based indicators: ThumbsDown for mismatch, OctagonAlert for low confidence) */}
          <div className={`flex items-center justify-between mb-3.5 pb-2.5 border-b gap-2 ${isDisagreed ? 'border-amber-500/25' : 'border-red-500/20'}`}>
            <div className="flex items-center gap-2.5">
              {isDisagreed ? (
                <span className="p-1.5 rounded-lg bg-amber-500/20 text-amber-500 border border-amber-500/30 flex items-center justify-center shrink-0" title="Values Disagree">
                  <ThumbsDown size={18} />
                </span>
              ) : (
                <span className="p-1.5 rounded-lg bg-red-500/20 text-red-500 border border-red-500/30 flex items-center justify-center shrink-0" title="Low Confidence Warning">
                  <OctagonAlert size={18} />
                </span>
              )}
              <span className="text-base sm:text-lg font-bold text-textMain font-display">
                {label}
              </span>
            </div>            
          </div>

          {/* Side-by-Side Comparison Engine Boxes */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            {/* Azure Box */}
            <div 
              onClick={() => onUpdate(path, azureVal)}
              className="p-4 rounded-xl border-2 border-outline/70 bg-surface hover:border-primary cursor-pointer transition-all flex flex-col justify-between shadow-sm group"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold uppercase tracking-wider text-textMuted flex items-center gap-1.5 font-display">
                    <Cpu size={14} className="text-sky-400" /> Azure AI Engine
                  </span>
                  <ConfidenceBadge confidence={azure.confidence} />
                </div>
                <p className="text-lg font-bold text-textMain mb-3 break-words">{azureVal || '—'}</p>
              </div>
              <button 
                type="button"
                className="w-max px-3 py-1 text-sm font-bold text-primary bg-primary/10 group-hover:bg-primary group-hover:text-white rounded-lg transition-all flex items-center gap-1 font-display"
              >
                <Check size={13} /> Select Azure
              </button>
            </div>

            {/* GLM Box */}
            <div 
              onClick={() => !isGlmLoading && onUpdate(path, glmVal)}
              className={`p-4 rounded-xl border-2 border-outline/70 bg-surface transition-all flex flex-col justify-between shadow-sm group ${isGlmLoading ? 'opacity-70 cursor-wait' : 'hover:border-primary cursor-pointer'}`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold uppercase tracking-wider text-textMuted flex items-center gap-1.5 font-display">
                    <Bot size={14} className="text-emerald-400" /> GLM-OCR Engine
                  </span>
                  <span className="px-2 py-0.5 text-xs font-bold rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-display">GLM AI</span>
                </div>
                {isGlmLoading ? (
                  <div className="flex items-center gap-2 text-textMuted text-sm font-bold py-1 mb-3">
                    <Loader2 size={16} className="animate-spin text-emerald-500" /> Processing...
                  </div>
                ) : (
                  <p className="text-lg font-bold text-textMain mb-3 break-words">{glmVal || '—'}</p>
                )}
              </div>
              {!isGlmLoading && (
                <button 
                  type="button"
                  className="w-max px-3 py-1 text-sm font-bold text-primary bg-primary/10 group-hover:bg-primary group-hover:text-white rounded-lg transition-all flex items-center gap-1 font-display"
                >
                  <Check size={13} /> Select GLM
                </button>
              )}
            </div>
          </div>

          {/* Confirmed / Human Corrected Field Input */}
          <div className="pt-2 border-t border-amber-500/20">
            <label className="text-sm font-semibold text-primary uppercase tracking-wider font-display mb-1.5 flex items-center gap-2">
              Confirmed Value {isHumanEdited && <span className="text-sm bg-primary/20 text-primary px-2 py-0.5 rounded-full font-bold">✍️ Manually Edited</span>}
            </label>
            {azure.options ? (
              <select 
                className="w-full px-4 py-3 text-sm font-bold border-2 border-primary/50 rounded-xl bg-surface text-textMain outline-none focus:ring-2 focus:ring-primary shadow-sm"
                value={defaultVal || ''}
                onChange={(e) => onUpdate(path, e.target.value)}
              >
                <option value="">-- Select --</option>
                {azure.options.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            ) : (
              <ExpandableInput label={label} value={defaultVal || ''} onChange={(val) => onUpdate(path, val)} />
            )}
          </div>
        </div>
      ) : (
        /* HIGH CONFIDENCE MATCH STATE: Card showing both outputs matching with high confidence */
        <div className="p-4 rounded-2xl border border-outline/70 bg-surface/90 hover:bg-surface transition-all flex flex-col md:flex-row md:items-end justify-between gap-4 shadow-sm">
          {/* Left: Field Name & Agreed Badges */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="text-lg font-semibold text-textMain font-display">{label}</span>
              {isGlmLoading ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-sm font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-display">
                  <Loader2 size={13} className="animate-spin" /> Verifying with GLM...
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-sm font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-display">
                  <CheckCircle2 size={13} /> High Confidence Match
                </span>
              )}
              <ConfidenceBadge confidence={azure.confidence} />
            </div>

            {/* Extracted Values Side-by-Side Breakdown */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm font-medium text-textMuted bg-background/60 min-h-12 h-auto py-1.5 px-4 rounded-xl border border-outline/40">
              <div className="flex items-center gap-1.5 whitespace-nowrap">
                <Cpu size={13} className="text-sky-400 shrink-0" />
                <span>Azure:</span>
                <span className="text-textMain font-bold text-base">{azureVal || '—'}</span>
              </div>
              <span className="opacity-30">•</span>
              <div className="flex items-center gap-1.5 whitespace-nowrap">
                <Bot size={13} className="text-emerald-400 shrink-0" />
                <span>GLM:</span>
                {isGlmLoading ? (
                  <span className="flex items-center gap-1.5 text-textMuted text-sm font-bold">
                    <Loader2 size={14} className="animate-spin text-emerald-500" /> Processing...
                  </span>
                ) : (
                  <span className="text-textMain font-bold text-base">{glmVal || '—'}</span>
                )}
              </div>
            </div>
          </div>

          {/* Right: Quick Edit Confirmed Input & Unambiguous Review Badges (Gap 4 fix) */}
          <div className="w-full md:w-[280px] lg:w-[320px] shrink-0 flex items-center gap-2">
            <div className="flex-1">
              {azure.options ? (
                <select 
                  className="w-full h-12 px-4 text-sm font-semibold border border-outline rounded-xl bg-background text-textMain outline-none focus:border-primary"
                  value={defaultVal || ''}
                  onChange={(e) => onUpdate(path, e.target.value)}
                >
                  <option value="">-- Select --</option>
                  {azure.options.map(opt => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : (
                <ExpandableInput label={label} value={defaultVal || ''} onChange={(val) => onUpdate(path, val)} />
              )}
            </div>
            {isHumanEdited ? (
              <span className="text-sm text-primary font-bold whitespace-nowrap bg-primary/10 border border-primary/20 px-2 py-1 rounded" title="Manually edited">✍️ Edited</span>
            ) : needsReview ? (
              <span className="text-sm text-amber-500 font-bold whitespace-nowrap bg-amber-500/10 border border-amber-500/20 px-2 py-1 rounded" title="Needs review">⚠️ Review</span>
            ) : (
              <span className="text-sm text-emerald-500 font-bold whitespace-nowrap bg-emerald-500/10 border border-emerald-500/20 px-2 py-1 rounded" title="Auto-accepted">✓ Accepted</span>
            )}
          </div>
        </div>
      )}
    </motion.div>
  );
};

export function ResultRenderer({ data, fileUrls, onUpdate }) {
  // Helper to count fields and disagreements for document metrics bar
  const calculateMetrics = (obj) => {
    let total = 0;
    let disagreements = 0;
    let matches = 0;

    const traverse = (item) => {
      if (Array.isArray(item)) {
        item.forEach(traverse);
      } else if (item && typeof item === 'object') {
        if ('azure' in item || 'value' in item) {
          total++;
          let az = item.azure ? String(item.azure.value || item.azure.selected || '').trim() : '';
          let gl = item.glm ? String(item.glm.value || '').trim() : '';
          let azConf = item.azure && item.azure.confidence !== undefined ? item.azure.confidence : null;
          let isLowConf = azConf !== null && azConf < LOW_CONF_THRESHOLD;
          
          if (az && gl && gl !== '—' && gl !== 'unreadable' && az.toLowerCase() !== gl.toLowerCase()) {
            disagreements++;
          } else if (isLowConf) {
            disagreements++; // Treat low confidence as needing review for the metric
          } else {
            matches++;
          }
        } else {
          Object.values(item).forEach(traverse);
        }
      }
    };

    traverse(obj);
    return { total, disagreements, matches };
  };

  const metrics = calculateMetrics(data);

  return (
    <div className="flex flex-col lg:flex-row h-full w-full overflow-hidden bg-background">
      {/* Sticky Left Panel: Document Viewer (Wider ~540px) */}
      <DocumentViewer fileUrls={fileUrls} />

      {/* Main Right Panel: Verification Stream (Expanded Width) */}
      <div className="flex-1 flex flex-col h-full overflow-auto p-4 sm:p-6 lg:p-8">
        
        {/* Document Summary Header & Metric Cards */}
        <div className="mb-6 pb-4 border-b border-outline/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-3xl font-extrabold font-display text-textMain tracking-tight">Field Verification Stream</h2>
            <p className="text-sm font-medium text-textMuted uppercase tracking-wider mt-1 font-display">
              Side-by-Side Dual AI Cross-Check • Natural Document Order
            </p>
          </div>

          {/* Metric Badges */}
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="px-3.5 py-1.5 rounded-xl border border-outline bg-surface text-sm font-medium text-textMain shadow-sm font-display">
              Total Fields: {metrics.total}
            </span>
            <span className="px-3.5 py-1.5 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-sm font-bold text-emerald-700 dark:text-emerald-400 shadow-sm font-display flex items-center gap-1.5">
              <CheckCircle2 size={15} /> Matches: {metrics.matches}
            </span>
            {metrics.disagreements > 0 && (
              <span className="px-3.5 py-1.5 rounded-xl border border-amber-500/60 bg-amber-500/20 text-sm font-bold text-amber-800 dark:text-amber-300 shadow-sm font-display flex items-center gap-1.5">
                <OctagonAlert size={15} className="text-amber-600 dark:text-amber-400" /> {metrics.disagreements} Needs Review
              </span>
            )}
          </div>
        </div>

        {/* Legend Key */}
        <div className="mb-6 p-3.5 rounded-xl bg-surface/70 border border-outline/50 flex flex-wrap items-center justify-between gap-3 text-sm font-semibold text-textMuted shadow-sm">
          <div className="flex flex-wrap items-center gap-5">
            <span className="flex items-center gap-1.5 text-emerald-500 font-bold">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> High Confidence Match
            </span>
            <span className="flex items-center gap-1.5 text-amber-400 font-bold">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400"></span> Disagreement Detected
            </span>
            <span className="flex items-center gap-1.5 text-red-400 font-bold">
              <span className="w-2.5 h-2.5 rounded-full bg-red-400"></span> Low Confidence Flag
            </span>
            <span className="flex items-center gap-1.5 text-primary font-bold">
              <span>✍️</span> Manually Edited
            </span>
          </div>
          <span className="text-sm font-medium opacity-80">Click any Azure/GLM box to accept candidate value</span>
        </div>

        {/* Render Field Groups */}
        <div className="flex-1 space-y-6 pb-12">
          {Array.isArray(data) ? (
            data.map((doc, idx) => (
              <div key={idx} className="space-y-3">
                {data.length > 1 && (
                  <h3 className="text-xl font-bold text-primary uppercase tracking-wider py-2 font-display">
                    Document {idx + 1}
                  </h3>
                )}
                {Object.entries(doc).map(([key, field]) => {
                  if (typeof field === 'object' && field !== null && ('azure' in field || 'value' in field)) {
                    return (
                      <SmartFieldRow 
                        key={key} 
                        label={formatName(key)} 
                        fieldObj={field} 
                        path={`[${idx}].${key}`} 
                        onUpdate={onUpdate} 
                      />
                    );
                  }
                  return null;
                })}
              </div>
            ))
          ) : (
            Object.entries(data).map(([key, val]) => {
              if (key === "form_title") return null;

              return (
                <div key={key} className="space-y-3">
                  <h3 className="text-lg font-semibold text-primary uppercase tracking-widest font-display pb-1 border-b border-outline/40">
                    {formatName(key)}
                  </h3>

                  {Array.isArray(val) ? (
                    val.map((item, idx) => (
                      <motion.div 
                        key={idx} 
                        initial={{ opacity: 0, y: 16 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true, margin: "-20px" }}
                        transition={{ duration: 0.35, ease: [0.25, 0.1, 0.25, 1.0] }}
                        className="mx-2 sm:mx-4 my-5 p-4 sm:p-6 pr-6 sm:pr-8 bg-surface/70 dark:bg-surface/50 rounded-2xl border border-outline/70 shadow-md hover:shadow-lg transition-all space-y-4 mb-8"
                      >
                        <div className="flex items-center justify-between pb-2 border-b border-outline/40 mb-3">
                          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs sm:text-sm font-bold text-primary bg-primary/10 border border-primary/20 uppercase tracking-wider font-display">
                            Entry {idx + 1}
                          </span>
                        </div>
                        {typeof item === 'object' && item !== null && Object.entries(item).map(([sk, sv]) => (
                          <SmartFieldRow key={sk} label={formatName(sk)} fieldObj={sv} path={`${key}[${idx}].${sk}`} onUpdate={onUpdate} />
                        ))}
                      </motion.div>
                    ))
                  ) : typeof val === 'object' && val !== null && !('azure' in val || 'value' in val) ? (
                    Object.entries(val).map(([sk, sv]) => {
                      if (Array.isArray(sv)) {
                        return (
                          <div key={sk} className="my-5 space-y-4">
                            <span className="inline-block text-sm font-bold text-textMuted uppercase font-display tracking-wider mb-1">{formatName(sk)}</span>
                            {sv.map((item, idx) => (
                              <motion.div 
                                key={idx} 
                                initial={{ opacity: 0, y: 16 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true, margin: "-20px" }}
                                transition={{ duration: 0.35, ease: [0.25, 0.1, 0.25, 1.0] }}
                                className="mx-2 sm:mx-4 p-4 sm:p-6 pr-6 sm:pr-8 bg-surface/70 dark:bg-surface/50 rounded-2xl border border-outline/70 shadow-md hover:shadow-lg transition-all space-y-4 mb-8"
                              >
                                <div className="flex items-center justify-between pb-2 border-b border-outline/40 mb-3">
                                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs sm:text-sm font-bold text-primary bg-primary/10 border border-primary/20 uppercase tracking-wider font-display">
                                    Entry {idx + 1}
                                  </span>
                                </div>
                                {typeof item === 'object' && item !== null && Object.entries(item).map(([subK, subV]) => (
                                  <SmartFieldRow key={subK} label={formatName(subK)} fieldObj={subV} path={`${key}.${sk}[${idx}].${subK}`} onUpdate={onUpdate} />
                                ))}
                              </motion.div>
                            ))}
                          </div>
                        );
                      }
                      return (
                        <SmartFieldRow key={sk} label={formatName(sk)} fieldObj={sv} path={`${key}.${sk}`} onUpdate={onUpdate} />
                      );
                    })
                  ) : (
                    <SmartFieldRow label={formatName(key)} fieldObj={val} path={key} onUpdate={onUpdate} />
                  )}
                </div>
              );
            })
          )}
        </div>

      </div>
    </div>
  );
}
