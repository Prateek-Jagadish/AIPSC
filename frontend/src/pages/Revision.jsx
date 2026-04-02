import { useState } from 'react'
import { getWeeklyRevision, getMonthlyRevision, getTopicRevision } from '../utils/api'
import { BookOpen, Calendar, Loader, ChevronDown, ChevronRight } from 'lucide-react'

function Section({ title, children, color = '#E8830A' }) {
  const [open, setOpen] = useState(true)
  return (
    <div className="card overflow-hidden animate-fade-up">
      <button className="w-full flex items-center justify-between p-4 text-left"
        onClick={() => setOpen(o => !o)}>
        <p className="text-xs uppercase tracking-widest font-semibold" style={{ color }}>
          {title}
        </p>
        {open ? <ChevronDown size={14} style={{ color: '#64748B' }} />
               : <ChevronRight size={14} style={{ color: '#64748B' }} />}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  )
}

function CheatSheet({ data }) {
  if (!data) return null
  const cs = data.cheatsheet || data

  return (
    <div className="flex flex-col gap-4">
      {cs.high_priority_topics?.length > 0 && (
        <Section title="High Priority Topics" color="#E8830A">
          <div className="flex flex-col gap-3">
            {cs.high_priority_topics.map((t, i) => (
              <div key={i} className="pl-3 border-l-2" style={{ borderColor: '#E8830A' }}>
                <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>{t.topic}</p>
                <p className="text-xs mt-0.5" style={{ color: '#64748B' }}>{t.why}</p>
                <p className="text-xs mt-1" style={{ color: '#94A3B8' }}>{t.quick_revision_note}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {cs.missed_topics?.length > 0 && (
        <Section title="Missed Topics" color="#f87171">
          <div className="flex flex-wrap gap-2">
            {cs.missed_topics.map((t, i) => (
              <span key={i} className="tag tag-red">{t}</span>
            ))}
          </div>
        </Section>
      )}

      {cs.current_affairs_to_remember?.length > 0 && (
        <Section title="Current Affairs to Remember" color="#10B981">
          <div className="flex flex-col gap-3">
            {cs.current_affairs_to_remember.map((ca, i) => (
              <div key={i}>
                <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>{ca.headline}</p>
                <p className="text-xs mt-0.5" style={{ color: '#10B981' }}>{ca.upsc_angle}</p>
                {ca.probable_question && (
                  <p className="text-xs mt-0.5" style={{ color: '#64748B' }}>
                    ❓ {ca.probable_question}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {cs.prelims_fact_clusters?.length > 0 && (
        <Section title="Prelims Fact Clusters" color="#818cf8">
          <ul className="flex flex-col gap-1">
            {cs.prelims_fact_clusters.map((f, i) => (
              <li key={i} className="text-sm flex items-start gap-2" style={{ color: '#CBD5E1' }}>
                <span style={{ color: '#818cf8', marginTop: 2 }}>•</span> {f}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {cs.rapid_revision_prompts?.length > 0 && (
        <Section title="Rapid Revision Prompts" color="#E8830A">
          <ol className="flex flex-col gap-2">
            {cs.rapid_revision_prompts.map((q, i) => (
              <li key={i} className="text-sm" style={{ color: '#CBD5E1' }}>
                <span style={{ color: '#E8830A', fontWeight: 600 }}>{i + 1}. </span>{q}
              </li>
            ))}
          </ol>
        </Section>
      )}

      {cs.map_diagram_reminders?.length > 0 && (
        <Section title="Map / Diagram Reminders" color="#F5A623">
          <div className="flex flex-wrap gap-2">
            {cs.map_diagram_reminders.map((r, i) => (
              <span key={i} className="tag tag-saffron">{r}</span>
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}

export default function Revision() {
  const [mode,    setMode   ] = useState('weekly')
  const [data,    setData   ] = useState(null)
  const [loading, setLoading] = useState(false)
  const [topic,   setTopic  ] = useState('')
  const [depth,   setDepth  ] = useState('quick')

  const generate = async () => {
    setLoading(true)
    setData(null)
    try {
      let res
      if (mode === 'weekly')       res = await getWeeklyRevision()
      else if (mode === 'monthly') res = await getMonthlyRevision()
      else                         res = await getTopicRevision({ topic, depth })
      setData(res.data)
    } catch { }
    finally { setLoading(false) }
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8 animate-fade-up">
        <p className="text-xs tracking-widest uppercase mb-1" style={{ color: '#E8830A' }}>Study Planner</p>
        <h1 className="font-display text-4xl font-semibold" style={{ color: '#E2E8F0' }}>Revision</h1>
        <p className="mt-1 text-sm" style={{ color: '#64748B' }}>
          Personalised cheat sheets built from your study patterns
        </p>
      </div>

      <div className="card p-6 mb-6 animate-fade-up">
        <div className="flex gap-2 mb-4">
          {['weekly', 'monthly', 'topic'].map(m => (
            <button key={m} onClick={() => setMode(m)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all capitalize ${
                mode === m ? 'text-black' : 'btn-ghost'}`}
              style={mode === m ? { background: '#E8830A' } : {}}>
              {m}
            </button>
          ))}
        </div>

        {mode === 'topic' && (
          <div className="grid grid-cols-2 gap-4 mb-4">
            <input className="input" placeholder="Topic name (e.g. Federalism)"
              value={topic} onChange={e => setTopic(e.target.value)} />
            <select className="input" value={depth} onChange={e => setDepth(e.target.value)}>
              <option value="quick">Quick revision</option>
              <option value="deep">Deep notes</option>
            </select>
          </div>
        )}

        <button className="btn-primary flex items-center gap-2" onClick={generate}
          disabled={loading || (mode === 'topic' && !topic.trim())}>
          {loading ? <Loader size={14} className="animate-spin" /> : <BookOpen size={14} />}
          Generate {mode === 'weekly' ? 'Weekly' : mode === 'monthly' ? 'Monthly' : 'Topic'} Sheet
        </button>
      </div>

      {loading ? (
        <div className="flex flex-col gap-4">
          {[1,2,3].map(i => <div key={i} className="skeleton h-24" />)}
        </div>
      ) : data && (
        <div className="animate-fade-up">
          {data.period && (
            <div className="flex items-center gap-2 mb-4">
              <Calendar size={14} style={{ color: '#E8830A' }} />
              <p className="text-sm font-medium" style={{ color: '#E8830A' }}>{data.period}</p>
            </div>
          )}
          <CheatSheet data={data} />
        </div>
      )}
    </div>
  )
}
