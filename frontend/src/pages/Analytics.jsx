import { useEffect, useState } from 'react'
import { getWeakness, getCoverage, getPYQTrends, getCASummary } from '../utils/api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { AlertTriangle, TrendingUp, BookOpen, Newspaper } from 'lucide-react'

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload?.length) return (
    <div className="card p-3 text-xs" style={{ border: '1px solid rgba(232,131,10,0.3)' }}>
      <p style={{ color: '#E8830A' }}>{label}</p>
      <p style={{ color: '#E2E8F0' }}>{payload[0].value}</p>
    </div>
  )
  return null
}

function WeakCard({ w, level }) {
  const color = { Critical: '#f87171', High: '#fb923c', Medium: '#E8830A' }[level] || '#E8830A'
  return (
    <div className="card p-4 animate-fade-up">
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>{w.topic_name}</p>
          <p className="text-xs" style={{ color: '#64748B' }}>{w.paper}</p>
        </div>
        <div className="text-right">
          <p className="text-lg font-display font-semibold" style={{ color }}>
            {w.gap_score?.toFixed(1)}
          </p>
          <p className="text-[10px]" style={{ color: '#64748B' }}>gap</p>
        </div>
      </div>
      <div className="progress-bar">
        <div className="progress-fill"
          style={{ width: `${(w.coverage_score / 10) * 100}%`, background: color }} />
      </div>
      <div className="flex justify-between text-[10px] mt-1" style={{ color: '#64748B' }}>
        <span>Coverage: {w.coverage_score?.toFixed(1)}/10</span>
        <span>PYQ weight: {w.pyq_weight?.toFixed(1)}</span>
      </div>
      {w.reason && (
        <p className="text-[10px] mt-2" style={{ color: '#64748B' }}>
          {w.reason}
        </p>
      )}
      {w.is_anomaly && (
        <span className="tag tag-red mt-2 inline-flex">
          ⚠ Never studied
        </span>
      )}
    </div>
  )
}

export default function Analytics() {
  const [weak,     setWeak    ] = useState(null)
  const [trends,   setTrends  ] = useState(null)
  const [caSummary, setCaSummary] = useState(null)
  const [loading,  setLoading ] = useState(true)
  const [tab,      setTab     ] = useState('weakness')

  useEffect(() => {
    setLoading(true)
    Promise.all([
      getWeakness().then(r => setWeak(r.data)).catch(() => {}),
      getPYQTrends().then(r => setTrends(r.data)).catch(() => {}),
      getCASummary(30).then(r => setCaSummary(r.data)).catch(() => {}),
    ]).finally(() => setLoading(false))
  }, [])

  const pyqChartData = trends
    ? Object.entries(trends.topic_frequency || {})
        .slice(0, 12)
        .map(([name, count]) => ({ name: name.length > 14 ? name.slice(0, 14) + '…' : name, count }))
    : []

  const caChartData = caSummary?.topics?.slice(0, 10) || []

  const TABS = [
    { id: 'weakness', label: 'Weakness',  icon: AlertTriangle },
    { id: 'pyq',      label: 'PYQ Trends', icon: TrendingUp   },
    { id: 'ca',       label: 'CA Coverage', icon: Newspaper   },
  ]

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8 animate-fade-up">
        <p className="text-xs tracking-widest uppercase mb-1" style={{ color: '#E8830A' }}>Intelligence</p>
        <h1 className="font-display text-4xl font-semibold" style={{ color: '#E2E8F0' }}>Analytics</h1>
        <p className="mt-1 text-sm" style={{ color: '#64748B' }}>
          Gap analysis, PYQ patterns, and current affairs coverage
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-8 animate-fade-up" style={{ animationDelay: '50ms' }}>
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === id
                ? 'text-black'
                : 'btn-ghost'
            }`}
            style={tab === id ? { background: '#E8830A' } : {}}>
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex flex-col gap-4">
          {[1,2,3].map(i => <div key={i} className="skeleton h-24" />)}
        </div>
      ) : (
        <>
          {/* Weakness Tab */}
          {tab === 'weakness' && (weak ? (
            <div className="flex flex-col gap-6">
              {weak.message && (
                <div className="card p-4 animate-fade-up"
                  style={{ borderColor: 'rgba(248,113,113,0.2)' }}>
                  <p className="text-sm" style={{ color: '#f87171' }}>{weak.message}</p>
                </div>
              )}

              {weak.priority_order?.length > 0 && (
                <div className="animate-fade-up">
                  <p className="text-xs uppercase tracking-widest mb-3" style={{ color: '#64748B' }}>
                    Priority Order
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {weak.priority_order.map((t, i) => (
                      <span key={i} className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium"
                        style={{ background: 'rgba(232,131,10,0.1)', color: '#E8830A',
                                 border: '1px solid rgba(232,131,10,0.2)' }}>
                        <span className="w-4 h-4 rounded-full bg-orange-500 text-black text-[9px]
                          font-bold flex items-center justify-center shrink-0">
                          {i + 1}
                        </span>
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {weak.critical?.length > 0 && (
                <div>
                  <p className="text-xs uppercase tracking-widest mb-3 flex items-center gap-2"
                    style={{ color: '#f87171' }}>
                    <AlertTriangle size={12} /> Critical Gaps ({weak.critical.length})
                  </p>
                  <div className="grid md:grid-cols-2 gap-3">
                    {weak.critical.map((w, i) => <WeakCard key={i} w={w} level="Critical" />)}
                  </div>
                </div>
              )}

              {weak.high?.length > 0 && (
                <div>
                  <p className="text-xs uppercase tracking-widest mb-3" style={{ color: '#fb923c' }}>
                    High Priority ({weak.high.length})
                  </p>
                  <div className="grid md:grid-cols-2 gap-3">
                    {weak.high.map((w, i) => <WeakCard key={i} w={w} level="High" />)}
                  </div>
                </div>
              )}

              {!weak.critical?.length && !weak.high?.length && (
                <div className="card p-8 text-center">
                  <BookOpen size={32} style={{ color: '#10B981' }} className="mx-auto mb-3" />
                  <p className="text-sm font-medium" style={{ color: '#10B981' }}>
                    No critical gaps detected!
                  </p>
                  <p className="text-xs mt-1" style={{ color: '#64748B' }}>
                    Keep asking questions and uploading materials to build your profile.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="card p-12 text-center animate-fade-up">
              <AlertTriangle size={36} style={{ color: '#64748B' }} className="mx-auto mb-3" />
              <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>
                No weakness data yet
              </p>
              <p className="text-xs mt-2 max-w-sm mx-auto" style={{ color: '#64748B' }}>
                Start asking questions in<span style={{ color: '#E8830A' }}> Ask & Learn </span>
                and upload your study materials. The system will automatically
                detect your weak areas and rank them by priority.
              </p>
            </div>
          ))}

          {/* PYQ Trends Tab */}
          {tab === 'pyq' && (trends ? (
            <div className="flex flex-col gap-6 animate-fade-up">
              <div className="card p-6">
                <p className="text-xs uppercase tracking-widest mb-4" style={{ color: '#64748B' }}>
                  Topic Frequency in PYQs
                </p>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={pyqChartData} layout="vertical"
                    margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
                    <XAxis type="number" tick={{ fill: '#64748B', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="name" tick={{ fill: '#94A3B8', fontSize: 11 }}
                      width={120} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {pyqChartData.map((_, i) => (
                        <Cell key={i}
                          fill={i === 0 ? '#E8830A' : i < 3 ? '#F5A623' : '#1e3a5f'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {trends.command_word_frequency && (
                <div className="card p-6">
                  <p className="text-xs uppercase tracking-widest mb-4" style={{ color: '#64748B' }}>
                    Command Words
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(trends.command_word_frequency).map(([w, n]) => (
                      <span key={w} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs"
                        style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                                 color: '#E2E8F0' }}>
                        {w} <span style={{ color: '#E8830A', fontWeight: 600 }}>{n}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="card p-12 text-center animate-fade-up">
              <TrendingUp size={36} style={{ color: '#64748B' }} className="mx-auto mb-3" />
              <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>
                No PYQ data uploaded yet
              </p>
              <p className="text-xs mt-2 max-w-sm mx-auto" style={{ color: '#64748B' }}>
                Upload PYQ papers via the<span style={{ color: '#E8830A' }}> Upload </span>page.
                The system will analyze topic frequencies, command words, and question patterns
                across all years.
              </p>
            </div>
          ))}

          {/* CA Tab */}
          {tab === 'ca' && (caSummary?.topics?.length > 0 ? (
            <div className="flex flex-col gap-4 animate-fade-up">
              <div className="card p-6">
                <p className="text-xs uppercase tracking-widest mb-4" style={{ color: '#64748B' }}>
                  Topics in Last 30 Days' Current Affairs
                </p>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={caChartData} layout="vertical"
                    margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
                    <XAxis type="number" tick={{ fill: '#64748B', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="topic" tick={{ fill: '#94A3B8', fontSize: 11 }}
                      width={130} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="article_count" radius={[0, 4, 4, 0]} fill="#10B981" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : (
            <div className="card p-12 text-center animate-fade-up">
              <Newspaper size={36} style={{ color: '#64748B' }} className="mx-auto mb-3" />
              <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>
                No current affairs data yet
              </p>
              <p className="text-xs mt-2 max-w-sm mx-auto" style={{ color: '#64748B' }}>
                Upload newspapers via<span style={{ color: '#E8830A' }}> Daily Briefing </span>
                to see topic distribution charts and UPSC-relevant article analysis.
              </p>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
