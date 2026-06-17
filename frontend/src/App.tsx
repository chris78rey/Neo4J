import { useEffect, useMemo, useState } from 'react'
import { NavLink, Navigate, Outlet, Route, Routes, useNavigate, useOutletContext } from 'react-router-dom'

type Job = { status: string; detail?: string }
type DocumentRecord = { title: string; source: string; job_id?: string; chunks?: string; entities?: string; relations?: string }

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

async function requestJSON(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE}${path}`, init)
  const text = await response.text()
  if (!response.ok) {
    throw new Error(text || `Request failed with ${response.status}`)
  }
  return text ? JSON.parse(text) : {}
}

type AppContext = {
  result: string
  setResult: (value: string) => void
  askResult: string
  setAskResult: (value: string) => void
  error: string
  setError: (value: string) => void
  busy: boolean
  setBusy: (value: boolean) => void
  busyLabel: string
  setBusyLabel: (value: string) => void
  jobs: Record<string, Job>
  setJobs: (value: Record<string, Job>) => void
  documents: Record<string, DocumentRecord>
  setDocuments: (value: Record<string, DocumentRecord>) => void
  jobId: string
  setJobId: (value: string) => void
  jobStatus: string
  setJobStatus: (value: string) => void
  question: string
  setQuestion: (value: string) => void
  path: string
  setPath: (value: string) => void
  selectedDoc: { id: string; data: DocumentRecord } | null
  setSelectedDoc: (value: { id: string; data: DocumentRecord } | null) => void
  chatModel: string
  setChatModel: (value: string) => void
  embeddingModel: string
  setEmbeddingModel: (value: string) => void
  refreshJob: () => Promise<void>
  loadJobs: () => Promise<void>
  loadDocuments: () => Promise<void>
  deleteDocument: (documentId: string) => Promise<void>
  ingestFile: (event: React.FormEvent<HTMLFormElement>) => Promise<void>
  askQuestion: (event: React.FormEvent<HTMLFormElement>) => Promise<void>
  timeline: string[]
}

function Shell({ context }: { context: AppContext }) {
  const navItems = [
    ['/', 'Overview'],
    ['/ingest', 'Ingest'],
    ['/ask', 'Ask'],
    ['/documents', 'Documents'],
    ['/jobs', 'Jobs'],
  ] as const

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">Neo4j GraphRAG</p>
          <h1>Control center</h1>
          <p className="lede">Una interfaz por secciones para subir fuentes, preguntar y administrar documentos y jobs.</p>
        </div>
        <nav className="nav">
          {navItems.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'}>
              {({ isActive }) => <button type="button" className={`nav-item ${isActive ? 'active' : ''}`}>{label}</button>}
            </NavLink>
          ))}
        </nav>
        {(context.busyLabel || context.error) && (
          <div className={`banner ${context.error ? 'error' : 'info'}`}>
            <strong>{context.error ? 'Error' : 'Working'}</strong>
            <span>{context.error || context.busyLabel}</span>
          </div>
        )}
      </aside>
      <section className="content">
        <Outlet context={context} />
      </section>
    </main>
  )
}

function OverviewPage() {
  const { documents, jobs, jobStatus, result } = useOutletContext<AppContext>()
  return (
    <section className="panel-grid">
      <article className="panel hero-panel editorial-hero">
        <p className="eyebrow">Overview</p>
        <h2>Upload, ingest, ask.</h2>
        <p className="lede">El flujo GraphRAG vive en backend y la UI solo lo organiza por tareas. Cada sección ahora tiene URL propia.</p>
        <div className="mini-stats">
          <div><strong>{Object.keys(documents).length}</strong><span>Documents</span></div>
          <div><strong>{Object.keys(jobs).length}</strong><span>Jobs</span></div>
          <div><strong>{jobStatus}</strong><span>Current job</span></div>
        </div>
      </article>
      <article className="panel">
        <h3>Recent result</h3>
        <pre>{result}</pre>
      </article>
    </section>
  )
}

function IngestPage() {
  const { busy, ingestFile, embeddingModel, setEmbeddingModel, path, setPath } = useOutletContext<AppContext>()
  return (
    <section className="panel-grid single">
      <article className="panel editorial-panel">
        <div className="page-head">
          <div>
            <p className="eyebrow">Ingest</p>
            <h2>Bring a source in.</h2>
          </div>
          <p className="lede">Archivo o ruta, un solo gesto. El job sigue corriendo en background y puedes ver su avance en Jobs.</p>
        </div>
        <h2>Ingest Document</h2>
        <form onSubmit={ingestFile}>
          <label>File</label>
          <input name="file" type="file" accept=".txt,.md" />
          <label>Or path on server</label>
          <input name="path" value={path} onChange={(e) => setPath(e.target.value)} />
          <label>Embedding model</label>
          <input name="ingest-embedding-model" value={embeddingModel} onChange={(e) => setEmbeddingModel(e.target.value)} placeholder="text-embedding-3-large" />
          <button type="submit" disabled={busy}>{busy ? 'Processing…' : 'Ingest'}</button>
        </form>
      </article>
    </section>
  )
}

function AskPage() {
  const { busy, askQuestion, chatModel, setChatModel, embeddingModel, setEmbeddingModel, question, setQuestion, askResult, documents } = useOutletContext<AppContext>()
  let askSummary = 'No answer yet.'
  try {
    const parsed = JSON.parse(askResult) as { document_count?: number; chunk_count?: number }
    if (parsed && typeof parsed.document_count === 'number') {
      askSummary = `${parsed.document_count} documentos · ${parsed.chunk_count ?? 0} chunks`
    }
  } catch {
    askSummary = 'No answer yet.'
  }
  return (
    <section className="panel-grid ask-layout">
      <article className="panel editorial-panel">
        <div className="page-head">
          <div>
            <p className="eyebrow">Ask</p>
            <h2>Ask with context.</h2>
          </div>
          <p className="lede">La respuesta usa automáticamente todos los documentos cargados en la biblioteca.</p>
        </div>
        <div className="active-source">
          <span>Corpus</span>
          <strong>{Object.keys(documents).length} documentos cargados</strong>
        </div>
        <form onSubmit={askQuestion}>
          {Object.keys(documents).length === 0 && (
            <div className="banner info">
              <strong>No documents yet</strong>
              <span>Load or ingest documents first. Ask will use all loaded documents automatically.</span>
            </div>
          )}
          <label>Chat model</label>
          <input value={chatModel} onChange={(e) => setChatModel(e.target.value)} placeholder="deepseek/deepseek-v4-pro" />
          <label>Embedding model</label>
          <input value={embeddingModel} onChange={(e) => setEmbeddingModel(e.target.value)} placeholder="text-embedding-3-large" />
          <label>Question</label>
          <textarea name="question" value={question} onChange={(e) => setQuestion(e.target.value)} />
          <button type="submit" disabled={busy || Object.keys(documents).length === 0}>{busy ? 'Working…' : 'Ask'}</button>
        </form>
      </article>
      <article className="panel">
        <h3>Answer</h3>
        <p className="lede">La respuesta aparece aquí sin cambiar de vista.</p>
        <div className="active-source">
          <span>Context summary</span>
          <strong>{askSummary}</strong>
        </div>
        <pre>{askResult}</pre>
      </article>
    </section>
  )
}

function DocumentsPage() {
  const { busy, documents, loadDocuments, deleteDocument, selectedDoc, setSelectedDoc, setPath } = useOutletContext<AppContext>()
  return (
    <section className="panel-grid two-col">
      <article className="panel editorial-panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">Library</p>
            <h2>Documents</h2>
          </div>
          <button type="button" onClick={loadDocuments} disabled={busy}>Load documents</button>
        </div>
        <div className="list">
          {Object.entries(documents).map(([id, doc]) => (
            <div key={id} className="entry-stack">
              <button
                type="button"
                className="entry"
                onClick={() => {
                  setSelectedDoc({ id, data: doc })
                  setPath(doc.source)
                }}
                disabled={busy}
              >
                <strong>{doc.title}</strong>
                <span>{id}</span>
                <small>{doc.source}</small>
              </button>
              <button type="button" className="secondary" onClick={() => deleteDocument(id)} disabled={busy}>
                Remove from library
              </button>
            </div>
          ))}
        </div>
      </article>
      <article className="panel">
        <h3>Document detail</h3>
        <pre className="detail">{selectedDoc ? JSON.stringify({ document_id: selectedDoc.id, ...selectedDoc.data }, null, 2) : 'Select a document.'}</pre>
      </article>
    </section>
  )
}

function JobsPage() {
  const { busy, jobs, jobId, setJobId, jobStatus, setJobStatus, loadJobs, refreshJob, result, timeline } = useOutletContext<AppContext>()
  return (
    <section className="panel-grid two-col">
      <article className="panel editorial-panel">
        <div className="page-head">
          <div>
            <p className="eyebrow">Jobs</p>
            <h2>Watch the pipeline.</h2>
          </div>
          <p className="lede">Cada ingestión corre con etapas visibles. Aquí puedes seguir el estado sin perder la señal de progreso.</p>
        </div>
        <div className="row">
          <input value={jobId} onChange={(e) => setJobId(e.target.value)} placeholder="Paste job id" />
          <button type="button" onClick={refreshJob}>Refresh</button>
        </div>
        <div className="status">{jobStatus}</div>
        <div className="timeline">
          {timeline.map((step) => (
            <div key={step} className={`step ${jobStatus.toLowerCase().includes(step) ? 'active' : ''}`}>
              <span>{step}</span>
              <span>{jobStatus.toLowerCase().includes(step) ? 'active' : 'pending'}</span>
            </div>
          ))}
        </div>
        <button type="button" onClick={loadJobs} disabled={busy}>Load jobs</button>
        <div className="list">
          {Object.entries(jobs).map(([id, job]) => (
            <button key={id} type="button" className="entry" onClick={() => { setJobId(id); setJobStatus(job.status); }} disabled={busy}>
              <strong>{id}</strong>
              <span>{job.status}</span>
              <small>{job.detail}</small>
            </button>
          ))}
        </div>
      </article>
      <article className="panel">
        <h3>Result</h3>
        <pre>{result}</pre>
      </article>
    </section>
  )
}

function RoutedApp() {
  const [result, setResult] = useState('Ready.')
  const [askResult, setAskResult] = useState('Ready.')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [busyLabel, setBusyLabel] = useState('')
  const [jobs, setJobs] = useState<Record<string, Job>>({})
  const [documents, setDocuments] = useState<Record<string, DocumentRecord>>({})
  const [jobId, setJobId] = useState('')
  const [jobStatus, setJobStatus] = useState('idle')
  const [question, setQuestion] = useState('What is the project about?')
  const [path, setPath] = useState('')
  const [selectedDoc, setSelectedDoc] = useState<{ id: string; data: DocumentRecord } | null>(null)
  const [chatModel, setChatModel] = useState('deepseek/deepseek-v4-pro')
  const [embeddingModel, setEmbeddingModel] = useState('text-embedding-3-large')
  const navigate = useNavigate()

  const timeline = useMemo(() => ['queued', 'loading', 'chunking', 'building', 'completed'], [])

  const refreshJob = async () => {
    if (!jobId.trim()) return
    const payload = await requestJSON(`/jobs/${encodeURIComponent(jobId.trim())}`)
    setJobStatus(`${payload.status}${payload.detail ? `: ${payload.detail}` : ''}`)
    setResult(JSON.stringify(payload, null, 2))
  }

  const loadJobs = async () => {
    const payload = await requestJSON('/jobs')
    setJobs(payload)
  }

  const loadDocuments = async () => {
    const payload = await requestJSON('/documents')
    setDocuments(payload)
    const entries = Object.entries(payload)
    if (!selectedDoc && entries.length > 0) {
      const [id, doc] = entries[entries.length - 1]
      setSelectedDoc({ id, data: doc })
      setPath(doc.source)
    }
  }

  const deleteDocument = async (documentId: string) => {
    setError('')
    setBusy(true)
    setBusyLabel(`Deleting ${documentId}...`)
    try {
      const normalizedId = documentId.startsWith('doc:') ? documentId.slice(4) : documentId
      const payload = await requestJSON(`/documents/${encodeURIComponent(normalizedId)}`, { method: 'DELETE' })
      setResult(JSON.stringify(payload, null, 2))
      await loadDocuments()
      await loadJobs().catch(() => undefined)
      if (selectedDoc?.id === documentId || selectedDoc?.id === normalizedId) {
        setSelectedDoc(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
      setBusyLabel('')
    }
  }

  const poll = async () => {
    await refreshJob().catch(() => undefined)
  }

  useEffect(() => {
    const timer = setInterval(poll, 2500)
    return () => clearInterval(timer)
  }, [jobId])

  useEffect(() => {
    loadDocuments().catch(() => undefined)
    loadJobs().catch(() => undefined)
  }, [])

  useEffect(() => {
    if (selectedDoc || path.trim()) return
    const entries = Object.entries(documents)
    if (entries.length === 0) return
    const [id, doc] = entries[entries.length - 1]
    setSelectedDoc({ id, data: doc })
    setPath(doc.source)
  }, [documents, selectedDoc, path])

  const ingestFile = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    setBusyLabel('Uploading and queuing ingest job...')
    try {
      const form = event.currentTarget
      const data = new FormData()
      const file = (form.elements.namedItem('file') as HTMLInputElement).files?.[0]
      const serverPath = (form.elements.namedItem('path') as HTMLInputElement).value.trim()
      const ingestEmbeddingModel = (form.elements.namedItem('ingest-embedding-model') as HTMLInputElement).value.trim()
      if (!file && !serverPath) {
        throw new Error('Choose a file or provide a server path.')
      }
      if (file) data.append('file', file)
      if (serverPath) data.append('path', serverPath)
      if (ingestEmbeddingModel) data.append('embedding_model', ingestEmbeddingModel)
      const payload = await requestJSON('/documents', { method: 'POST', body: data })
      setResult(JSON.stringify(payload, null, 2))
      if (payload.job_id) {
        setJobId(payload.job_id)
        setJobStatus('queued')
        navigate('/jobs')
      }
      await Promise.all([loadJobs().catch(() => undefined), loadDocuments().catch(() => undefined)])
      await refreshJob().catch(() => undefined)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
      setBusyLabel('')
    }
  }

  const askQuestion = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    setBusyLabel('Generating answer...')
    try {
      const form = event.currentTarget
      const questionValue = (form.elements.namedItem('question') as HTMLTextAreaElement).value.trim()
      if (!questionValue) {
        throw new Error('Write a question first.')
      }
      const payload = await requestJSON('/questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: questionValue, limit: 3, model: chatModel, embedding_model: embeddingModel }),
      })
      setAskResult(JSON.stringify(payload, null, 2))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
      setBusyLabel('')
    }
  }

  const context: AppContext = {
    result,
    setResult,
    askResult,
    setAskResult,
    error,
    setError,
    busy,
    setBusy,
    busyLabel,
    setBusyLabel,
    jobs,
    setJobs,
    documents,
    setDocuments,
    jobId,
    setJobId,
    jobStatus,
    setJobStatus,
    question,
    setQuestion,
    path,
    setPath,
    selectedDoc,
    setSelectedDoc,
    chatModel,
    setChatModel,
    embeddingModel,
    setEmbeddingModel,
    refreshJob,
    loadJobs,
    loadDocuments,
    deleteDocument,
    ingestFile,
    askQuestion,
    timeline,
  }

  return (
    <Routes>
      <Route element={<Shell context={context} />}>
        <Route index element={<OverviewPage />} />
        <Route path="ingest" element={<IngestPage />} />
        <Route path="ask" element={<AskPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="jobs" element={<JobsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return <RoutedApp />
}
