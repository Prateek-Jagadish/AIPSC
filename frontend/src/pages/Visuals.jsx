import { useState, useEffect } from 'react'
import { listDocuments, getDocumentVisuals, visualImageUrl, processVisual } from '../utils/api'
import { Image, Map, Table, TrendingUp, Workflow, RefreshCw, Loader } from 'lucide-react'

const TYPE_ICONS = {
  Map: Map, Table: Table, Graph: TrendingUp,
  Diagram: Workflow, Flowchart: Workflow, Other: Image,
}
const TYPE_COLORS = {
  Map: '#10B981', Table: '#818cf8', Graph: '#E8830A',
  Diagram: '#F5A623', Flowchart: '#F5A623', Other: '#64748B',
}

function VisualCard({ v, onProcess }) {
  const [expanded, setExpanded] = useState(false)
  const [imgError, setImgError] = useState(false)
  const Icon  = TYPE_ICONS[v.image_type] || Image
  const color = TYPE_COLORS[v.image_type] || '#64748B'

  return (
    <div className="card overflow-hidden animate-fade-up flex flex-col">
      {/* Image */}
      <div className="relative bg-[#080D18] flex items-center justify-center"
        style={{ height: 180, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        {imgError ? (
          <div className="flex flex-col items-center gap-2">
            <Icon size={28} style={{ color }} />
            <p className="text-xs" style={{ color: '#64748B' }}>{v.image_type}</p>
          </div>
        ) : (
          <img src={visualImageUrl(v.id)}
            alt={v.ai_summary || 'Visual asset'}
            className="max-h-full max-w-full object-contain"
            onError={() => setImgError(true)} />
        )}
        <span className="absolute top-2 right-2 tag"
          style={{ background: `rgba(${color === '#10B981' ? '16,185,129' : '232,131,10'},0.15)`, color }}>
          {v.image_type}
        </span>
        {v.exam_use && v.exam_use !== 'Reference' && (
          <span className="absolute top-2 left-2 tag tag-blue">{v.exam_use}</span>
        )}
      </div>

      {/* Info */}
      <div className="p-4 flex flex-col gap-2 flex-1">
        {v.ai_summary ? (
          <>
            <p className="text-xs font-medium leading-snug" style={{ color: '#E2E8F0' }}>
              {v.ai_summary}
            </p>
            {v.upsc_relevance_note && (
              <p className="text-[10px]" style={{ color: '#64748B' }}>{v.upsc_relevance_note}</p>
            )}
            {v.probable_question && (
              <p className="text-[10px]" style={{ color: '#E8830A' }}>
                ❓ {v.probable_question}
              </p>
            )}
            {v.geo_entities && (
              <p className="text-[10px]" style={{ color: '#64748B' }}>
                📍 {v.geo_entities}
              </p>
            )}
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center gap-2 py-2">
            <p className="text-xs" style={{ color: '#64748B' }}>Not yet captioned</p>
            <button className="btn-ghost text-xs flex items-center gap-1"
              onClick={() => onProcess(v.id)}>
              <RefreshCw size={11} /> Generate Caption
            </button>
          </div>
        )}

        <div className="flex items-center justify-between mt-auto pt-2"
          style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <span className="text-[10px] font-mono" style={{ color: '#64748B' }}>
            p.{v.page_number} · {v.width_px}×{v.height_px}
          </span>
          <button onClick={() => setExpanded(e => !e)}
            className="text-[10px]" style={{ color: '#E8830A' }}>
            {expanded ? 'Less' : 'Full caption'}
          </button>
        </div>

        {expanded && v.ai_caption && (
          <p className="text-xs leading-relaxed mt-1" style={{ color: '#94A3B8' }}>
            {v.ai_caption}
          </p>
        )}
      </div>
    </div>
  )
}

export default function Visuals() {
  const [docs,     setDocs    ] = useState([])
  const [selDoc,   setSelDoc  ] = useState(null)
  const [visuals,  setVisuals ] = useState([])
  const [filter,   setFilter  ] = useState('All')
  const [loading,  setLoading ] = useState(false)

  useEffect(() => {
    listDocuments({ limit: 50 })
      .then(r => setDocs(r.data.documents || []))
      .catch(() => {})
  }, [])

  const loadVisuals = async (docId) => {
    setSelDoc(docId)
    setLoading(true)
    setVisuals([])
    try {
      const { data } = await getDocumentVisuals(docId)
      setVisuals(data.visuals || [])
    } catch { }
    finally { setLoading(false) }
  }

  const handleProcess = async (visId) => {
    await processVisual(visId)
    loadVisuals(selDoc)
  }

  const filtered = filter === 'All'
    ? visuals
    : visuals.filter(v => v.image_type === filter)

  const types = ['All', ...new Set(visuals.map(v => v.image_type))]

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8 animate-fade-up">
        <p className="text-xs tracking-widest uppercase mb-1" style={{ color: '#E8830A' }}>Study Assets</p>
        <h1 className="font-display text-4xl font-semibold" style={{ color: '#E2E8F0' }}>
          Maps & Visuals
        </h1>
        <p className="mt-1 text-sm" style={{ color: '#64748B' }}>
          All maps, tables, graphs, and diagrams extracted from your documents
        </p>
      </div>

      {/* Document selector */}
      <div className="mb-6 animate-fade-up">
        <p className="text-xs uppercase tracking-widest mb-3" style={{ color: '#64748B' }}>
          Select Document
        </p>
        <div className="flex flex-wrap gap-2">
          {docs.length === 0 ? (
            <p className="text-sm" style={{ color: '#64748B' }}>
              No documents uploaded yet.
            </p>
          ) : (
            docs.map(d => (
              <button key={d.id} onClick={() => loadVisuals(d.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  selDoc === d.id ? 'text-black' : 'btn-ghost'}`}
                style={selDoc === d.id ? { background: '#E8830A' } : {}}>
                {d.title.length > 35 ? d.title.slice(0, 35) + '…' : d.title}
                {d.images > 0 && (
                  <span className="ml-1.5 opacity-70">{d.images} imgs</span>
                )}
              </button>
            ))
          )}
        </div>
      </div>

      {/* Type filter */}
      {visuals.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6 animate-fade-up">
          {types.map(t => (
            <button key={t} onClick={() => setFilter(t)}
              className={`px-3 py-1 rounded-lg text-xs transition-all ${
                filter === t ? 'text-black' : 'btn-ghost'}`}
              style={filter === t ? { background: TYPE_COLORS[t] || '#E8830A' } : {}}>
              {t} {t === 'All' ? `(${visuals.length})` : `(${visuals.filter(v=>v.image_type===t).length})`}
            </button>
          ))}
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton h-64" />)}
        </div>
      ) : filtered.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filtered.map(v => (
            <VisualCard key={v.id} v={v} onProcess={handleProcess} />
          ))}
        </div>
      ) : selDoc ? (
        <div className="card p-12 text-center">
          <Image size={32} style={{ color: '#64748B' }} className="mx-auto mb-3" />
          <p className="text-sm" style={{ color: '#64748B' }}>
            No visual assets found in this document.
          </p>
        </div>
      ) : null}
    </div>
  )
}
