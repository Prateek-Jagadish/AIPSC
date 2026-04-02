import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { uploadPDF, getDocumentStatus } from '../utils/api'
import { Upload, CheckCircle, AlertCircle, Loader, FileText, X } from 'lucide-react'

const DOC_TYPES = [
  { value: 'PYQ',      label: 'PYQ Paper',      desc: '2016–2025 Mains & Prelims papers' },
  { value: 'NCERT',    label: 'NCERT',           desc: 'Class 6–12 NCERTs' },
  { value: 'Book',     label: 'Standard Book',   desc: 'Laxmikanth, Bipan Chandra, etc.' },
  { value: 'Notes',    label: 'Notes',           desc: 'Class notes, handwritten or typed' },
  { value: 'Syllabus', label: 'Syllabus',        desc: 'UPSC official syllabus' },
  { value: 'Other',    label: 'Other',           desc: 'Any other study material' },
]

const GS_PAPERS = ['GS1', 'GS2', 'GS3', 'GS4', 'Essay', 'Prelims_GS1', 'Prelims_GS2']

function UploadItem({ item, onRemove }) {
  const statusColor = {
    uploading: '#E8830A', processing: '#818cf8',
    Tagged: '#10B981', Embedded: '#10B981',
    Failed: '#f87171', done: '#10B981',
  }[item.status] || '#64748B'

  const StatusIcon = item.status === 'Failed' ? AlertCircle :
    item.status === 'Embedded' || item.status === 'done' ? CheckCircle : Loader

  return (
    <div className="card p-4 flex items-center gap-4 animate-fade-up">
      <FileText size={18} style={{ color: '#E8830A', shrink: 0 }} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate" style={{ color: '#E2E8F0' }}>
          {item.name}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs" style={{ color: statusColor }}>{item.status}</span>
          {item.progress > 0 && item.progress < 100 && (
            <div className="progress-bar flex-1" style={{ maxWidth: 120 }}>
              <div className="progress-fill" style={{ width: `${item.progress}%` }} />
            </div>
          )}
          {item.docId && (
            <span className="text-[10px] font-mono" style={{ color: '#64748B' }}>
              id:{item.docId}
            </span>
          )}
        </div>
      </div>
      <StatusIcon size={16} style={{ color: statusColor, shrink: 0 }}
        className={item.status === 'processing' ? 'animate-spin' : ''} />
      {(item.status === 'done' || item.status === 'Failed') && (
        <button onClick={() => onRemove(item.id)}>
          <X size={14} style={{ color: '#64748B' }} />
        </button>
      )}
    </div>
  )
}

export default function UploadPage() {
  const [docType, setDocType] = useState('Notes')
  const [year,    setYear   ] = useState('')
  const [paper,   setPaper  ] = useState('')
  const [items,   setItems  ] = useState([])

  const updateItem = (id, patch) =>
    setItems(prev => prev.map(it => it.id === id ? { ...it, ...patch } : it))

  const pollStatus = async (itemId, docId) => {
    const maxAttempts = 30
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise(r => setTimeout(r, 3000))
      try {
        const { data } = await getDocumentStatus(docId)
        updateItem(itemId, { status: data.status, chunks: data.chunk_count, images: data.image_count })
        if (['Embedded', 'Failed'].includes(data.status)) break
      } catch { break }
    }
  }

  const handleFiles = useCallback(async (files) => {
    for (const file of files) {
      const id = `${Date.now()}-${Math.random()}`
      setItems(prev => [...prev, { id, name: file.name, status: 'uploading', progress: 0 }])

      const fd = new FormData()
      fd.append('file', file)
      fd.append('doc_type', docType)
      if (year)  fd.append('year',  year)
      if (paper) fd.append('paper', paper)

      try {
        const { data } = await uploadPDF(fd, pct => updateItem(id, { progress: pct }))
        updateItem(id, { status: 'processing', docId: data.document_id })
        pollStatus(id, data.document_id)
      } catch (e) {
        updateItem(id, { status: 'Failed' })
      }
    }
  }, [docType, year, paper])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleFiles,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: true,
  })

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8 animate-fade-up">
        <p className="text-xs tracking-widest uppercase mb-1" style={{ color: '#E8830A' }}>Knowledge Base</p>
        <h1 className="font-display text-4xl font-semibold" style={{ color: '#E2E8F0' }}>Upload Documents</h1>
        <p className="mt-1 text-sm" style={{ color: '#64748B' }}>
          Text PDFs, scanned PDFs, mixed — all handled automatically
        </p>
      </div>

      {/* Document type selector */}
      <div className="mb-6 animate-fade-up" style={{ animationDelay: '50ms' }}>
        <p className="text-xs uppercase tracking-widest mb-3" style={{ color: '#64748B' }}>Document Type</p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {DOC_TYPES.map(dt => (
            <button key={dt.value} onClick={() => setDocType(dt.value)}
              className={`card p-3 text-left transition-all ${docType === dt.value ? 'card-glow' : ''}`}
              style={docType === dt.value ? { borderColor: 'rgba(232,131,10,0.4)' } : {}}>
              <p className="text-sm font-medium" style={{ color: docType === dt.value ? '#E8830A' : '#E2E8F0' }}>
                {dt.label}
              </p>
              <p className="text-[10px] mt-0.5" style={{ color: '#64748B' }}>{dt.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Optional metadata */}
      {docType === 'PYQ' && (
        <div className="grid grid-cols-2 gap-4 mb-6 animate-fade-up">
          <div>
            <label className="text-xs uppercase tracking-widest mb-2 block" style={{ color: '#64748B' }}>
              Year
            </label>
            <input className="input" placeholder="2023" type="number"
              value={year} onChange={e => setYear(e.target.value)} />
          </div>
          <div>
            <label className="text-xs uppercase tracking-widest mb-2 block" style={{ color: '#64748B' }}>
              Paper
            </label>
            <select className="input" value={paper} onChange={e => setPaper(e.target.value)}>
              <option value="">Select paper</option>
              {GS_PAPERS.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>
      )}

      {/* Drop zone */}
      <div {...getRootProps()} className="animate-fade-up" style={{ animationDelay: '100ms' }}>
        <input {...getInputProps()} />
        <div className={`rounded-xl border-2 border-dashed p-12 text-center cursor-pointer transition-all
          ${isDragActive ? 'border-orange-500 bg-orange-500/5' : 'border-white/10 hover:border-orange-500/30 hover:bg-white/2'}`}>
          <Upload size={28} className="mx-auto mb-3"
            style={{ color: isDragActive ? '#E8830A' : '#64748B' }} />
          <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>
            {isDragActive ? 'Drop to upload' : 'Drop PDF files here'}
          </p>
          <p className="text-xs mt-1" style={{ color: '#64748B' }}>
            or click to browse — text, scanned, and mixed PDFs accepted
          </p>
        </div>
      </div>

      {/* Upload list */}
      {items.length > 0 && (
        <div className="mt-6 flex flex-col gap-3">
          <p className="text-xs uppercase tracking-widest" style={{ color: '#64748B' }}>
            Uploads ({items.length})
          </p>
          {items.map(item => (
            <UploadItem key={item.id} item={item}
              onRemove={id => setItems(prev => prev.filter(it => it.id !== id))} />
          ))}
        </div>
      )}

      {/* Status legend */}
      <div className="mt-8 card p-4 animate-fade-up" style={{ animationDelay: '150ms' }}>
        <p className="text-xs uppercase tracking-widest mb-3" style={{ color: '#64748B' }}>Processing Stages</p>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {[
            ['Uploaded',   '#E8830A', 'File saved to disk'],
            ['Processing', '#818cf8', 'OCR + text extraction'],
            ['Tagged',     '#E8830A', 'AI topic tagging'],
            ['Embedded',   '#10B981', 'Vectors stored — searchable'],
          ].map(([s, c, d]) => (
            <div key={s} className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: c }} />
              <span style={{ color: '#E2E8F0' }}>{s}</span>
              <span style={{ color: '#64748B' }}>— {d}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
