import { useState, useRef, useEffect } from 'react'
import { sendQuery, startConversation, getProbableQs, writeAnswer } from '../utils/api'
import { Send, Loader, Brain, BookOpen, Target, Map, TrendingUp, PenLine, Zap } from 'lucide-react'

const INTENT_ICONS = {
  'Concept Query':      Brain,
  'PYQ Search':         BookOpen,
  'Probable Questions': Target,
  'Map Query':          Map,
  'Trend Analysis':     TrendingUp,
  'Answer Writing':     PenLine,
  'Weakness Check':     Zap,
}

const QUICK_PROMPTS = [
  'Explain Indian Federalism with constitutional provisions and recent issues',
  'What are recurring PYQ themes in GS2 Polity from 2016–2025?',
  'Give me 5 probable questions on Indus Valley Civilization',
  'Write a 250-word mains answer on demand and supply with current affairs',
  'Which topics am I lagging in?',
  'Give me my weekly revision cheat sheet',
]

function AnswerBlock({ data, intent }) {
  if (!data || Object.keys(data).length === 0) return null

  // Concept query response
  if (data.concept_explanation) return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-xs uppercase tracking-widest mb-2" style={{ color: '#E8830A' }}>Concept</p>
        <p className="text-sm leading-relaxed" style={{ color: '#E2E8F0' }}>{data.concept_explanation}</p>
      </div>
      {data.mains_dimensions?.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: '#64748B' }}>Mains Dimensions</p>
          <ul className="flex flex-col gap-1">
            {data.mains_dimensions.map((d, i) => (
              <li key={i} className="flex items-start gap-2 text-sm" style={{ color: '#CBD5E1' }}>
                <span style={{ color: '#E8830A', marginTop: 2 }}>›</span> {d}
              </li>
            ))}
          </ul>
        </div>
      )}
      {data.prelims_key_facts?.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: '#64748B' }}>Prelims Facts</p>
          <ul className="flex flex-col gap-1">
            {data.prelims_key_facts.map((f, i) => (
              <li key={i} className="flex items-start gap-2 text-sm" style={{ color: '#CBD5E1' }}>
                <span style={{ color: '#10B981', marginTop: 2 }}>•</span> {f}
              </li>
            ))}
          </ul>
        </div>
      )}
      {data.current_affairs_linkage && (
        <div className="card p-3" style={{ borderColor: 'rgba(16,185,129,0.2)' }}>
          <p className="text-xs uppercase tracking-widest mb-1" style={{ color: '#10B981' }}>CA Linkage</p>
          <p className="text-sm" style={{ color: '#CBD5E1' }}>{data.current_affairs_linkage}</p>
        </div>
      )}
    </div>
  )

  // Mains answer
  if (data.introduction) return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-xs uppercase tracking-widest mb-2" style={{ color: '#E8830A' }}>Introduction</p>
        <p className="text-sm leading-relaxed" style={{ color: '#E2E8F0' }}>{data.introduction}</p>
      </div>
      {data.body_points?.map((bp, i) => (
        <div key={i}>
          <p className="text-xs font-semibold mb-1" style={{ color: '#E8830A' }}>
            {i + 1}. {bp.heading}
          </p>
          <p className="text-sm leading-relaxed" style={{ color: '#CBD5E1' }}>{bp.content}</p>
        </div>
      ))}
      {data.conclusion && (
        <div>
          <p className="text-xs uppercase tracking-widest mb-2" style={{ color: '#E8830A' }}>Conclusion</p>
          <p className="text-sm leading-relaxed" style={{ color: '#E2E8F0' }}>{data.conclusion}</p>
        </div>
      )}
      {data.diagram_suggestion && (
        <div className="flex items-center gap-2 text-xs" style={{ color: '#818cf8' }}>
          <Map size={12} /> Diagram suggestion: {data.diagram_suggestion}
        </div>
      )}
    </div>
  )

  // Probable questions
  if (data.questions) return (
    <div className="flex flex-col gap-3">
      {data.questions.map((q, i) => (
        <div key={i} className="card p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className={`tag ${q.type === 'Mains' ? 'tag-saffron' : 'tag-blue'}`}>{q.type}</span>
            <span className={`tag ${q.probability === 'High' ? 'tag-emerald' : 'tag-saffron'}`}>{q.probability}</span>
          </div>
          <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>{q.question}</p>
          <p className="text-xs mt-1" style={{ color: '#64748B' }}>{q.reasoning}</p>
        </div>
      ))}
    </div>
  )

  // Weakness / generic JSON
  if (data.priority_order || data.overall_message) return (
    <div className="flex flex-col gap-3">
      {data.overall_message && (
        <p className="text-sm leading-relaxed" style={{ color: '#E2E8F0' }}>{data.overall_message}</p>
      )}
      {data.critical_gaps?.map((g, i) => (
        <div key={i} className="card p-3" style={{ borderColor: 'rgba(239,68,68,0.2)' }}>
          <p className="text-sm font-medium" style={{ color: '#f87171' }}>{g.topic} — {g.subtopic}</p>
          <p className="text-xs mt-1" style={{ color: '#64748B' }}>{g.why_critical}</p>
          <p className="text-xs mt-1" style={{ color: '#E8830A' }}>→ {g.recommended_action}</p>
        </div>
      ))}
    </div>
  )

  // Cheat sheet
  if (data.cheatsheet?.high_priority_topics) {
    const cs = data.cheatsheet
    return (
      <div className="flex flex-col gap-4">
        {cs.high_priority_topics?.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-widest mb-2" style={{ color: '#E8830A' }}>High Priority</p>
            {cs.high_priority_topics.map((t, i) => (
              <div key={i} className="mb-2">
                <p className="text-sm font-medium" style={{ color: '#E2E8F0' }}>{t.topic}</p>
                <p className="text-xs" style={{ color: '#64748B' }}>{t.quick_revision_note}</p>
              </div>
            ))}
          </div>
        )}
        {cs.rapid_revision_prompts?.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-widest mb-2" style={{ color: '#64748B' }}>Practice Questions</p>
            <ul className="flex flex-col gap-1">
              {cs.rapid_revision_prompts.map((q, i) => (
                <li key={i} className="text-sm" style={{ color: '#CBD5E1' }}>
                  <span style={{ color: '#E8830A' }}>{i+1}.</span> {q}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    )
  }

  // Fallback: render as text
  return (
    <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: '#E2E8F0' }}>
      {JSON.stringify(data, null, 2)}
    </p>
  )
}

function MessageBubble({ msg }) {
  const IntentIcon = INTENT_ICONS[msg.intent] || Brain
  return (
    <div className={`flex flex-col gap-1 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
      {msg.role === 'user' ? (
        <div className="bubble-user">
          <p className="text-sm" style={{ color: '#E2E8F0' }}>{msg.content}</p>
        </div>
      ) : (
        <div className="bubble-ai w-full">
          {msg.intent && (
            <div className="flex items-center gap-1.5 mb-3 pb-2"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              <IntentIcon size={12} style={{ color: '#E8830A' }} />
              <span className="text-[10px] uppercase tracking-widest" style={{ color: '#E8830A' }}>
                {msg.intent}
              </span>
            </div>
          )}
          <AnswerBlock data={msg.content} intent={msg.intent} />
          {/* Sources */}
          {msg.sources && (
            <div className="flex gap-3 mt-3 pt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
              {msg.sources.chunks?.length > 0 && (
                <span className="text-[10px]" style={{ color: '#64748B' }}>
                  📄 {msg.sources.chunks.length} chunks
                </span>
              )}
              {msg.sources.pyqs?.length > 0 && (
                <span className="text-[10px]" style={{ color: '#64748B' }}>
                  📋 {msg.sources.pyqs.length} PYQs
                </span>
              )}
              {msg.sources.current_affairs?.length > 0 && (
                <span className="text-[10px]" style={{ color: '#64748B' }}>
                  📰 {msg.sources.current_affairs.length} CA
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages]       = useState([])
  const [query, setQuery]             = useState('')
  const [loading, setLoading]         = useState(false)
  const [convId, setConvId]           = useState(null)
  const bottomRef                     = useRef(null)
  const inputRef                      = useRef(null)

  // Start a conversation session on mount
  useEffect(() => {
    startConversation()
      .then(r => setConvId(r.data.conversation_id))
      .catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async (text) => {
    const q = text || query.trim()
    if (!q || loading) return
    setQuery('')

    setMessages(prev => [...prev, { role: 'user', content: q }])
    setLoading(true)

    try {
      const res = await sendQuery({ query: q, conversation_id: convId })
      const d   = res.data
      setMessages(prev => [...prev, {
        role: 'ai',
        intent: d.intent,
        content: d.answer,
        sources: d.sources,
      }])
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'ai',
        content: { concept_explanation: 'Something went wrong. Please try again.' },
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="px-8 py-5 border-b shrink-0" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
        <h2 className="font-display text-2xl font-semibold" style={{ color: '#E2E8F0' }}>
          Ask & Learn
        </h2>
        <p className="text-xs mt-0.5" style={{ color: '#64748B' }}>
          Ask anything — concepts, PYQs, answers, maps, trends, revision
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {messages.length === 0 ? (
          <div className="animate-fade-up">
            <p className="text-xs uppercase tracking-widest mb-4" style={{ color: '#64748B' }}>
              Try asking
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {QUICK_PROMPTS.map((p, i) => (
                <button key={i} onClick={() => send(p)}
                  className="card p-4 text-left hover:border-orange-500/30 transition-colors"
                  style={{ animationDelay: `${i * 50}ms` }}>
                  <p className="text-sm" style={{ color: '#CBD5E1' }}>{p}</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-5 max-w-3xl mx-auto">
            {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
            {loading && (
              <div className="bubble-ai flex items-center gap-2">
                <Loader size={14} style={{ color: '#E8830A' }} className="animate-spin" />
                <span className="text-sm typing" style={{ color: '#64748B' }}>Thinking</span>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-8 py-5 border-t shrink-0" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
        <div className="max-w-3xl mx-auto flex gap-3">
          <input
            ref={inputRef}
            className="input flex-1"
            placeholder="Ask anything about UPSC…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            disabled={loading}
          />
          <button className="btn-primary flex items-center gap-2" onClick={() => send()} disabled={loading}>
            {loading
              ? <Loader size={15} className="animate-spin" />
              : <Send size={15} />}
            <span>Send</span>
          </button>
        </div>
      </div>
    </div>
  )
}
