import { useState, useCallback, createContext, useContext } from 'react'
import { AlertCircle, CheckCircle, Info, X } from 'lucide-react'

const ToastContext = createContext(null)

export function useToast() {
  return useContext(ToastContext)
}

let toastId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', duration = 5000) => {
    const id = ++toastId
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration)
    return id
  }, [])

  const toast = useCallback({
    success: (msg) => addToast(msg, 'success', 4000),
    error:   (msg) => addToast(msg, 'error',   6000),
    info:    (msg) => addToast(msg, 'info',     5000),
  }, [addToast])

  // Reassign as function with methods
  const toastFn = useCallback((msg, type) => addToast(msg, type), [addToast])
  toastFn.success = (msg) => addToast(msg, 'success', 4000)
  toastFn.error   = (msg) => addToast(msg, 'error', 6000)
  toastFn.info    = (msg) => addToast(msg, 'info', 5000)

  const dismiss = (id) => setToasts(prev => prev.filter(t => t.id !== id))

  const ICONS = {
    success: CheckCircle,
    error:   AlertCircle,
    info:    Info,
  }
  const COLORS = {
    success: { bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.3)',  text: '#10B981' },
    error:   { bg: 'rgba(248,113,113,0.12)', border: 'rgba(248,113,113,0.3)', text: '#f87171' },
    info:    { bg: 'rgba(232,131,10,0.12)',   border: 'rgba(232,131,10,0.3)',  text: '#E8830A' },
  }

  return (
    <ToastContext.Provider value={toastFn}>
      {children}
      {/* Toast container */}
      <div style={{
        position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
        display: 'flex', flexDirection: 'column', gap: 8, pointerEvents: 'none',
      }}>
        {toasts.map(t => {
          const Icon = ICONS[t.type] || Info
          const c = COLORS[t.type] || COLORS.info
          return (
            <div key={t.id} className="animate-fade-up"
              style={{
                background: c.bg, border: `1px solid ${c.border}`,
                borderRadius: 10, padding: '12px 16px',
                display: 'flex', alignItems: 'center', gap: 10,
                pointerEvents: 'auto', backdropFilter: 'blur(12px)',
                minWidth: 280, maxWidth: 420,
              }}>
              <Icon size={16} style={{ color: c.text, shrink: 0 }} />
              <p style={{ color: '#E2E8F0', fontSize: '0.85rem', flex: 1, margin: 0 }}>
                {t.message}
              </p>
              <button onClick={() => dismiss(t.id)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2 }}>
                <X size={12} style={{ color: '#64748B' }} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
