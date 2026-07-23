import React, { useState, useEffect } from 'react';
import { UploadScreen } from './components/UploadScreen';
import { ResultRenderer } from './components/ResultRenderer';
import { Loader2, FileText, CheckCircle2, Download, Database, AlertCircle, ArrowLeft, Sun, Moon } from 'lucide-react';

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
  const [uploadedFileUrls, setUploadedFileUrls] = useState([]);
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('app-theme') || 'dark';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('app-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  };

  // Server-Sent Events (SSE) stream listener for real-time GLM-OCR updates
  React.useEffect(() => {
    if (!glmJobId || appState !== 'results') return;

    const eventSource = new EventSource(`${API_BASE_URL}/glm-stream/${glmJobId}`);

    // Safety timeout: if GLM takes longer than 120s, force-stop spinners and set remaining fields to "unreadable"
    const timeoutTimer = setTimeout(() => {
      console.warn("GLM SSE processing timed out after 120s");
      eventSource.close();
      setGlmJobId(null);
      setExtractedData(prevData => {
        if (!prevData) return prevData;
        const newData = JSON.parse(JSON.stringify(prevData));
        const markTimeoutDone = (obj) => {
          if (Array.isArray(obj)) obj.forEach(markTimeoutDone);
          else if (obj && typeof obj === 'object') {
            if ('azure' in obj && 'glm' in obj) {
              if (obj.glm.status === 'processing') {
                obj.glm = { value: 'unreadable', confidence: null, status: 'completed' };
              }
            } else {
              for (const k in obj) markTimeoutDone(obj[k]);
            }
          }
        };
        markTimeoutDone(newData);
        return newData;
      });
    }, 120000);

    eventSource.onmessage = (event) => {
      try {
        const result = JSON.parse(event.data);

        if (result.status === 'completed') {
          clearTimeout(timeoutTimer);
          eventSource.close();
          setGlmJobId(null);

          // Update GLM column in extractedData with real GLM OCR data
          setExtractedData(prevData => {
            if (!prevData) return prevData;
            const newData = JSON.parse(JSON.stringify(prevData));
            const glmRaw = result.glm_data || {};

            const normalizeKey = (str) => {
              if (!str) return "";
              return String(str)
                .toLowerCase()
                .replace(/^section_\d+_/, "")
                .replace(/_/g, " ")
                .replace(/[^a-z0-9]/g, "");
            };

            const ALIASES = {
              "issue date": ["date_of_issue", "issue_date", "date of issue", "issuedate"],
              "expiry date": ["date_of_expiry", "expiry_date", "date of expiry", "expirydate"],
              "cnic number": ["identity_number", "cnic_number", "cnic", "cnic number", "identity number"],
              "father name": ["father_name", "father name", "fathername"],
              "date of birth": ["date_of_birth", "dob", "date of birth", "dateofbirth"],
              "telephone": ["telephone", "phone", "mobile", "contact_number", "mobile_number"],
            };

            const findGlmValue = (raw, targetKey) => {
              if (!raw || typeof raw !== 'object') return null;
              const targetNorm = normalizeKey(targetKey);

              const searchInObj = (obj) => {
                if (!obj || typeof obj !== 'object') return null;

                for (const [k, v] of Object.entries(obj)) {
                  const kNorm = normalizeKey(k);
                  if (kNorm === targetNorm) {
                    if (v !== null && v !== undefined && typeof v !== 'object') return v;
                  }

                  // Alias check
                  for (const [aliasCanonical, aliasVariants] of Object.entries(ALIASES)) {
                    if (targetNorm === normalizeKey(aliasCanonical)) {
                      if (aliasVariants.some(varStr => normalizeKey(varStr) === kNorm)) {
                        if (v !== null && v !== undefined && typeof v !== 'object') return v;
                      }
                    }
                  }

                  // Recursive search into child section objects
                  if (typeof v === 'object' && v !== null && !('azure' in v || 'value' in v)) {
                    const nested = searchInObj(v);
                    if (nested !== null) return nested;
                  }
                }
                return null;
              };

              return searchInObj(raw);
            };

            const updateGlmNodes = (obj, keyName = "") => {
              if (Array.isArray(obj)) {
                return obj.map(item => updateGlmNodes(item, keyName));
              } else if (obj && typeof obj === 'object') {
                if ('azure' in obj && 'glm' in obj) {
                  const val = findGlmValue(glmRaw, keyName);
                  obj.glm = {
                    value: (val !== null && val !== undefined && val !== "" && val !== "—") ? String(val).trim() : "unreadable",
                    confidence: null,
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

            return updateGlmNodes(newData);
          });
        } else if (result.status === 'error') {
          clearTimeout(timeoutTimer);
          eventSource.close();
          setGlmJobId(null);
          // Mark GLM nodes as completed with "unreadable"
          setExtractedData(prevData => {
            if (!prevData) return prevData;
            const newData = JSON.parse(JSON.stringify(prevData));
            const setError = (obj) => {
              if (Array.isArray(obj)) obj.forEach(setError);
              else if (obj && typeof obj === 'object') {
                if ('azure' in obj && 'glm' in obj) {
                  obj.glm = { value: 'unreadable', confidence: null, status: 'completed' };
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

    // EventSource error handler — do NOT kill socket on transient retries
    eventSource.onerror = (err) => {
      console.warn("SSE stream retrying or transient network event:", err);
      // Allow browser EventSource native auto-reconnect logic to retry while job processes
    };

    return () => {
      clearTimeout(timeoutTimer);
      eventSource.close();
    };
  }, [glmJobId, appState]);

  const handleFileUpload = async (files) => {
    if (!files || files.length === 0) return;

    // Generate local Object URLs for instant document preview
    const fileObjects = Array.from(files).map(file => ({
      name: file.name,
      url: URL.createObjectURL(file),
      type: file.type
    }));
    setUploadedFileUrls(fileObjects);

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
    <div className={`min-h-[100dvh] flex font-sans justify-center items-start bg-background ${isUploadOnly ? 'p-0' : 'p-0 md:p-6 lg:p-10'} transition-colors duration-300`}>
      <div className={`w-full flex flex-col lg:flex-row gap-4 md:gap-6 ${isUploadOnly ? 'h-[100dvh]' : 'w-full max-w-[99%] 2xl:max-w-[1720px]'}`}>
        
        {/* Render Upload Screen if not in results mode */}
        {appState !== 'results' && (
          <div className="w-full h-full flex flex-col items-center justify-center relative">
            {/* Top Right Floating Theme Toggle Button */}
            <div className="absolute top-6 right-6 z-20">
              <button
                onClick={toggleTheme}
                className="p-3 text-textMuted hover:text-textMain bg-surface/80 border border-outline/50 backdrop-blur-xl rounded-full shadow-lg transition-all focus-visible:ring-2 focus-visible:ring-primary cursor-pointer flex items-center justify-center gap-2"
                title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
                aria-label={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
              >
                {theme === 'dark' ? <Sun size={20} className="text-amber-400" /> : <Moon size={20} className="text-indigo-600" />}
              </button>
            </div>

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
          <div className="flex-1 flex flex-col h-[100vh] md:h-[calc(100vh-3rem)] lg:h-[calc(100vh-5rem)] bg-surface/95 backdrop-blur-xl rounded-none md:rounded-[2rem] shadow-2xl border-0 md:border border-outline/50 overflow-hidden animate-in slide-in-from-right-8 duration-500 w-full transition-colors">
            {/* Header */}
            <header className="px-10 py-6 border-b border-outline/50 flex items-center justify-between shrink-0 bg-surface z-10 relative">
              <div className="flex items-center gap-4">
                <button 
                  onClick={() => {
                    setAppState('upload');
                    setIsSaved(false);
                    setIsSaving(false);
                  }}
                  className="w-12 h-12 flex items-center justify-center text-textMuted hover:text-textMain hover:bg-outline/20 rounded-full transition-all focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none cursor-pointer"
                  title="Back to upload"
                  aria-label="Back to upload"
                >
                  <ArrowLeft size={24} />
                </button>
                <div>
                  <h1 className="font-display font-bold text-2xl tracking-tight text-textMain">Document Intelligence</h1>
                  <p className="text-sm text-textMuted font-medium tracking-wide uppercase mt-1">Extraction Complete</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={toggleTheme}
                  className="p-3 text-textMuted hover:text-textMain bg-surface border border-outline/50 rounded-xl shadow-sm transition-all focus-visible:ring-2 focus-visible:ring-primary cursor-pointer flex items-center justify-center"
                  title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
                  aria-label={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
                >
                  {theme === 'dark' ? <Sun size={20} className="text-amber-400" /> : <Moon size={20} className="text-indigo-600" />}
                </button>
                <button 
                  onClick={downloadJSON} 
                  className="p-3 text-textMuted hover:text-primary hover:bg-primary/10 border border-outline/50 rounded-xl transition-all focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none" 
                  title="Download JSON"
                  aria-label="Download JSON"
                >
                  <Download size={20} />
                </button>
                <button 
                  onClick={saveToDatabase} 
                  disabled={isSaving || isSaved} 
                  className={`px-6 py-3 text-white text-base font-semibold tracking-wide rounded-xl shadow-lg transition-all flex items-center gap-2 focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-surface focus-visible:ring-primary focus-visible:outline-none ${
                    isSaved 
                      ? 'bg-primary/80 cursor-not-allowed opacity-90' 
                      : isSaving 
                      ? 'bg-primary/50 cursor-wait' 
                      : 'bg-primary hover:bg-primary-hover hover:shadow-primary/20 hover:-translate-y-0.5'
                  }`}
                >
                  <CheckCircle2 size={20} /> 
                  {isSaved ? 'Saved to DB' : isSaving ? 'Saving…' : 'Confirm'}
                </button>
              </div>
            </header>

            {/* Dynamic Rendering Body */}
            <main className="flex-1 overflow-hidden p-0">
              <ResultRenderer data={extractedData} fileUrls={uploadedFileUrls} onUpdate={handleDataUpdate} />
            </main>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;
