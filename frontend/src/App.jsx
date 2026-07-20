import React, { useState, useRef } from 'react';
import { UploadScreen } from './components/UploadScreen';
import { ResultRenderer } from './components/ResultRenderer';
import { Loader2, FileText, CheckCircle2, Download, Database, AlertCircle, ArrowLeft } from 'lucide-react';

// Make sure your Flask backend is running on port 5000 and has CORS enabled.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

function App() {
  const [appState, setAppState] = useState('upload'); // 'upload', 'processing', 'results', 'error'
  const [progressMessage, setProgressMessage] = useState('');
  const [extractedData, setExtractedData] = useState(null);
  const [formType, setFormType] = useState('auto');
  const [errorMessage, setErrorMessage] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [glmJobId, setGlmJobId] = useState(null);

  // Server-Sent Events (SSE) stream listener for real-time GLM-OCR updates
  React.useEffect(() => {
    if (!glmJobId || appState !== 'results') return;

    const eventSource = new EventSource(`${API_BASE_URL}/glm-stream/${glmJobId}`);

    eventSource.onmessage = (event) => {
      try {
        const result = JSON.parse(event.data);

        if (result.status === 'completed') {
          eventSource.close();
          setGlmJobId(null);

          // Update GLM column in extractedData with real GLM OCR data
          setExtractedData(prevData => {
            if (!prevData) return prevData;
            const newData = JSON.parse(JSON.stringify(prevData));
            const glmRaw = result.glm_data || {};

            const updateGlmNodes = (obj, keyName = "") => {
              if (Array.isArray(obj)) {
                return obj.map(item => updateGlmNodes(item, keyName));
              } else if (obj && typeof obj === 'object') {
                if ('azure' in obj && 'glm' in obj) {
                  const val = glmRaw[keyName] || glmRaw[formatKey(keyName)] || null;
                  obj.glm = {
                    value: val !== null ? String(val) : "—",
                    confidence: val !== null ? 0.88 : 0.0,
                    status: 'completed'
                  };
                } else {
                  for (const k in obj) {
                    obj[k] = updateGlmNodes(obj[k], k);
                  }
                }
              }
              return obj;
            };

            const formatKey = (k) => k.replace(/_/g, " ").toLowerCase();
            return updateGlmNodes(newData);
          });
        } else if (result.status === 'error') {
          eventSource.close();
          setGlmJobId(null);
          // Mark GLM nodes as error
          setExtractedData(prevData => {
            if (!prevData) return prevData;
            const newData = JSON.parse(JSON.stringify(prevData));
            const setError = (obj) => {
              if (Array.isArray(obj)) obj.forEach(setError);
              else if (obj && typeof obj === 'object') {
                if ('azure' in obj && 'glm' in obj) {
                  obj.glm = { value: 'Error extracting', confidence: 0.0, status: 'error' };
                } else {
                  for (const k in obj) setError(obj[k]);
                }
              }
            };
            setError(newData);
            return newData;
          });
        }
      } catch (err) {
        console.error("Error parsing SSE event data:", err);
      }
    };

    eventSource.onerror = (err) => {
      console.error("SSE connection error:", err);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [glmJobId, appState]);

  const handleFileUpload = async (files) => {
    if (!files || files.length === 0) return;

    setAppState('processing');
    setProgressMessage('Uploading document...');
    setErrorMessage('');
    setGlmJobId(null);
    setIsSaving(false);
    setIsSaved(false);
    
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }

    try {
      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("HTTP error " + response.status);
      }

      // Handle the streaming NDJSON response
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const processStream = async () => {
        const { done, value } = await reader.read();
        if (done) return;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // Keep last incomplete line in buffer

        for (const line of lines) {
          if (line.trim()) {
            try {
              const res = JSON.parse(line);
              if (res.status === "progress") {
                setProgressMessage(res.message);
              } else if (res.status === "success") {
                if (res.classified_type) {
                  setFormType(res.classified_type);
                }
                if (res.glm_job_id) {
                  setGlmJobId(res.glm_job_id);
                }
                setExtractedData(res.data);
                setAppState('results');
              } else if (res.status === "error") {
                setErrorMessage(res.message || "Extraction failed");
                setAppState('error');
              }
            } catch (e) {
              console.error("Failed to parse stream line:", e);
            }
          }
        }
        await processStream();
      };

      await processStream();
    } catch (error) {
      console.error("Error during upload:", error);
      const detailMsg = error.message ? `: ${error.message}` : "";
      setErrorMessage(`Backend is not working or unreachable${detailMsg}. Please check if Flask app.py is running.`);
      setAppState('error');
    }
  };

  const handleDataUpdate = (path, value) => {
    // This updates the local React state when the user edits a field
    setExtractedData(prevData => {
      const newData = JSON.parse(JSON.stringify(prevData));
      
      let parts = path.split(/[\.\[\]]+/).filter(Boolean);
      let obj = newData;
      
      for (let i = 0; i < parts.length - 1; i++) {
        if (!obj[parts[i]]) obj[parts[i]] = {};
        obj = obj[parts[i]];
      }
      
      let lastPart = parts[parts.length - 1];
      if (!obj[lastPart]) obj[lastPart] = {};
      if (!obj[lastPart].corrected) obj[lastPart].corrected = {};
      
      if (obj[lastPart].azure && obj[lastPart].azure.options) {
        obj[lastPart].corrected.selected = value;
      } else {
        obj[lastPart].corrected.value = value;
      }

      return newData;
    });
  };

  const saveToDatabase = async () => {
    if (isSaving || isSaved || !extractedData) return;
    setIsSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/save-to-db/${formType}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(extractedData)
      });
      const result = await response.json();
      if (response.ok) {
        setIsSaved(true);
        alert(result.message || "Data saved successfully.");
      } else {
        alert(result.message || "Failed to save data.");
      }
    } catch (error) {
      alert("Error saving data: " + error.message);
    } finally {
      setIsSaving(false);
    }
  };

  const downloadJSON = async () => {
    if (!extractedData) return;
    try {
      const response = await fetch(`${API_BASE_URL}/download-json`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(extractedData)
      });
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `extracted_${formType}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      } else {
        alert("Failed to download JSON.");
      }
    } catch (error) {
      alert("Error downloading JSON.");
    }
  };

  const isUploadOnly = appState !== 'results';

  return (
    <div className={`min-h-[100dvh] flex font-sans justify-center items-start ${isUploadOnly ? 'bg-gradient-to-br from-slate-50 via-primary/15 to-primary/15' : 'bg-background p-0 md:p-4 lg:p-6'}`}>
      <div className={`w-full flex flex-col lg:flex-row gap-4 md:gap-6 ${isUploadOnly ? 'h-[100dvh]' : 'max-w-[95%]'}`}>
        
        {/* Render Upload Screen if not in results mode */}
        {appState !== 'results' && (
          <div className="w-full h-full flex flex-col">
            <UploadScreen 
              onUpload={handleFileUpload} 
              appState={appState}
              progressMessage={progressMessage}
              errorMessage={errorMessage}
              onReset={() => {
                setAppState('upload');
                setIsSaved(false);
                setIsSaving(false);
              }}
            />
          </div>
        )}

        {/* Results Screen */}
        {appState === 'results' && extractedData && (
          <div className="flex-1 flex flex-col h-[100vh] md:h-[calc(100vh-2rem)] lg:h-[calc(100vh-3rem)] bg-surface rounded-none md:rounded-3xl shadow-sm border-0 md:border border-outline overflow-hidden animate-in slide-in-from-right-4 duration-300 w-full">
            {/* Header */}
            <header className="px-6 py-4 border-b border-outline flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <button 
                  onClick={() => {
                    setAppState('upload');
                    setIsSaved(false);
                    setIsSaving(false);
                  }}
                  className="w-10 h-10 flex items-center justify-center text-black cursor-pointer"
                  title="Back to upload"
                >
                  <ArrowLeft/>
                </button>
              </div>
              <div className="flex items-center gap-3">
                <button onClick={downloadJSON} className="p-2 text-textMuted hover:text-textMain hover:bg-background rounded-lg transition-colors" title="Download JSON">
                  <Download size={20} />
                </button>
                <button 
                  onClick={saveToDatabase} 
                  disabled={isSaving || isSaved} 
                  className={`px-4 py-2 text-white text-sm font-medium rounded-lg shadow-sm transition-all flex items-center gap-2 ${
                    isSaved 
                      ? 'bg-emerald-600 cursor-not-allowed opacity-90' 
                      : isSaving 
                      ? 'bg-primary/70 cursor-wait' 
                      : 'bg-primary hover:bg-primary-hover'
                  }`}
                >
                  <CheckCircle2 size={16} /> 
                  {isSaved ? 'Saved to DB' : isSaving ? 'Saving...' : 'Confirm'}
                </button>
              </div>
            </header>

            {/* Dynamic Rendering Body */}
            <main className="flex-1 overflow-auto p-0">
              <ResultRenderer data={extractedData} onUpdate={handleDataUpdate} />
            </main>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;
