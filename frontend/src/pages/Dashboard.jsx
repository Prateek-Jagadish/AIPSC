import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCoverage, getCurrentAffairs, getWeakness } from '../utils/api'
import { TrendingUp, AlertTriangle, Newspaper, BookOpen, MessageSquare, Upload, ArrowRight } from 'lucide-react'

const StatCard = ({ label, value, sub, color = '#E8830A', delay = 0 }) => (
  <div className="card p-5 animate-fade-up" style={{ animationDelay: `${delay}ms` }}>
    <p className="text-xs uppercase tracking-widest mb-1" style={{ color: '#64748B' }}>{label}</p>
    <p className="text-3xl font-display font-semibold" style={{ color }}>{value}</p>
    {sub && <p className="text-xs mt-1" style={{ color: '#64748B' }}>{sub}</p>}
  </div>
)

const QuickAction = ({ icon: Icon, label, desc, to, delay }) => {
  const nav = useNavigate()
  return (
    <button onClick={() => nav(to)}
      className="card p-4 text-left group w-full animate-fade-up"
      style={{ animationDelay: `${delay}ms` }}>
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: 'rgba(232,131,10,0.12)' }}>
          <Icon size={16} style={{ color: '#E8830A' }} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>{label}</p>
          <p className="text-xs mt-0.5 truncate" style={{ color: '#64748B' }}>{desc}</p>
        </div>
        <ArrowRight size={14} style={{ color: '#64748B' }}
          className="group-hover:translate-x-1 transition-transform mt-0.5" />
      </div>
    </button>
  )
}

export default function Dashboard() {
  const [ca, setCa]       = useState([])
  const [weak, setWeak]   = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getCurrentAffairs({ days: 3, limit: 5 }).then(r => setCa(r.data.items || [])).catch(() => {}),
      getWeakness().then(r => setWeak(r.data)).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [])

  const today = new Date().toLocaleDateString('en-IN', { weekday:'long', day:'numeric', month:'long' })

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8 animate-fade-up">
        <p className="text-xs tracking-widest uppercase mb-1" style={{ color: '#E8830A' }}>
          {today}
        </p>
        <h1 className="font-display text-4xl font-semibold" style={{ color: '#E2E8F0' }}>
          Intelligence Briefing
        </h1>
        <p className="mt-1 text-sm" style={{ color: '#64748B' }}>
          Your UPSC preparation command center
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Critical Gaps"  value={weak?.critical?.length ?? '—'} color="#f87171" delay={50} />
        <StatCard label="CA Today"       value={ca.length}                      color="#E8830A" delay={100} />
        <StatCard label="Priority Topics" value={weak?.priority_order?.length ?? '—'} color="#10B981" delay={150} />
        <StatCard label="Anomalies"      value={weak?.anomalies?.length ?? '—'} color="#818cf8" delay={200} />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left: Quick actions */}
        <div className="lg:col-span-1 flex flex-col gap-3">
          <p className="text-xs uppercase tracking-widest mb-1" style={{ color: '#64748B' }}>Quick Actions</p>
          <QuickAction icon={MessageSquare} label="Ask a Question"  desc="Concept, PYQ, or answer writing" to="/chat"      delay={100} />
          <QuickAction icon={Upload}        label="Upload Document" desc="PDF, book, notes or PYQ paper"   to="/upload"     delay={150} />
          <QuickAction icon={Newspaper}     label="Today's Newspaper" desc="Upload for daily CA briefing"  to="/newspaper"  delay={200} />
          <QuickAction icon={BookOpen}      label="Revision Sheet"  desc="Weekly cheat sheet"             to="/revision"   delay={250} />
        </div>

        {/* Right: Current affairs */}
        <div className="lg:col-span-2">
          <p className="text-xs uppercase tracking-widest mb-3" style={{ color: '#64748B' }}>Recent Current Affairs</p>
          {loading ? (
            <div className="flex flex-col gap-3">
              {[1,2,3].map(i => <div key={i} className="skeleton h-16 w-full" />)}
            </div>
          ) : ca.length === 0 ? (
            <div className="card p-6 text-center animate-fade-up">
              <Newspaper size={28} style={{ color: '#64748B' }} className="mx-auto mb-2" />
              <p className="text-sm" style={{ color: '#64748B' }}>No current affairs yet.</p>
              <p className="text-xs mt-1" style={{ color: '#64748B' }}>Upload today's newspaper to get started.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {ca.map((item, i) => (
                <div key={item.id}
                  className="card p-4 animate-fade-up"
                  style={{ animationDelay: `${i * 60}ms` }}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate" style={{ color: '#E2E8F0' }}>
                        {item.headline}
                      </p>
                      <p className="text-xs mt-1 line-clamp-2" style={{ color: '#64748B' }}>
                        {item.upsc_angle || item.summary}
                      </p>
                    </div>
                    <div className="shrink-0">
                      <span className="tag tag-saffron">{item.exam_relevance || 'Both'}</span>
                    </div>
                  </div>
                  {item.probable_question && (
                    <p className="text-xs mt-2 pt-2 border-t"
                      style={{ color: '#E8830A', borderColor: 'rgba(255,255,255,0.06)' }}>
                      ❓ {item.probable_question}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Weak areas strip */}
      {weak?.priority_order?.length > 0 && (
        <div className="mt-8 animate-fade-up">
          <p className="text-xs uppercase tracking-widest mb-3" style={{ color: '#64748B' }}>
            Priority Focus Areas
          </p>
          <div className="flex flex-wrap gap-2">
            {weak.priority_order.map((t, i) => (
              <span key={i} className="tag"
                style={{ background: 'rgba(232,131,10,0.08)', color: '#E8830A',
                         border: '1px solid rgba(232,131,10,0.15)', borderRadius: 6, fontSize: '0.75rem',
                         padding: '0.3rem 0.7rem', fontWeight: 500 }}>
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
