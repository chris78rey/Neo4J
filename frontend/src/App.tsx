import { useEffect, useMemo, useState } from 'react'

type Job = { status: string; detail?: string }
type DocumentRecord = { title: string; source: string; job_id?: string; chunks?: string; entities?: string; relations?: string }

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

async function requestJSON(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE}${path}`, init)
  return response.json()
}

export default function App() {
  const [result, setResult] = useState('Ready.')
  const [jobs, setJobs] = useState<Record<string, Job>>({})
  const [documents, setDocuments] = useState<Record<string, DocumentRecord>>({})
  const [jobId, setJobId] = useState('')
  const [jobStatus, setJobStatus] = useState('idle')
  const [question, setQuestion] = useState('What is the project about?')
  const [path, setPath] = useState('requerimientos/00_contexto_general.md')
  const [selectedDoc, setSelectedDoc] = useState<{ id: string; data: DocumentRecord } | null>(null)
  const [chatModel, setChatModel] = useState('openai/gpt-4o-mini')
  const [embeddingModel, setEmbeddingModel] = useState('text-embedding-3-large')

  const timeline = useMemo(() => ['queued', 'loading', 'chunking', 'building', 'completed'], [])

  const refreshJob = async () => {
    if (!jobId.trim()) return
    const payload = await requestJSON(`/jobs/${encodeURIComponent(jobId.trim())}`)
    setJobStatus(`${payload.status}${payload.detail ? `: ${payload.detail}` : ''}`)
    setResult(JSON.stringify(payload, null, 2))
  }

  const loadJobs = async () => {
    setJobs(await requestJSON('/jobs'))
  }

  const loadDocuments = async () => {
    setDocuments(await requestJSON('/documents'))
  }

  const poll = async () => {
    await refreshJob().catch(() => undefined)
  }

  useEffect(() => {
    const timer = setInterval(poll, 2500)
    return () => clearInterval(timer)
  })

  const ingestFile = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData()
    const file = (form.elements.namedItem('file') as HTMLInputElement).files?.[0]
    const serverPath = (form.elements.namedItem('path') as HTMLInputElement).value
    const ingestEmbeddingModel = (form.elements.namedItem('ingest-embedding-model') as HTMLInputElement).value
    if (file) data.append('file', file)
    if (serverPath) data.append('path', serverPath)
    if (ingestEmbeddingModel) data.append('embedding_model', ingestEmbeddingModel)
    const payload = await requestJSON('/documents', { method: 'POST', body: data })
    setResult(JSON.stringify(payload, null, 2))
    if (payload.job_id) setJobId(payload.job_id)
    await refreshJob()
  }

  const askQuestion = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const pathValue = (form.elements.namedItem('ask-path') as HTMLInputElement).value
    const questionValue = (form.elements.namedItem('question') as HTMLTextAreaElement).value
    const payload = await requestJSON(`/questions?path=${encodeURIComponent(pathValue)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: questionValue, limit: 3, model: chatModel, embedding_model: embeddingModel }),
    })
    setResult(JSON.stringify(payload, null, 2))
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">Neo4j GraphRAG</p>
        <h1>Upload, ingest, ask.</h1>
        <p className="lede">Frontend separado para el motor GraphRAG. Consume la API de FastAPI y muestra jobs, documentos y respuestas.</p>
      </header>
      <section className="grid">
        <article className="card">
          <h2>Ingest Document</h2>
          <form onSubmit={ingestFile}>
            <label>File</label>
            <input name="file" type="file" accept=".txt,.md" />
            <label>Or path on server</label>
            <input name="path" value={path} onChange={(e) => setPath(e.target.value)} />
            <label>Embedding model</label>
            <input name="ingest-embedding-model" value={embeddingModel} onChange={(e) => setEmbeddingModel(e.target.value)} placeholder="text-embedding-3-large" />
            <button type="submit">Ingest</button>
          </form>
        </article>
        <article className="card">
          <h2>Ask</h2>
          <form onSubmit={askQuestion}>
            <label>Document path</label>
            <input name="ask-path" value={path} onChange={(e) => setPath(e.target.value)} />
            <label>Chat model</label>
            <input value={chatModel} onChange={(e) => setChatModel(e.target.value)} placeholder="openai/gpt-4o-mini" />
            <label>Embedding model</label>
            <input value={embeddingModel} onChange={(e) => setEmbeddingModel(e.target.value)} placeholder="text-embedding-3-large" />
            <label>Question</label>
            <textarea name="question" value={question} onChange={(e) => setQuestion(e.target.value)} />
            <button type="submit">Ask</button>
          </form>
        </article>
        <article className="card">
          <h2>Jobs</h2>
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
          <button type="button" onClick={loadJobs}>Load jobs</button>
          <div className="list">
            {Object.entries(jobs).map(([id, job]) => (
              <button key={id} type="button" className="entry" onClick={() => { setJobId(id); setJobStatus(job.status); }}>
                <strong>{id}</strong>
                <span>{job.status}</span>
                <small>{job.detail}</small>
              </button>
            ))}
          </div>
        </article>
        <article className="card">
          <h2>Documents</h2>
          <button type="button" onClick={loadDocuments}>Load documents</button>
          <div className="list">
            {Object.entries(documents).map(([id, doc]) => (
              <button key={id} type="button" className="entry" onClick={() => setSelectedDoc({ id, data: doc })}>
                <strong>{doc.title}</strong>
                <span>{id}</span>
                <small>{doc.source}</small>
              </button>
            ))}
          </div>
          <pre className="detail">{selectedDoc ? JSON.stringify({ document_id: selectedDoc.id, ...selectedDoc.data }, null, 2) : 'Select a document.'}</pre>
        </article>
      </section>
      <section className="card wide">
        <h2>Result</h2>
        <pre>{result}</pre>
      </section>
    </main>
  )
}
