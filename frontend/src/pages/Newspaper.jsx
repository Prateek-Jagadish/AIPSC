import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { uploadNewspaper, getCurrentAffairs } from '../utils/api'
import { Newspaper, Upload, CheckCircle, Loader, Calendar, ExternalLink } from 'lucide-react'

const PUBLICATIONS = ['The Hindu', 'Indian Express', 'Hindustan Times', 'The Tribune', 'Other']

export default function NewspaperPage() {
  const [pub,      setPub    ] = useState('The Hindu')
  const [date,     setDate   ] = useState(new Date().toISOString().split('T')[0])
  const [status,   setStatus ] = useState(null)   // null | uploading | done | error
  const [progress, setProgress] = useState(0)
  const [docId,    setDocId  ] = useState(null)
  const [caItems,  setCaItems] = useState([])
  const [loadCA,   setLoadCA ] = useState(false)

  const handleFile = useCallback(async ([file]) => {
    if (!file) return
    setStatus('uploading')
    setProgress(0)

    const fd = new FormData()
    fd.append('file', file)
    fd.append('publication', pub)
    fd.append('publish_date', date)

    try {
      const { data } = await uploadNewspaper(fd, p => setProgress(p))
      setDocId(data.document_id)
      setStatus('processing')

      // Poll until embedded, then load CA items
      const maxTries = 20
      for (let i = 0; i < maxTries; i++) {
        await new Promise(r => setTimeout(r, 4000))
        const { data: sd } = await import('../utils/api').then(m => m.getDocumentStatus(data.document_id))
        if (sd.status === 'Embedded') {
          setStatus('done')
          break
        }
        if (sd.status === 'Failed') { setStatus('error'); return }
      }

      // Load the fresh CA items
      setLoadCA(true)
      const { data: ca } = await getCurrentAffairs({ days: 1, limit: 30 })
      setCaItems(ca.items || [])
    } catch {
      setStatus('error')
    } finally {
      setLoadCA(false)
    }
  }, [pub, date])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleFile,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
    disabled: status === 'uploading' || status === 'processing',
  })

  const relevanceColor = { High: '#10B981', Medium: '#E8830A', Low: '#64748B' }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8 animate-fade-up">
        <p className="text-xs tracking-widest uppercase mb-1" style={{ color: '#E8830A' }}>
          Daily Routine
        </p>
        <h1 className="font-display text-4xl font-semibold" style={{ color: '#E2E8F0' }}>
          Today's Briefing
        </h1>
        <p className="mt-1 text-sm" style={{ color: '#64748B' }}>
          Upload today's newspaper — UPSC-relevant articles are auto-extracted
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6 mb-6 animate-fade-up">
        <div>
          <label className="text-xs uppercase tracking-widest mb-2 block" style={{ color: '#64748B' }}>
            Publication
          </label>
          <select className="input" value={pub} onChange={e => setPub(e.target.value)}>
            {PUBLICATIONS.map(p => <option key={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs uppercase tracking-widest mb-2 block" style={{ color: '#64748B' }}>
            Date
          </label>
          <input className="input" type="date" value={date} onChange={e => setDate(e.target.value)} />
        </div>
      </div>

      {/* Drop zone */}
      <div {...getRootProps()} className="animate-fade-up" style={{ animationDelay: '50ms' }}>
        <input {...getInputProps()} />
        <div className={`rounded-xl border-2 border-dashed p-10 text-center cursor-pointer transition-all
          ${isDragActive ? 'border-orange-500 bg-orange-500/5' : 'border-white/10 hover:border-orange-500/30'}`}>
          {status === 'uploading' ? (
            <>
              <Loader size={28} className="mx-auto mb-3 animate-spin" style={{ color: '#E8830A' }} />
              <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>Uploading… {progress}%</p>
              <div className="progress-bar mt-3 mx-auto" style={{ maxWidth: 200 }}>
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
            </>
          ) : status === 'processing' ? (
            <>
              <Loader size={28} className="mx-auto mb-3 animate-spin" style={{ color: '#818cf8' }} />
              <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>Filtering UPSC articles…</p>
              <p className="text-xs mt-1" style={{ color: '#64748B' }}>This takes 1–3 minutes</p>
            </>
          ) : status === 'done' ? (
            <>
              <CheckCircle size={28} className="mx-auto mb-3" style={{ color: '#10B981' }} />
              <p className="text-sm font-medium" style={{ color: '#10B981' }}>Newspaper processed!</p>
              <p className="text-xs mt-1" style={{ color: '#64748B' }}>
                {caItems.length} UPSC-relevant articles extracted
              </p>
            </>
          ) : (
            <>
              <Newspaper size={28} className="mx-auto mb-3" style={{ color: '#64748B' }} />
              <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>
                {isDragActive ? 'Drop newspaper PDF' : 'Drop today\'s newspaper PDF'}
              </p>
              <p className="text-xs mt-1" style={{ color: '#64748B' }}>
                Scanned PDFs also accepted
              </p>
            </>
          )}
        </div>
      </div>

      {/* CA Results */}
      {(caItems.length > 0 || loadCA) && (
        <div className="mt-8 animate-fade-up">
          <p className="text-xs uppercase tracking-widest mb-4" style={{ color: '#64748B' }}>
            Extracted Articles ({caItems.length})
          </p>
          {loadCA ? (
            <div className="flex flex-col gap-3">
              {[1,2,3,4].map(i => <div key={i} className="skeleton h-20" />)}
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {caItems.map((item, i) => (
                <div key={item.id} className="card p-5 animate-fade-up"
                  style={{ animationDelay: `${i * 40}ms` }}>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <h3 className="text-sm font-medium" style={{ color: '#E2E8F0' }}>
                      {item.headline}
                    </h3>
                    <span className="tag shrink-0"
                      style={{ background: `rgba(${item.relevance_level === 'High' ? '16,185,129' : '232,131,10'},0.15)`,
                               color: relevanceColor[item.relevance_level] || '#E8830A' }}>
                      {item.relevance_level}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed mb-3" style={{ color: '#94A3B8' }}>
                    {item.summary}
                  </p>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    {item.probable_question && (
                      <div style={{ gridColumn: '1 / -1' }}>
                        <span style={{ color: '#E8830A' }}>❓ Probable Q: </span>
                        <span style={{ color: '#CBD5E1' }}>{item.probable_question}</span>
                      </div>
                    )}
                    {item.static_linkage && (
                      <div>
                        <span style={{ color: '#64748B' }}>Static: </span>
                        <span style={{ color: '#CBD5E1' }}>{item.static_linkage}</span>
                      </div>
                    )}
                    {item.prelims_facts && (
                      <div>
                        <span style={{ color: '#64748B' }}>Prelims: </span>
                        <span style={{ color: '#CBD5E1' }}>{item.prelims_facts}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
