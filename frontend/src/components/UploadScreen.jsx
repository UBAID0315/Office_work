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
        className={`w-full max-w-[95%] sm:max-w-md md:max-w-lg lg:max-w-xl p-6 sm:p-8 pt-10 sm:pt-12 shrink-0 bg-surface rounded-3xl shadow-xl shadow-black/5 flex flex-col items-center text-center border-2 transition-all duration-300 ${
          isDragging ? 'border-primary bg-primary/5 scale-[1.02]' : 'border-transparent'
        }`}
      >
        <div className="relative mb-4 sm:mb-6">
          <img
            src="/images/logo.jpg"
            alt="Logo"
            className="w-24 h-24 sm:w-32 sm:h-32 md:w-35 md:h-35 rounded-full object-cover ring-4 ring-primary/10"
            onError={(e) => (e.target.style.display = 'none')}
          />
        </div>

        <h1 className="text-xl sm:text-2xl font-bold text-textMain mb-2 leading-tight">
          Document Intelligence Extractor
        </h1>
        <p className="text-xs sm:text-sm text-textMuted mb-6 sm:mb-8 leading-relaxed px-2">
          AI-powered document classification and extraction.
        </p>

        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          className="hidden"
          multiple
          accept=".pdf,image/png,image/jpeg,image/jpg"
        />

        <div
          onClick={() => {
            if (isError) {
              onReset();
            } else if (!disabled) {
              fileInputRef.current?.click();
            }
          }}
          className={`w-full rounded-2xl border-2 border-dashed p-6 sm:p-8 md:p-10 cursor-pointer transition-all duration-300 flex flex-col items-center gap-2 sm:gap-3 ${
            disabled ? 'cursor-not-allowed opacity-60' : 'hover:border-primary hover:bg-primary/5'
          } ${isDragging ? 'border-primary bg-primary/10' : 'border-gray-300'} ${
            isError ? 'border-red-300 bg-red-50/50 hover:bg-red-50 hover:border-red-400' : ''
          }`}
        >
          {isProcessing && (
            <>
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full flex items-center justify-center bg-primary/10 text-primary">
                <Loader2 size={24} className="animate-spin text-primary" />
              </div>
              <p className="text-sm font-semibold text-textMain mt-2">
                Processing Document
              </p>
              <p className="text-xs text-textMuted text-center max-w-[85%] leading-relaxed mt-1">
                {progressMessage}
              </p>
            </>
          )}

          {isError && (
            <>
              <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-full flex items-center justify-center bg-red-100 text-red-600">
                <AlertCircle size={24} />
              </div>
              <p className="text-sm font-semibold text-red-600 mt-2">
                Extraction Failed
              </p>
              <p className="text-xs text-red-500/80 text-center max-w-[85%] leading-relaxed mt-1">
                {errorMessage}
              </p>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onReset();
                }}
                className="mt-3 px-4 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg shadow-sm transition-colors cursor-pointer"
              >
                Try Again
              </button>
            </>
          )}

          {!isProcessing && !isError && (
            <>
              <div
                className={`w-12 h-12 sm:w-14 sm:h-14 rounded-full flex items-center justify-center transition-all duration-300 ${
                  isDragging ? 'bg-primary/10 text-primary scale-110' : 'bg-primary/10 text-black'
                }`}
              >
                {isDragging ? (
                  <FileText size={24} className="animate-bounce" />
                ) : (
                  <UploadCloud size={24} className="sm:w-6 sm:h-6" />
                )}
              </div>

              <p className="text-sm font-medium text-textMain">
                {isDragging ? 'Drop it like it’s hot 🔥' : 'Drag & drop a file here'}
              </p>
              <p className="text-xs text-textMuted">or click to browse</p>
              <p className="text-[10px] sm:text-[11px] text-textMuted/70 mt-1">PDF, PNG, JPG supported</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}