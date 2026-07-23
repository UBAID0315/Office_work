import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, Loader2, AlertCircle } from 'lucide-react';

export function UploadScreen({ onUpload, appState, progressMessage, errorMessage, onReset }) {
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);

  const disabled = appState === 'processing';
  const isProcessing = appState === 'processing';
  const isError = appState === 'error';

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onUpload(e.target.files);
    }
    e.target.value = '';
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled || isError) return;
    dragCounter.current += 1;
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);

    if (disabled || isError) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onUpload(e.dataTransfer.files);
      e.dataTransfer.clearData();
    }
  };

  return (
    <div className="w-full h-full min-h-[500px] flex-1 flex items-center justify-center p-4 sm:p-6 md:p-8">
      <div
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`w-full max-w-[95%] sm:max-w-xl md:max-w-2xl p-8 sm:p-12 pt-12 sm:pt-16 shrink-0 bg-surface/80 backdrop-blur-2xl rounded-[2rem] shadow-2xl flex flex-col items-center text-center border transition-all duration-500 ${
          isDragging ? 'border-primary bg-primary/5 scale-[1.02] shadow-primary/20' : 'border-outline/50 hover:border-outline shadow-black/50'
        }`}
      >
        <div className="relative mb-6 sm:mb-8">
          <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-2xl bg-gradient-to-br from-primary/20 to-transparent flex items-center justify-center ring-1 ring-primary/30 relative overflow-hidden">
            <FileText size={40} className="text-primary" />
            {isProcessing && (
              <div className="absolute inset-0 bg-primary/20 animate-scan border-b-2 border-primary shadow-[0_0_15px_rgba(16,185,129,0.5)]"></div>
            )}
          </div>
        </div>

        <h1 className="font-display text-2xl sm:text-4xl font-bold text-textMain mb-3 leading-tight tracking-tight">
          Document Intelligence Engine
        </h1>
        <p className="text-sm sm:text-lg text-textMuted mb-8 sm:mb-10 leading-relaxed max-w-[80%] font-medium">
          Secure AI classification and extraction matrix.
        </p>

        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          className="hidden"
          multiple
          accept=".pdf,image/png,image/jpeg,image/jpg"
          aria-label="Upload document file"
        />

        <div
          onClick={() => {
            if (isError) {
              onReset();
            } else if (!disabled) {
              fileInputRef.current?.click();
            }
          }}
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              if (isError) onReset();
              else if (!disabled) fileInputRef.current?.click();
            }
          }}
          className={`w-full rounded-2xl border border-dashed p-8 sm:p-12 cursor-pointer transition-all duration-500 flex flex-col items-center gap-4 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none ${
            disabled ? 'cursor-not-allowed opacity-60' : 'hover:border-primary hover:bg-primary/5'
          } ${isDragging ? 'border-primary bg-primary/10 shadow-[inset_0_0_30px_rgba(16,185,129,0.1)]' : 'border-outline'} ${
            isError ? 'border-red-500/50 bg-red-950/20 hover:bg-red-950/30' : ''
          }`}
        >
          {isProcessing && (
            <>
              <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full flex items-center justify-center bg-primary/10 text-primary">
                <Loader2 size={32} className="animate-spin text-primary" />
              </div>
              <p className="text-base sm:text-xl font-semibold text-textMain mt-3 font-display tracking-wide">
                Processing Document…
              </p>
              <p className="text-sm sm:text-base text-primary text-center max-w-[85%] mt-1 font-medium">
                {progressMessage}
              </p>
            </>
          )}

          {isError && (
            <>
              <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full flex items-center justify-center bg-red-500/10 text-red-500">
                <AlertCircle size={32} />
              </div>
              <p className="text-base sm:text-xl font-semibold text-red-400 mt-3 font-display">
                Extraction Failed
              </p>
              <p className="text-sm sm:text-base text-red-400/80 text-center max-w-[85%] mt-1">
                {errorMessage}
              </p>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onReset();
                }}
                className="mt-5 px-6 py-2.5 bg-red-500 hover:bg-red-600 text-white text-sm font-semibold rounded-xl shadow-lg transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-surface focus-visible:ring-red-500 focus-visible:outline-none cursor-pointer"
              >
                Try Again
              </button>
            </>
          )}

          {!isProcessing && !isError && (
            <>
              <div
                className={`w-14 h-14 sm:w-16 sm:h-16 rounded-2xl flex items-center justify-center transition-all duration-500 ${
                  isDragging ? 'bg-primary/20 text-primary scale-110 shadow-[0_0_20px_rgba(16,185,129,0.3)]' : 'bg-surface border border-outline text-textMuted shadow-md'
                }`}
              >
                {isDragging ? (
                  <UploadCloud size={32} className="text-primary" />
                ) : (
                  <UploadCloud size={32} className="text-textMuted transition-colors group-hover:text-primary" />
                )}
              </div>

              <p className="text-base sm:text-xl font-semibold text-textMain font-display tracking-wide">
                {isDragging ? 'Initiate sequence…' : 'Drag & drop securely here'}
              </p>
              <p className="text-sm sm:text-base text-textMuted font-medium">or click to manually browse</p>
              <div className="flex gap-2 mt-2">
                {['PDF', 'PNG', 'JPG'].map(ext => (
                  <span key={ext} className="px-2 py-1 rounded bg-surface border border-outline text-[10px] sm:text-xs font-bold text-textMuted tracking-wider">{ext}</span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}