import React, { useState, useEffect, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

function App() {
  const [backendOnline, setBackendOnline] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState({
    total_documents: 0,
    total_indexed_documents: 0,
    total_pages: 0,
    total_chunks: 0,
    total_indexed_vectors: 0,
    ready: false,
  });
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatusMsg, setUploadStatusMsg] = useState('');
  const [isDragActive, setIsDragActive] = useState(false);

  // Document exploration state (Step 2 & Final Sprint Knowledge Explorer)
  const [currentView, setCurrentView] = useState('dashboard'); // 'dashboard' | 'explorer'
  const [explorerDoc, setExplorerDoc] = useState(null);
  const [explorerStructure, setExplorerStructure] = useState(null);
  const [explorerChunks, setExplorerChunks] = useState([]);
  const [explorerKnowledge, setExplorerKnowledge] = useState(null);
  const [isExplorerLoading, setIsExplorerLoading] = useState(false);
  const [selectedSectionIndex, setSelectedSectionIndex] = useState(0);
  const [docSearchQuery, setDocSearchQuery] = useState('');
  const [docSearchResults, setDocSearchResults] = useState([]);
  const [isSearchingDoc, setIsSearchingDoc] = useState(false);
  const [showTechnicalChunks, setShowTechnicalChunks] = useState(false);

  // Chat state
  const [question, setQuestion] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const [loadingStep, setLoadingStep] = useState('');
  const [messages, setMessages] = useState([]);
  const [errorMessage, setErrorMessage] = useState('');

  const fileInputRef = useRef(null);
  const chatBottomRef = useRef(null);

  // Check health, fetch documents, and fetch stats on mount
  useEffect(() => {
    fetchAllData();
    const interval = setInterval(() => {
      checkHealth();
      fetchStats();
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isAsking]);

  const checkHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        setBackendOnline(true);
      } else {
        setBackendOnline(false);
      }
    } catch {
      setBackendOnline(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/documents/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.warn('Could not fetch stats:', err);
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE}/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (err) {
      console.warn('Could not fetch documents:', err);
    }
  };

  const fetchAllData = async () => {
    await Promise.all([checkHealth(), fetchDocuments(), fetchStats()]);
  };

  // Upload and process PDF
  const handleFileUpload = async (file) => {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setErrorMessage('Only .pdf files are accepted. Please select a valid PDF.');
      return;
    }

    setErrorMessage('');
    setIsUploading(true);
    setUploadStatusMsg(`Uploading & extracting "${file.name}"...`);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Upload failed');
      }

      if (data.status === 'already_exists') {
        setUploadStatusMsg(`Document already exists in your library: "${data.display_title || data.filename}"`);
      } else {
        setUploadStatusMsg(`Indexed ${data.display_title || data.filename} (${data.pages} pages, ${data.chunks} chunks)`);
      }
      await fetchAllData();
      setTimeout(() => setUploadStatusMsg(''), 4500);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to upload document');
      setUploadStatusMsg('');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  // Open Document Exploration (Complete Knowledge Explorer)
  const handleExplore = async (doc) => {
    setExplorerDoc(doc);
    setCurrentView('explorer');
    setIsExplorerLoading(true);
    setExplorerStructure(null);
    setExplorerChunks([]);
    setExplorerKnowledge(null);
    setDocSearchQuery('');
    setDocSearchResults([]);
    setShowTechnicalChunks(false);
    setSelectedSectionIndex(0);

    try {
      const [structRes, docRes, knowRes] = await Promise.all([
        fetch(`${API_BASE}/documents/${doc.document_id}/structure`),
        fetch(`${API_BASE}/documents/${doc.document_id}`),
        fetch(`${API_BASE}/documents/${doc.document_id}/knowledge`),
      ]);

      if (structRes.ok) {
        const structData = await structRes.json();
        setExplorerStructure(structData);
      } else {
        setExplorerStructure({
          document_id: doc.document_id,
          filename: doc.filename,
          total_pages: doc.pages,
          has_structure: false,
          sections: [],
        });
      }

      if (docRes.ok) {
        const docData = await docRes.json();
        setExplorerChunks(docData.chunks || []);
      }

      if (knowRes.ok) {
        const knowData = await knowRes.json();
        setExplorerKnowledge(knowData);
      }
    } catch (err) {
      console.warn('Failed to load document explorer data:', err);
    } finally {
      setIsExplorerLoading(false);
    }
  };

  const handleBackToKnowledge = () => {
    setCurrentView('dashboard');
  };

  const handlePrevSection = () => {
    if (selectedSectionIndex > 0) {
      setSelectedSectionIndex((prev) => prev - 1);
    }
  };

  const handleNextSection = () => {
    const total = explorerStructure?.sections?.length || 0;
    if (selectedSectionIndex < total - 1) {
      setSelectedSectionIndex((prev) => prev + 1);
    }
  };

  const handleDocSearch = async (e) => {
    if (e) e.preventDefault();
    const q = docSearchQuery.trim();
    if (!q || !explorerDoc) return;
    setIsSearchingDoc(true);
    try {
      const res = await fetch(`${API_BASE}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: q,
          document_id: explorerDoc.document_id,
          top_k: 4,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setDocSearchResults(data.results || []);
      }
    } catch (err) {
      console.warn('Document search error:', err);
    } finally {
      setIsSearchingDoc(false);
    }
  };

  const handleAskSuggested = (qText) => {
    setCurrentView('dashboard');
    handleAsk(qText);
  };

  const handleExportJSON = () => {
    if (!explorerKnowledge && !explorerDoc) return;
    const payload = explorerKnowledge || {
      document_id: explorerDoc.document_id,
      filename: explorerDoc.filename,
      overview: 'Document overview is not generated yet.',
      categories: [],
      key_information: [],
      suggested_questions: [],
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(explorerDoc?.filename || 'knowledge').replace(/\.[^/.]+$/, '')}_knowledge.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportMarkdown = async () => {
    if (!explorerDoc) return;
    try {
      const res = await fetch(`${API_BASE}/documents/${explorerDoc.document_id}/knowledge/export/markdown`);
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob([data.markdown], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${(explorerDoc?.filename || 'knowledge').replace(/\.[^/.]+$/, '')}_knowledge.md`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.warn('Failed to export markdown:', err);
    }
  };

  // Send question to RAG /chat
  const handleAsk = async (queryText) => {
    const q = (queryText || question).trim();
    if (!q) return;

    setErrorMessage('');
    setQuestion('');
    setIsAsking(true);
    setLoadingStep('Searching your documents in FAISS index...');

    const timer = setTimeout(() => {
      setLoadingStep('Gemma 4 is generating a grounded answer...');
    }, 900);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to get answer');
      }

      setMessages((prev) => [
        ...prev,
        {
          question: q,
          answer: data.answer,
          sources: data.sources || [],
        },
      ]);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to communicate with chat service');
    } finally {
      clearTimeout(timer);
      setIsAsking(false);
      setLoadingStep('');
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    handleAsk(question);
  };

  // Computed real statistics (falling back to array aggregates if /stats is loading)
  const totalDocsCount = stats.total_documents || documents.length;
  const totalPagesCount =
    stats.total_pages ||
    documents.reduce((acc, d) => acc + (d.pages || 0), 0);
  const totalChunksCount =
    stats.total_chunks ||
    documents.reduce((acc, d) => acc + (d.chunks || d.chunks_count || 0), 0);
  const isSystemReady =
    backendOnline && (stats.ready || documents.length > 0);

  const formatFileSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-brand">
          <div className="header-title-row">
            <div className="logo-badge">📄</div>
            <h1 className="header-title">LocalAI</h1>
          </div>
          <p className="header-subtitle">Private local-first document intelligence and knowledge base.</p>
        </div>

        <div className="header-actions">
          <button
            className="btn-icon"
            onClick={fetchAllData}
            title="Refresh local documents and statistics"
          >
            <span>🔄</span> Refresh
          </button>
          <div className={`status-pill ${backendOnline ? '' : 'offline'}`}>
            <span className="status-dot"></span>
            <span>{backendOnline ? '● Local AI' : '● Backend Offline'}</span>
          </div>
        </div>
      </header>

      {/* Dismissible Error Banner */}
      {errorMessage && (
        <div className="alert alert-error" style={{ marginBottom: '1.25rem' }}>
          <span>⚠️ {errorMessage}</span>
          <button className="alert-close" onClick={() => setErrorMessage('')} title="Dismiss">✕</button>
        </div>
      )}

      {/* DASHBOARD VIEW */}
      {currentView === 'dashboard' && (
        <>
          {/* TOP STATISTICS CARDS */}
          <section className="top-stats-row">
        <div className="stat-card">
          <span className="stat-card-label">Documents</span>
          <span className="stat-card-value">{totalDocsCount}</span>
          <span className="stat-card-subtext">
            {stats.total_indexed_documents || totalDocsCount} indexed in FAISS
          </span>
        </div>

        <div className="stat-card">
          <span className="stat-card-label">Pages</span>
          <span className="stat-card-value">{totalPagesCount}</span>
          <span className="stat-card-subtext">Covered across all PDFs</span>
        </div>

        <div className="stat-card">
          <span className="stat-card-label">Chunks</span>
          <span className="stat-card-value">{totalChunksCount}</span>
          <span className="stat-card-subtext">
            {stats.total_indexed_vectors ? `${stats.total_indexed_vectors} vectors` : 'Normalized embeddings'}
          </span>
        </div>

        <div className="stat-card">
          <span className="stat-card-label">Status</span>
          <span className="stat-card-value" style={{ fontSize: '1.45rem', textTransform: 'uppercase' }}>
            {isSystemReady ? (
              <span className="stat-ready-badge">✓ READY</span>
            ) : backendOnline ? (
              'STANDBY'
            ) : (
              <span className="stat-offline-badge">OFFLINE</span>
            )}
          </span>
          <span className="stat-card-subtext">
            {isSystemReady ? 'RAG pipeline active' : backendOnline ? 'Awaiting documents' : 'Start backend server'}
          </span>
        </div>
      </section>

      {/* Main Two-Column Layout */}
      <main className="main-grid">
        {/* Left Column: Knowledge Overview & Documents */}
        <section className="panel">
          <div className="panel-header">
            <h2 className="panel-title">📚 Knowledge Overview</h2>
            <span className="badge badge-muted">{documents.length} loaded</span>
          </div>

          <div className="panel-body">
            {/* LOCAL KNOWLEDGE HERO BANNER */}
            <div className="knowledge-banner">
              <h3 className="knowledge-banner-title">
                <span>⚡</span> LOCAL KNOWLEDGE
              </h3>
              <p className="knowledge-banner-desc">
                Your documents have been processed into a searchable local knowledge base.
              </p>
              <div className="knowledge-banner-stats">
                <div className="kb-stat-item">
                  <span className="kb-stat-name">Documents</span>
                  <span className="kb-stat-num">{totalDocsCount}</span>
                </div>
                <div className="kb-stat-item">
                  <span className="kb-stat-name">Pages</span>
                  <span className="kb-stat-num">{totalPagesCount}</span>
                </div>
                <div className="kb-stat-item">
                  <span className="kb-stat-name">Knowledge Chunks</span>
                  <span className="kb-stat-num">{totalChunksCount}</span>
                </div>
              </div>
            </div>

            {/* KNOWLEDGE BASE STATUS CHECKLIST */}
            <div className="checklist-card">
              <span className="checklist-title">Knowledge Base Status</span>
              <div className="checklist-item">
                <span className="checklist-check">✓</span>
                <span>Documents stored locally</span>
              </div>
              <div className="checklist-item">
                <span className="checklist-check">✓</span>
                <span>Text extracted</span>
              </div>
              <div className="checklist-item">
                <span className="checklist-check">✓</span>
                <span>Knowledge chunks created</span>
              </div>
              <div className="checklist-item">
                <span className="checklist-check">✓</span>
                <span>Embeddings indexed</span>
              </div>
              <div className="checklist-item">
                <span className="checklist-check">✓</span>
                <span>Ready for AI questions</span>
              </div>
            </div>

            {/* Upload Area */}
            <div
              className={`dropzone ${isDragActive ? 'active' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setIsDragActive(true); }}
              onDragLeave={() => setIsDragActive(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="dropzone-icon">📥</div>
              <p className="dropzone-text">
                {isUploading ? 'Processing & Indexing Document...' : 'Drop a PDF here or click to upload'}
              </p>
              <span className="dropzone-hint">Supported: .pdf (Max 25MB)</span>

              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                style={{ display: 'none' }}
                onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
              />
            </div>

            <button
              className="btn btn-primary"
              style={{ width: '100%' }}
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              {isUploading ? 'Processing Document...' : 'Upload PDF'}
            </button>

            {uploadStatusMsg && (
              <div className="loading-box" style={{ padding: '0.65rem 0.85rem' }}>
                {isUploading && <div className="spinner"></div>}
                <span className="loading-text" style={{ fontSize: '0.825rem' }}>{uploadStatusMsg}</span>
              </div>
            )}

            {/* KNOWLEDGE LIBRARY */}
            <div className="kb-library-section" style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', marginTop: '0.75rem' }}>
              <div className="kb-library-header" style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.65rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                  <h3 style={{ margin: 0, fontSize: '0.825rem', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--accent-primary, #6366f1)' }}>
                    YOUR LOCAL KNOWLEDGE
                  </h3>
                  <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)' }}>
                    {documents.length} unique {documents.length === 1 ? 'document' : 'documents'}
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: '0.785rem', color: 'var(--text-secondary)' }}>
                  Documents stored and indexed locally
                </p>
              </div>

              {documents.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem 1rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📭</div>
                  <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                    Your local knowledge base is empty.
                  </div>
                  <div style={{ fontSize: '0.825rem', color: 'var(--text-muted)', lineHeight: '1.6', maxWidth: '300px', margin: '0 auto 1rem' }}>
                    1. Upload a PDF<br />
                    2. Process &amp; index it<br />
                    3. Your document knowledge will appear here
                  </div>
                  <button
                    className="btn btn-secondary"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Upload Document
                  </button>
                </div>
              ) : (
                documents.map((doc) => {
                  const displayTitle = doc.display_title || doc.filename;
                  const isIndexed = doc.indexing_status === 'indexed';
                  const isError = doc.indexing_status === 'failed' || doc.status === 'error';
                  const isProcessing = doc.indexing_status === 'pending' || doc.status === 'pending';

                  let statusBadge = <span className="badge badge-success">✓ Indexed</span>;
                  if (isError) {
                    statusBadge = <span className="badge badge-error">✕ Error</span>;
                  } else if (isProcessing) {
                    statusBadge = <span className="badge badge-muted">⏳ Processing</span>;
                  } else if (!isIndexed) {
                    statusBadge = <span className="badge badge-warning">⚠ Needs Indexing</span>;
                  }

                  const chunkCount = doc.chunks || doc.chunks_count || 0;
                  const pageLabel = `${doc.pages || 1} ${doc.pages === 1 ? 'page' : 'pages'}`;
                  const chunkLabel = `${chunkCount} ${chunkCount === 1 ? 'chunk' : 'chunks'}`;

                  return (
                    <div key={doc.document_id} className="doc-card" style={{ padding: '0.95rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}>
                      <div className="doc-card-header" style={{ alignItems: 'flex-start' }}>
                        <span className="doc-icon" style={{ fontSize: '1.35rem', marginTop: '0.1rem' }}>📄</span>
                        <div className="doc-info" style={{ flex: 1, minWidth: 0 }}>
                          <div className="doc-name" title={displayTitle} style={{ fontSize: '0.95rem', fontWeight: '700', color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
                            {displayTitle}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                            Original: <span style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>{doc.filename}</span>
                          </div>
                          <div style={{ fontSize: '0.785rem', color: 'var(--text-secondary)', marginTop: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span>{pageLabel} &bull; {chunkLabel}</span>
                            {doc.duplicate_count > 1 && (
                              <span
                                className="badge"
                                style={{ fontSize: '0.675rem', padding: '0.1rem 0.4rem', background: 'rgba(99, 102, 241, 0.12)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.25)' }}
                                title={`${doc.duplicate_count} identical uploads consolidated into this unique document`}
                              >
                                🔄 {doc.duplicate_count} identical uploads
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.85rem', paddingTop: '0.65rem', borderTop: '1px solid var(--border-subtle)' }}>
                        <div>{statusBadge}</div>
                        <button
                          className="btn-explore"
                          onClick={() => handleExplore(doc)}
                          title={`Explore ${displayTitle}`}
                        >
                          Explore &rarr;
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </section>

        {/* Right Column: Chat Panel (Preserved 100% Intact) */}
        <section className="panel">
          <div className="panel-header">
            <h2 className="panel-title">💬 Ask your documents</h2>
            {documents.length > 0 && (
              <span className="badge badge-muted">Gemma 4 E2B Active</span>
            )}
          </div>

          <div className="panel-body">
            {/* Chat Messages */}
            <div className="chat-container">
              {messages.length === 0 && !isAsking ? (
                <div className="chat-empty">
                  <div className="chat-empty-icon">💡</div>
                  <div className="chat-empty-title">Ask a question about your uploaded documents.</div>
                  <div className="chat-empty-desc">
                    Answers are strictly grounded in your local documents using FAISS vector search and local Gemma 4.
                  </div>

                  {/* Suggestion Chips */}
                  <div className="suggestion-chips">
                    <button
                      className="chip"
                      onClick={() => handleAsk('What is the minimum attendance requirement for students?')}
                    >
                      👉 "What is the minimum attendance requirement for students?"
                    </button>
                    <button
                      className="chip"
                      onClick={() => handleAsk('How are grades and CGPA calculated?')}
                    >
                      👉 "How are grades and CGPA calculated?"
                    </button>
                    <button
                      className="chip"
                      onClick={() => handleAsk('What is the policy for flying commercial drones in the campus football stadium?')}
                    >
                      👉 "What is the policy for flying commercial drones in the campus football stadium?" (Test refusal)
                    </button>
                  </div>
                </div>
              ) : (
                messages.map((item, idx) => (
                  <div key={idx} className="qa-card">
                    {/* User Question */}
                    <div className="qa-question-row">
                      <span className="qa-role-badge">Question</span>
                      <span className="qa-question-text">{item.question}</span>
                    </div>

                    {/* Answer Display */}
                    <div className="qa-answer-block">
                      <span className="qa-answer-label">Answer</span>
                      <div className="qa-answer-text">{item.answer}</div>
                    </div>

                    {/* Grounded Citations / Sources */}
                    {item.sources && item.sources.length > 0 && (
                      <div className="qa-sources-section">
                        <div className="qa-sources-title">Sources</div>
                        <div className="sources-list">
                          {item.sources.map((src, sIdx) => (
                            <div key={sIdx} className="source-item">
                              <span>📄 {src.document}</span>
                              <span className="page-badge">Page {src.page}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}

              {/* In-flight Loading Indicator */}
              {isAsking && (
                <div className="loading-box">
                  <div className="spinner"></div>
                  <span className="loading-text">{loadingStep || 'Searching your documents...'}</span>
                </div>
              )}

              <div ref={chatBottomRef} />
            </div>

            {/* Chat Input Bar */}
            <form onSubmit={handleSubmit} className="chat-input-wrapper">
              <input
                type="text"
                className="chat-input"
                placeholder="What is the minimum attendance requirement?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={isAsking}
              />
              <button
                type="submit"
                className="btn btn-primary"
                disabled={isAsking || !question.trim()}
              >
                {isAsking ? 'Thinking...' : 'Ask'}
              </button>
            </form>
          </div>
        </section>
      </main>
        </>
      )}

      {/* VIEW CONDITIONAL: DASHBOARD vs COMPLETE KNOWLEDGE EXPLORER */}
      {currentView === 'explorer' && explorerDoc ? (
        <div className="explorer-view">
          {/* Navigation & Action Bar */}
          <div className="explorer-nav-bar">
            <button className="btn-back" onClick={handleBackToKnowledge}>
              ← Back to Knowledge
            </button>

            <div className="export-btn-group">
              <button
                className="btn-export"
                onClick={handleExportJSON}
                title="Download verified knowledge structure as JSON"
              >
                <span>💾</span> Export JSON
              </button>
              <button
                className="btn-export"
                onClick={handleExportMarkdown}
                title="Download formatted knowledge report as Markdown"
              >
                <span>📄</span> Export Markdown
              </button>
            </div>
          </div>

          {/* Document Header Card */}
          <div className="explorer-header-card">
            <div className="explorer-doc-title-row">
              <span className="explorer-doc-icon">📄</span>
              <div>
                <h2 className="explorer-doc-title">
                  {explorerDoc.display_title || explorerKnowledge?.filename || explorerStructure?.filename || explorerDoc.filename}
                </h2>
                <div className="explorer-doc-sub" style={{ marginTop: '0.2rem' }}>
                  Original file: <span style={{ fontFamily: 'monospace' }}>{explorerDoc.filename}</span> &bull; {formatFileSize(explorerDoc.file_size_bytes)}
                </div>
              </div>
            </div>

            <div className="explorer-badges">
              {explorerDoc.duplicate_count > 1 && (
                <span className="explorer-badge" style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', borderColor: 'rgba(99, 102, 241, 0.3)' }}>
                  🔄 {explorerDoc.duplicate_count} identical uploads consolidated
                </span>
              )}
              <span className="explorer-badge">
                {explorerKnowledge?.total_pages || explorerStructure?.total_pages || explorerDoc.pages} Pages
              </span>
              <span className="explorer-badge">
                {explorerDoc.chunks || explorerDoc.chunks_count || explorerChunks.length} Chunks
              </span>
              <span className="explorer-badge success">
                ✓ Indexed
              </span>
            </div>
          </div>

          {/* DOCUMENT OVERVIEW */}
          <div className="overview-card">
            <div className="overview-card-title">
              <span>📋</span> DOCUMENT OVERVIEW
            </div>
            <p className="overview-card-text">
              {explorerKnowledge?.overview ? (
                explorerKnowledge.overview
              ) : isExplorerLoading ? (
                'Analyzing grounded overview...'
              ) : (
                'Document overview is not generated yet.'
              )}
            </p>
          </div>

          {/* Main Knowledge Explorer Grid */}
          <div className="explorer-grid">
            {/* Left Column: STRUCTURE & KNOWLEDGE CATEGORIES */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* DOCUMENT STRUCTURE */}
              <section className="explorer-panel">
                <div className="explorer-panel-header">
                  <h3 className="explorer-panel-title">
                    <span>📑</span> DOCUMENT STRUCTURE
                  </h3>
                  <span className="badge badge-muted">
                    {explorerStructure?.sections ? `${explorerStructure.sections.length} sections` : '0 sections'}
                  </span>
                </div>

                <div className="explorer-panel-body" style={{ maxHeight: '340px' }}>
                  {isExplorerLoading ? (
                    <div className="loading-box" style={{ padding: '2rem 1rem' }}>
                      <div className="spinner"></div>
                      <span className="loading-text">Detecting structure...</span>
                    </div>
                  ) : !explorerStructure || !explorerStructure.sections || explorerStructure.sections.length === 0 ? (
                    <div className="no-structure-box">
                      <span className="no-structure-icon">📋</span>
                      <h4 className="no-structure-title">No structured sections detected</h4>
                      <p className="no-structure-desc">
                        No explicit chapter headings were detected in this document.
                      </p>
                    </div>
                  ) : (
                    <div className="section-nav-list">
                      {explorerStructure.sections.map((section, idx) => {
                        const isActive = selectedSectionIndex === idx;
                        const pageLabel = section.start_page === section.end_page
                          ? `Page ${section.start_page}`
                          : `Pages ${section.start_page}–${section.end_page}`;

                        return (
                          <button
                            key={section.section_id || idx}
                            className={`section-item-btn ${isActive ? 'active' : ''}`}
                            onClick={() => setSelectedSectionIndex(idx)}
                          >
                            <span className="section-num">
                              {String(idx + 1).padStart(2, '0')}
                            </span>
                            <div className="section-item-info">
                              <span className="section-item-title">{section.title}</span>
                              <div className="section-item-pages">
                                <span>{pageLabel}</span>
                              </div>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              </section>

              {/* KNOWLEDGE CATEGORIES */}
              <section className="explorer-panel">
                <div className="explorer-panel-header">
                  <h3 className="explorer-panel-title">
                    <span>🏷️</span> KNOWLEDGE CATEGORIES
                  </h3>
                  <span className="badge badge-muted">
                    {explorerKnowledge?.categories ? `${explorerKnowledge.categories.length} active` : '0 categories'}
                  </span>
                </div>

                <div className="explorer-panel-body">
                  {!explorerKnowledge || explorerKnowledge.categories.length === 0 ? (
                    <div style={{ padding: '1.25rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      No categories found in this document.
                    </div>
                  ) : (
                    <div className="category-grid">
                      {explorerKnowledge.categories.map((cat) => (
                        <div key={cat.category_id} className="category-card">
                          <div className="category-card-header">
                            <span className="category-card-icon">{cat.icon}</span>
                            <span className="category-card-name">{cat.name}</span>
                          </div>
                          <div className="category-topics-list">
                            {cat.topics.slice(0, 3).map((topic, tIdx) => (
                              <div key={tIdx} className="category-topic-item">
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={topic.name}>
                                  &bull; {topic.name}
                                </span>
                                <span style={{ flexShrink: 0, opacity: 0.8 }}>
                                  p.{topic.start_page}
                                </span>
                              </div>
                            ))}
                            {cat.topics.length > 3 && (
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                +{cat.topics.length - 3} more topics
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            </div>

            {/* Right Column: SEARCH, KEY INFO, QUESTIONS, & ACTIVE SECTION */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* DOCUMENT SEARCH / EXPLORE */}
              <div className="doc-search-panel">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>
                    🔍 SEARCH THIS DOCUMENT
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Vector search in {explorerDoc.filename}
                  </span>
                </div>

                <form onSubmit={handleDocSearch} className="doc-search-input-row">
                  <input
                    type="text"
                    className="doc-search-input"
                    placeholder="e.g. minimum attendance, passing grade, library rules..."
                    value={docSearchQuery}
                    onChange={(e) => setDocSearchQuery(e.target.value)}
                  />
                  <button
                    type="submit"
                    className="btn btn-secondary"
                    disabled={isSearchingDoc || !docSearchQuery.trim()}
                    style={{ padding: '0.55rem 1rem' }}
                  >
                    {isSearchingDoc ? 'Searching...' : 'Search'}
                  </button>
                </form>

                {docSearchResults.length > 0 && (
                  <div className="doc-search-results">
                    {docSearchResults.map((res, rIdx) => (
                      <div key={rIdx} className="doc-search-item">
                        <div className="doc-search-item-header">
                          <span>📄 Page {res.page}</span>
                          <span className="doc-search-score-badge">
                            Score: {(res.score * 100).toFixed(0)}% relevant
                          </span>
                        </div>
                        <div className="doc-search-item-text">
                          {res.text.slice(0, 220)}...
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* KEY INFORMATION */}
              {explorerKnowledge && explorerKnowledge.key_information && explorerKnowledge.key_information.length > 0 && (
                <section className="explorer-panel">
                  <div className="explorer-panel-header">
                    <h3 className="explorer-panel-title">
                      <span>💡</span> KEY INFORMATION
                    </h3>
                    <span className="badge badge-muted">
                      {explorerKnowledge.key_information.length} extracted facts
                    </span>
                  </div>

                  <div className="explorer-panel-body">
                    <div className="key-info-grid">
                      {explorerKnowledge.key_information.map((fact, fIdx) => (
                        <div key={fIdx} className="key-info-card">
                          <span className="key-info-title">{fact.title}</span>
                          <span className="key-info-value">{fact.value}</span>
                          <span className="key-info-source">
                            <span>📄</span> {fact.source_document || explorerDoc.filename} &bull; Page {fact.source_page}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              )}

              {/* QUESTIONS YOU CAN ASK */}
              {explorerKnowledge && explorerKnowledge.suggested_questions && explorerKnowledge.suggested_questions.length > 0 && (
                <section className="explorer-panel">
                  <div className="explorer-panel-header">
                    <h3 className="explorer-panel-title">
                      <span>❓</span> QUESTIONS YOU CAN ASK
                    </h3>
                    <span className="badge badge-muted">Click to query Gemma 4</span>
                  </div>

                  <div className="explorer-panel-body">
                    <div className="suggested-questions-grid">
                      {explorerKnowledge.suggested_questions.map((qItem, qIdx) => (
                        <button
                          key={qIdx}
                          className="suggested-question-btn"
                          onClick={() => handleAskSuggested(qItem.question)}
                          title="Ask this question in RAG chat"
                        >
                          <span>💬 "{qItem.question}"</span>
                          <span className="question-cat-tag">{qItem.category}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </section>
              )}

              {/* ACTIVE SECTION DETAILS */}
              {explorerStructure?.sections && explorerStructure.sections.length > 0 && (
                <section className="explorer-panel">
                  <div className="explorer-panel-header">
                    <h3 className="explorer-panel-title">
                      <span>📖</span> SECTION CONTENT
                    </h3>
                    <span className="badge badge-muted">
                      Section {selectedSectionIndex + 1} of {explorerStructure.sections.length}
                    </span>
                  </div>

                  <div className="explorer-panel-body">
                    {(() => {
                      const activeSection = explorerStructure.sections[selectedSectionIndex] || explorerStructure.sections[0];
                      const sectionChunks = explorerChunks.filter(
                        (c) => c.page >= activeSection.start_page && c.page <= activeSection.end_page
                      );
                      const pageLabel = activeSection.start_page === activeSection.end_page
                        ? `Page ${activeSection.start_page}`
                        : `Pages ${activeSection.start_page}–${activeSection.end_page}`;

                      return (
                        <div className="section-detail-pane">
                          <div className="section-nav-controls">
                            <button
                              className="btn-nav-step"
                              onClick={handlePrevSection}
                              disabled={selectedSectionIndex <= 0}
                            >
                              ← Previous Section
                            </button>
                            <span className="section-nav-counter">
                              Section {selectedSectionIndex + 1} of {explorerStructure.sections.length}
                            </span>
                            <button
                              className="btn-nav-step"
                              onClick={handleNextSection}
                              disabled={selectedSectionIndex >= explorerStructure.sections.length - 1}
                            >
                              Next Section →
                            </button>
                          </div>

                          <div className="section-banner">
                            <h3 className="section-banner-title">{activeSection.title}</h3>
                            <div className="section-banner-pages">
                              <span>📄 {pageLabel}</span>
                            </div>
                          </div>

                          <div className="source-content-section">
                            <div className="source-attribution-card">
                              <div className="source-line">
                                Source: <strong>{explorerStructure.filename || explorerDoc.filename}</strong>
                              </div>
                              <div className="source-line">
                                {pageLabel}
                              </div>
                            </div>

                            {sectionChunks.length === 0 ? (
                              <div style={{ textAlign: 'center', padding: '1.5rem 1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                                No text chunks recorded for {pageLabel}.
                              </div>
                            ) : (
                              <div className="source-chunks-stream">
                                {sectionChunks.slice(0, 5).map((chunk, cIdx) => (
                                  <div key={chunk.chunk_id || cIdx} className="source-chunk-item">
                                    <div className="source-chunk-header">
                                      <span className="source-chunk-num">
                                        Chunk #{chunk.chunk_index !== undefined ? chunk.chunk_index + 1 : cIdx + 1}
                                      </span>
                                      <span className="badge badge-muted">Page {chunk.page}</span>
                                    </div>
                                    <div className="source-chunk-text">
                                      {chunk.text}
                                    </div>
                                  </div>
                                ))}
                                {sectionChunks.length > 5 && (
                                  <div style={{ textAlign: 'center', padding: '0.5rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                                    Showing first 5 chunks of this section. Full chunks available below.
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                </section>
              )}
            </div>
          </div>

          {/* TECHNICAL SOURCE CHUNKS (COLLAPSIBLE AT BOTTOM) */}
          <div className="collapsible-chunks-section">
            <button
              className="collapsible-toggle-btn"
              onClick={() => setShowTechnicalChunks(!showTechnicalChunks)}
            >
              <span>⚙️ Technical Source Chunks ({explorerChunks.length})</span>
              <span>{showTechnicalChunks ? '▲ Hide' : '▼ Show'}</span>
            </button>

            {showTechnicalChunks && (
              <div className="source-chunks-stream" style={{ marginTop: '0.75rem' }}>
                {explorerChunks.map((chunk, cIdx) => (
                  <div key={chunk.chunk_id || cIdx} className="source-chunk-item">
                    <div className="source-chunk-header">
                      <span className="source-chunk-num">
                        Chunk #{chunk.chunk_index !== undefined ? chunk.chunk_index + 1 : cIdx + 1}
                      </span>
                      <span className="badge badge-muted">Page {chunk.page}</span>
                    </div>
                    <div className="source-chunk-text">
                      {chunk.text}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default App;
