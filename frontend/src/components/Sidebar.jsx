import { NavLink } from 'react-router-dom'
import {
  Brain, Upload, MessageSquare, BarChart2,
  BookOpen, Image, Newspaper, Home, Zap
} from 'lucide-react'

const NAV = [
  { to: '/',           icon: Home,          label: 'Dashboard'     },
  { to: '/chat',       icon: MessageSquare, label: 'Ask & Learn'   },
  { to: '/upload',     icon: Upload,        label: 'Upload'        },
  { to: '/newspaper',  icon: Newspaper,     label: 'Daily Briefing' },
  { to: '/analytics',  icon: BarChart2,     label: 'Analytics'     },
  { to: '/revision',   icon: BookOpen,      label: 'Revision'      },
  { to: '/visuals',    icon: Image,         label: 'Maps & Visuals' },
]

export default function Sidebar() {
  return (
    <aside style={{ width: 220, minHeight: '100vh', borderRight: '1px solid rgba(255,255,255,0.06)' }}
      className="flex flex-col bg-[#080D18] py-6 px-3 shrink-0">

      {/* Logo */}
      <div className="px-3 mb-8">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, #E8830A, #C4700A)' }}>
            <Brain size={16} color="#000" />
          </div>
          <div>
            <p className="font-display font-semibold text-sm leading-tight" style={{ color: '#E2E8F0' }}>
              UPSC Intel
            </p>
            <p className="text-[10px]" style={{ color: '#64748B' }}>Study System</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 flex-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} end={to === '/'}
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
            <Icon size={15} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 pt-4 border-t border-white/5">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs" style={{ color: '#64748B' }}>System Online</span>
        </div>
      </div>
    </aside>
  )
}
