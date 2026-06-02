"use client";

import React, { useState, useRef, useEffect } from "react";

// List of OCR resolutions from the python backend config
const RESOLUTION_MODES = ["Default", "Quality", "Fast", "No Crop", "Small"];

// List of tasks and their associated prompt configurations
const TASKS = [
  "Markdown",
  "Free OCR",
  "OCR Image",
  "Parse Figure",
  "Locate",
  "Describe",
  "Custom"
];

// Helper details for example images
const EXAMPLES = [
  { path: "/next/examples/1.jpg", name: "Example 1 (Document)" },
  { path: "/next/examples/2.jpg", name: "Example 2 (Math/Layout)" },
  { path: "/next/examples/3.jpg", name: "Example 3 (Table/Structure)" }
];

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [mode, setMode] = useState<string>("Default");
  const [task, setTask] = useState<string>("Markdown");
  const [prompt, setPrompt] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Tab state
  const [activeTab, setActiveTab] = useState<string>("text");

  // Prediction Results
  const [results, setResults] = useState<{
    text: string;
    markdown: string;
    raw: string;
    imageUrl: string | null;
    crops: string[];
  } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropZoneRef = useRef<HTMLDivElement>(null);

  // Handle task selection changes to autofill defaults or show/hide inputs
  useEffect(() => {
    if (task === "Locate") {
      setPrompt("");
    } else if (task === "Custom") {
      setPrompt("");
    } else {
      setPrompt("");
    }
  }, [task]);

  // Clean up image preview URL when component unmounts
  useEffect(() => {
    return () => {
      if (preview && preview.startsWith("blob:")) {
        URL.revokeObjectURL(preview);
      }
    };
  }, [preview]);

  // Handle file drop
  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const selectedFile = e.dataTransfer.files[0];
      if (selectedFile.type.startsWith("image/")) {
        setFile(selectedFile);
        setPreview(URL.createObjectURL(selectedFile));
        setError(null);
      } else {
        setError("Invalid file type. Please select an image.");
      }
    }
  };

  // Clipboard paste support
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      if (e.clipboardData && e.clipboardData.files.length > 0) {
        const pastedFile = e.clipboardData.files[0];
        if (pastedFile.type.startsWith("image/")) {
          setFile(pastedFile);
          setPreview(URL.createObjectURL(pastedFile));
          setError(null);
          e.preventDefault();
        }
      }
    };

    window.addEventListener("paste", handlePaste);
    return () => {
      window.removeEventListener("paste", handlePaste);
    };
  }, []);

  // Handle file select from input
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setPreview(URL.createObjectURL(selectedFile));
      setError(null);
    }
  };

  // Trigger file dialog
  const triggerFileDialog = () => {
    fileInputRef.current?.click();
  };

  // Remove selected image
  const removeImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setFile(null);
    if (preview && preview.startsWith("blob:")) {
      URL.revokeObjectURL(preview);
    }
    setPreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Select an example image
  const selectExample = async (examplePath: string) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(examplePath);
      const blob = await response.blob();
      const filename = examplePath.split("/").pop() || "example.jpg";
      const exampleFile = new File([blob], filename, { type: "image/jpeg" });
      
      setFile(exampleFile);
      setPreview(examplePath); // Use direct path for static assets
      
      // Auto trigger prediction for examples to make UI fluid
      setLoading(false);
    } catch (e: any) {
      console.error(e);
      setError("Failed to load example image");
      setLoading(false);
    }
  };

  // Submit OCR request to the API
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please upload an image first.");
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("mode", mode);
    formData.append("task", task);
    formData.append("prompt", prompt);

    try {
      const res = await fetch("/next/api/ocr", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Failed to process OCR request");
      }

      setResults(data);
      
      // Auto switch tabs based on task type
      if (task === "Locate" && data.imageUrl) {
        setActiveTab("boxes");
      } else {
        setActiveTab("markdown");
      }
    } catch (e: any) {
      console.error(e);
      setError(e.message || "An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  };

  // Custom Inline & Line markdown compiler
  const compileMarkdown = (md: string): string => {
    if (!md) return "<p>No transcript generated</p>";
    
    const lines = md.split("\n");
    let html = "";
    let inList = false;
    let inCode = false;
    let inTable = false;
    let tableHeader = true;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Code blocks
      if (line.startsWith("```")) {
        if (inCode) {
          html += "</code></pre>";
          inCode = false;
        } else {
          html += "<pre><code>";
          inCode = true;
        }
        continue;
      }

      if (inCode) {
        html += line
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;") + "\n";
        continue;
      }

      // Tables
      if (line.startsWith("|")) {
        if (!inTable) {
          inTable = true;
          tableHeader = true;
          html += '<table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">';
        }
        
        // Separator line |---|---|
        if (line.match(/^\|[\s\-\|]+$/)) {
          continue;
        }

        const cells = line.split("|").slice(1, -1).map(c => c.trim());
        html += '<tr style="border-bottom: 1px solid var(--primary-border);">';
        for (const cell of cells) {
          const tag = tableHeader ? "th" : "td";
          const styles = tableHeader 
            ? 'style="background: var(--primary-light); font-weight: 600; padding: 8px 12px; border: 1px solid var(--primary-border); text-align: left;"'
            : 'style="padding: 8px 12px; border: 1px solid var(--primary-border); text-align: left;"';
          html += `<${tag} ${styles}>${inlineMarkdown(cell)}</${tag}>`;
        }
        html += "</tr>";
        tableHeader = false;
        continue;
      } else if (inTable) {
        html += "</table>";
        inTable = false;
      }

      // Lists
      if (line.startsWith("- ") || line.startsWith("* ")) {
        if (!inList) {
          inList = true;
          html += '<ul style="margin-left: 20px; margin-bottom: 16px; list-style-type: disc;">';
        }
        html += `<li style="margin-bottom: 4px;">${inlineMarkdown(line.substring(2))}</li>`;
        continue;
      } else {
        if (inList) {
          html += "</ul>";
          inList = false;
        }
      }

      // Blockquotes
      if (line.startsWith("> ")) {
        html += `<blockquote style="border-left: 4px solid var(--primary); padding-left: 16px; margin-bottom: 16px; color: var(--text-secondary); font-style: italic;">${inlineMarkdown(line.substring(2))}</blockquote>`;
        continue;
      }

      // Headers
      if (line.startsWith("#")) {
        const match = line.match(/^(#{1,6})\s+(.*)$/);
        if (match) {
          const level = match[1].length;
          const text = match[2];
          const fontSize = level === 1 ? "1.8rem" : level === 2 ? "1.5rem" : "1.25rem";
          const margin = level === 1 ? "24px 0 12px 0" : "18px 0 8px 0";
          html += `<h${level} style="font-size: ${fontSize}; font-weight: 700; margin: ${margin}; font-family: var(--font-sans);">${inlineMarkdown(text)}</h${level}>`;
          continue;
        }
      }

      // Blank line
      if (line.trim() === "") {
        continue;
      }

      // Paragraph
      html += `<p style="margin-bottom: 12px; line-height: 1.7;">${inlineMarkdown(line)}</p>`;
    }

    if (inList) html += "</ul>";
    if (inCode) html += "</code></pre>";
    if (inTable) html += "</table>";

    return html;
  };

  const inlineMarkdown = (text: string): string => {
    let res = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Bold
    res = res.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    
    // Italic
    res = res.replace(/\*(.*?)\*/g, "<em>$1</em>");

    // Inline images: ![alt](url)
    res = res.replace(/!\[(.*?)\]\((.*?)\)/g, (_, alt, url) => {
      const decodedUrl = url.replace(/&amp;/g, "&");
      return `<img src="${decodedUrl}" alt="${alt}" class="md-img" style="max-width:100%; border-radius: 8px; margin: 12px 0; border: 1px solid var(--primary-border); display: block;" />`;
    });

    // Inline links: [text](url)
    res = res.replace(/\[(.*?)\]\((.*?)\)/g, (_, label, url) => {
      const decodedUrl = url.replace(/&amp;/g, "&");
      return `<a href="${decodedUrl}" target="_blank" rel="noopener noreferrer" style="color:var(--primary); text-decoration:underline; font-weight:500;">${label}</a>`;
    });

    // Inline code: `code`
    res = res.replace(/`(.*?)`/g, '<code style="font-family:var(--font-mono); background:var(--primary-light); color:var(--primary); padding:2px 6px; border-radius:4px; font-size:0.9em;">$1</code>');

    return res;
  };

  const showPromptField = task === "Custom" || task === "Locate";

  return (
    <>
      {/* Decorative Blur Orbs */}
      <div className="glow-container">
        <div className="glow-orb orb-1"></div>
        <div className="glow-orb orb-2"></div>
      </div>

      <div className="main-wrapper">
        <header>
          <div className="brand-badge">
            <span className="pulse"></span>
            Next.js Engine
          </div>
          <h1>DeepSeek OCR 2</h1>
          <p>
            Experience high-fidelity document layout analysis, causal flow transcription, 
            and pixel-level grounding visualization in a modern Next.js workspace.
          </p>
        </header>

        <main className="dashboard-grid">
          {/* Left Panel: Upload & Parameters */}
          <div className="panel">
            <form onSubmit={handleSubmit} className="control-group">
              
              {/* File Upload Zone */}
              <div className="form-field">
                <label>Input Image</label>
                <div
                  ref={dropZoneRef}
                  onClick={triggerFileDialog}
                  onDragOver={(e) => { e.preventDefault(); dropZoneRef.current?.classList.add("upload-zone-active"); }}
                  onDragLeave={() => dropZoneRef.current?.classList.remove("upload-zone-active")}
                  onDrop={(e) => { dropZoneRef.current?.classList.remove("upload-zone-active"); handleDrop(e); }}
                  className="upload-zone"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleFileChange}
                    style={{ display: "none" }}
                  />
                  
                  {preview ? (
                    <div className="preview-container">
                      <img src={preview} alt="Upload Preview" className="preview-img" />
                      <div className="remove-btn" onClick={removeImage} title="Remove image">
                        &times;
                      </div>
                    </div>
                  ) : (
                    <>
                      <span className="upload-icon">📷</span>
                      <p className="upload-text">Upload or drag & drop image</p>
                      <p className="upload-subtext">Supports PNG, JPG, WEBP. Ctrl+V to paste.</p>
                    </>
                  )}
                </div>
              </div>

              {/* Resolution Dropdown */}
              <div className="form-field">
                <label htmlFor="mode-select">Resolution Mode</label>
                <select
                  id="mode-select"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                  className="select-input"
                >
                  {RESOLUTION_MODES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>

              {/* Task Selection */}
              <div className="form-field">
                <label htmlFor="task-select">Task Type</label>
                <select
                  id="task-select"
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  className="select-input"
                >
                  {TASKS.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              {/* Conditional Prompt Textarea */}
              {showPromptField && (
                <div className="form-field">
                  <label htmlFor="prompt-input">
                    {task === "Locate" ? "Text to Locate" : "Custom Prompt"}
                  </label>
                  <textarea
                    id="prompt-input"
                    rows={2}
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder={
                      task === "Locate"
                        ? "Enter target text keywords (e.g. 'total sum' or 'signatures')"
                        : "Enter a custom instruction. Include <|grounding|> to extract bounding coordinates."
                    }
                    className="text-input"
                    required
                  />
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading || !file}
                className="submit-btn"
              >
                {loading ? (
                  <>
                    <div className="spinner"></div>
                    Executing OCR Pipeline...
                  </>
                ) : (
                  <>
                    <span>🔍</span>
                    Perform OCR
                  </>
                )}
              </button>
            </form>

            {/* Example Images Section */}
            <div className="examples-section">
              <h4>Load Example Document</h4>
              <div className="examples-list">
                {EXAMPLES.map((ex, index) => (
                  <div
                    key={index}
                    onClick={() => selectExample(ex.path)}
                    className="example-item"
                    title={ex.name}
                  >
                    <img src={ex.path} alt={ex.name} />
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Panel: Output Tabs & Workspace */}
          <div className="panel" style={{ minHeight: "560px" }}>
            {error && (
              <div style={{
                background: "rgba(239, 68, 68, 0.15)",
                border: "1px solid #EF4444",
                color: "#F87171",
                padding: "16px",
                borderRadius: "10px",
                marginBottom: "20px",
                fontSize: "0.95rem"
              }}>
                <strong>Error: </strong> {error}
              </div>
            )}

            {!results && !loading ? (
              <div className="empty-state">
                <span className="empty-state-icon">📄</span>
                <h3>Ready for Document Analysis</h3>
                <p style={{ maxWidth: "400px", marginTop: "8px" }}>
                  Select or upload a document/image on the left side, configure your parameters, 
                  and click the run button to begin layout classification and text recognition.
                </p>
              </div>
            ) : loading ? (
              <div className="empty-state" style={{ borderStyle: "solid" }}>
                <div className="spinner" style={{ width: "40px", height: "40px", borderWidth: "4px", borderColor: "rgba(30,144,255,0.1)", borderTopColor: "var(--primary)", marginBottom: "20px" }}></div>
                <h3>Processing Model Inference</h3>
                <p style={{ maxWidth: "350px", marginTop: "8px" }}>
                  Running multimodal grounding and layout transcription in the background. 
                  This can take up to 20-30 seconds depending on the document density.
                </p>
              </div>
            ) : (
              results && (
                <>
                  {/* Tab Headers */}
                  <nav className="tabs-nav" aria-label="OCR output views">
                    <button
                      onClick={() => setActiveTab("markdown")}
                      className={`tab-trigger ${activeTab === "markdown" ? "tab-trigger-active" : ""}`}
                    >
                      Markdown Preview
                    </button>
                    <button
                      onClick={() => setActiveTab("text")}
                      className={`tab-trigger ${activeTab === "text" ? "tab-trigger-active" : ""}`}
                    >
                      Clean Text
                    </button>
                    <button
                      onClick={() => setActiveTab("boxes")}
                      className={`tab-trigger ${activeTab === "boxes" ? "tab-trigger-active" : ""}`}
                    >
                      Bounding Boxes
                    </button>
                    <button
                      onClick={() => setActiveTab("crops")}
                      className={`tab-trigger ${activeTab === "crops" ? "tab-trigger-active" : ""}`}
                    >
                      Cropped Items ({results.crops.length})
                    </button>
                    <button
                      onClick={() => setActiveTab("raw")}
                      className={`tab-trigger ${activeTab === "raw" ? "tab-trigger-active" : ""}`}
                    >
                      Raw Engine Output
                    </button>
                  </nav>

                  {/* Tab Panes */}
                  
                  {/* Markdown Tab */}
                  <div className={`output-pane ${activeTab === "markdown" ? "output-pane-active" : ""}`}>
                    <div 
                      className="markdown-preview"
                      dangerouslySetInnerHTML={{ __html: compileMarkdown(results.markdown) }}
                    />
                  </div>

                  {/* Clean Text Tab */}
                  <div className={`output-pane ${activeTab === "text" ? "output-pane-active" : ""}`}>
                    <textarea
                      readOnly
                      value={results.text}
                      className="text-area-output"
                      placeholder="Clean transcripted text will appear here."
                    />
                  </div>

                  {/* Bounding Boxes Tab */}
                  <div className={`output-pane ${activeTab === "boxes" ? "output-pane-active" : ""}`}>
                    {results.imageUrl ? (
                      <div className="boxes-image-container">
                        <img src={results.imageUrl} alt="OCR Bounding Boxes Visualizer" className="boxes-img" />
                      </div>
                    ) : (
                      <div className="empty-state" style={{ height: "400px" }}>
                        <span style={{ fontSize: "2.5rem" }}>🖼️</span>
                        <h4 style={{ marginTop: "12px" }}>No Bounding Boxes Extracted</h4>
                        <p style={{ maxWidth: "300px", fontSize: "0.85rem", marginTop: "4px" }}>
                          Bounding boxes are generated only when the task supports grounding (like OCR Image, Locate, or Markdown with grounding anchors).
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Cropped Items Tab */}
                  <div className={`output-pane ${activeTab === "crops" ? "output-pane-active" : ""}`}>
                    {results.crops.length > 0 ? (
                      <div className="crops-grid">
                        {results.crops.map((cropUrl, idx) => (
                          <div key={idx} className="crop-card" title={`Cropped segment ${idx + 1}`}>
                            <img src={cropUrl} alt={`Crop segment ${idx + 1}`} />
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="empty-state" style={{ height: "400px" }}>
                        <span style={{ fontSize: "2.5rem" }}>✂️</span>
                        <h4 style={{ marginTop: "12px" }}>No Cropped Elements Found</h4>
                        <p style={{ maxWidth: "300px", fontSize: "0.85rem", marginTop: "4px" }}>
                          Cropped document figures or table elements will display here when detected and segmentized by the layout models.
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Raw Output Tab */}
                  <div className={`output-pane ${activeTab === "raw" ? "output-pane-active" : ""}`}>
                    <textarea
                      readOnly
                      value={results.raw}
                      className="text-area-output"
                      placeholder="Raw engine coordinates will appear here."
                    />
                  </div>
                </>
              )
            )}
          </div>
        </main>

        <footer style={{ textAlign: "center", marginTop: "60px", color: "var(--text-secondary)", fontSize: "0.85rem", fontFamily: "var(--font-mono)" }}>
          Powered by deepseek-ai/DeepSeek-OCR-2 • Next.js v15 Workspace
        </footer>
      </div>
    </>
  );
}
