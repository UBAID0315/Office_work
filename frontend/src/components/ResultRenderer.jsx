import React from 'react';
import { ExpandableInput } from './ExpandableInput';

const formatName = (key) => {
  return key
    .toString()
    .replace(/^section_\d+_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (l) => l.toUpperCase());
};

const ConfidenceBadge = ({ confidence }) => {
  if (confidence === null || confidence === undefined) {
    return <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold bg-background text-textMuted">N/A</span>;
  }
  const pct = (confidence * 100).toFixed(1);
  let cls = "bg-green-100 text-green-800";
  if (confidence < 0.5) cls = "bg-red-100 text-red-800";
  else if (confidence < 0.8) cls = "bg-amber-100 text-amber-800";
  
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold ${cls}`}>
      {pct}%
    </span>
  );
};

const DisplayValue = ({ obj }) => {
  if (!obj) return <em className="text-outline">—</em>;
  if (obj.options) {
    return (
      <div className="flex flex-wrap gap-1">
        {obj.options.map(opt => (
          <span key={opt} className={`px-2 py-0.5 text-[10px] rounded-md ${opt === obj.selected ? 'bg-primary/10 text-primary font-bold' : 'bg-background text-textMuted'}`}>
            {opt === obj.selected ? '✓' : '☐'} {opt}
          </span>
        ))}
      </div>
    );
  }
  if (obj.value !== null && obj.value !== undefined && obj.value !== "") {
    return <span className="whitespace-pre-wrap">{obj.value}</span>;
  }
  return <em className="text-outline">—</em>;
};

const GlmSkeletonLoader = () => (
  <div className="flex flex-col gap-1.5 py-1">
    <div className="flex items-center gap-2 animate-pulse">
      <div className="w-3.5 h-3.5 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
      <div className="h-3.5 bg-slate-200 dark:bg-slate-700 rounded w-28"></div>
    </div>
    <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-600 w-max animate-pulse">
      Processing GLM...
    </span>
  </div>
);

// Represents a single row in the data table
const FieldRow = ({ label, fieldObj, path, onUpdate }) => {
  let azure = (fieldObj && fieldObj.azure) ? fieldObj.azure : (fieldObj && (fieldObj.value !== undefined || fieldObj.options) ? fieldObj : {});
  let glm = (fieldObj && fieldObj.glm) ? fieldObj.glm : {};
  let corrected = (fieldObj && fieldObj.corrected) ? fieldObj.corrected : {};

  let defaultVal = corrected.value !== undefined ? corrected.value : (corrected.selected !== undefined ? corrected.selected : (azure.value !== undefined ? azure.value : azure.selected));

  let isGlmLoading = glm.status === 'processing' || (!glm.value && !glm.status && Object.keys(glm).length === 0);

  return (
    <tr className="border-t border-outline hover:bg-background/50 transition-colors group flex flex-col md:table-row">
      <td className="py-2 md:py-3 px-4 md:px-6 align-top w-full md:w-1/4 bg-background/30 md:bg-transparent">
        <span className="text-sm font-semibold text-textMain">{label}</span>
      </td>
      <td className="py-2 md:py-3 px-4 md:px-6 align-top w-full md:w-1/4">
        <div className="text-xs md:text-sm text-textMuted md:hidden mb-1 font-semibold uppercase tracking-wider">Azure AI</div>
        <div className="text-sm text-textMain mb-1.5"><DisplayValue obj={azure} /></div>
        <ConfidenceBadge confidence={azure.confidence} />
      </td>
      <td className="py-2 md:py-3 px-4 md:px-6 align-top w-full md:w-1/4">
        <div className="text-xs md:text-sm text-textMuted md:hidden mb-1 font-semibold uppercase tracking-wider">GLM-OCR</div>
        {isGlmLoading ? (
          <GlmSkeletonLoader />
        ) : (
          <>
            <div className="text-sm text-textMain mb-1.5"><DisplayValue obj={glm} /></div>
            <ConfidenceBadge confidence={glm.confidence} />
          </>
        )}
      </td>
      <td className="py-2 md:py-3 px-4 md:px-6 align-top w-full md:w-1/4 pb-4 md:pb-3">
        <div className="text-xs md:text-sm text-textMuted md:hidden mb-1 font-semibold uppercase tracking-wider">Human Corrected</div>
        {azure.options ? (
          <select 
            className="w-full px-3 py-2 text-sm border border-outline rounded-md focus:border-primary focus:ring-1 focus:ring-primary bg-surface outline-none"
            value={defaultVal || ''}
            onChange={(e) => onUpdate(path, e.target.value)}
          >
            <option value="">-- Select --</option>
            {azure.options.map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        ) : (
          <ExpandableInput 
            label={label}
            value={defaultVal || ''}
            onChange={(val) => onUpdate(path, val)}
          />
        )}
      </td>
    </tr>
  );
};

// Represents a table wrapper for a group of fields
const TableWrapper = ({ children }) => (
  <div className="w-full overflow-hidden border border-outline bg-surface rounded-none mb-6">
    <table className="w-full text-left border-collapse block md:table">
      <thead className="hidden md:table-header-group">
        <tr className="bg-background text-[11px] uppercase tracking-wider text-textMuted border-b border-outline">
          <th className="py-3 px-6 font-bold w-1/4">Field</th>
          <th className="py-3 px-6 font-bold w-1/4">Azure AI</th>
          <th className="py-3 px-6 font-bold w-1/4">GLM-OCR</th>
          <th className="py-3 px-6 font-bold w-1/4">Human Corrected</th>
        </tr>
      </thead>
      <tbody className="block md:table-row-group">
        {children}
      </tbody>
    </table>
  </div>
);

export function ResultRenderer({ data, onUpdate }) {
  // If data is an array (e.g. CNIC), render each document
  if (Array.isArray(data)) {
    return (
      <div className="p-0">
        {data.map((doc, idx) => (
          <div key={idx}>
            {data.length > 1 && (
              <h2 className="text-sm font-bold text-primary uppercase tracking-wider px-4 md:px-6 py-4 bg-background border-b border-outline">
                Document {idx + 1}
              </h2>
            )}
            <TableWrapper>
              {Object.entries(doc).map(([key, field]) => {
                if (typeof field === 'object' && field !== null && ('azure' in field || 'value' in field)) {
                  return <FieldRow key={key} label={formatName(key)} fieldObj={field} path={`[${idx}].${key}`} onUpdate={onUpdate} />;
                }
                return null;
              })}
            </TableWrapper>
          </div>
        ))}
      </div>
    );
  }

  // Object data (e.g. NAF)
  const sections = [];
  
  if (data.form_title) {
    sections.push(
      <div key="title" className="text-lg font-bold text-textMain px-6 py-4 border-b border-outline bg-background/50">
        {data.form_title}
      </div>
    );
  }

  if (data.family_takaful_need_analysis_of) {
    sections.push(
      <div key="analysis_of" className="px-6">
        <TableWrapper>
          <FieldRow 
            label="Analysis Of" 
            fieldObj={data.family_takaful_need_analysis_of} 
            path="family_takaful_need_analysis_of" 
            onUpdate={onUpdate} 
          />
        </TableWrapper>
      </div>
    );
  }

  // Iterate over remaining sections
  for (const [key, val] of Object.entries(data)) {
    if (key === "form_title" || key === "family_takaful_need_analysis_of") continue;

    sections.push(
      <div key={key}>
        <h3 className="text-[11px] font-bold tracking-wider uppercase text-primary px-6 py-3 border-b border-outline bg-background/50">
          {formatName(key)}
        </h3>
        
        {Array.isArray(val) ? (
          // Arrays inside sections (e.g. dependents, existing plans)
          <div className="px-6 pt-4">
            {val.map((item, idx) => (
              <div key={idx} className="mb-4">
                <div className="text-xs font-semibold text-textMuted mb-2">Entry {idx + 1}</div>
                <TableWrapper>
                  {typeof item === 'object' && item !== null && Object.entries(item).map(([sk, sv]) => {
                    if (sv && typeof sv === "object" && ("azure" in sv || "value" in sv || "options" in sv)) {
                      return <FieldRow key={sk} label={`  ${formatName(sk)}`} fieldObj={sv} path={`${key}[${idx}].${sk}`} onUpdate={onUpdate} />;
                    } else if (sv === null || typeof sv !== "object") {
                      return <FieldRow key={sk} label={`  ${formatName(sk)}`} fieldObj={{ azure: { value: sv } }} path={`${key}[${idx}].${sk}`} onUpdate={onUpdate} />;
                    }
                    return null;
                  })}
                </TableWrapper>
              </div>
            ))}
          </div>
        ) : typeof val === 'object' && val !== null ? (
          // Object inside section
          <div className="px-6 pt-4">
            {("azure" in val || "value" in val || "options" in val) ? (
              <TableWrapper>
                <FieldRow label={formatName(key)} fieldObj={val} path={key} onUpdate={onUpdate} />
              </TableWrapper>
            ) : (
              <TableWrapper>
                {Object.entries(val).map(([sk, sv]) => {
                  if (sv && typeof sv === "object" && ("azure" in sv || "value" in sv || "options" in sv)) {
                    return <FieldRow key={sk} label={formatName(sk)} fieldObj={sv} path={`${key}.${sk}`} onUpdate={onUpdate} />;
                  }
                  return null;
                })}
              </TableWrapper>
            )}
          </div>
        ) : null}
      </div>
    );
  }

  return <div className="pb-8">{sections}</div>;
}
