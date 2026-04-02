import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ToastProvider } from './components/Toast'
import Sidebar    from './components/Sidebar'
import Dashboard  from './pages/Dashboard'
import Chat       from './pages/Chat'
import Upload     from './pages/Upload'
import Newspaper  from './pages/Newspaper'
import Analytics  from './pages/Analytics'
import Revision   from './pages/Revision'
import Visuals    from './pages/Visuals'
import './styles/globals.css'

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <div className="flex min-h-screen noise">
          <Sidebar />
          <main className="flex-1 overflow-y-auto">
            <Routes>
              <Route path="/"          element={<Dashboard />} />
              <Route path="/chat"      element={<Chat />} />
              <Route path="/upload"    element={<Upload />} />
              <Route path="/newspaper" element={<Newspaper />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/revision"  element={<Revision />} />
              <Route path="/visuals"   element={<Visuals />} />
            </Routes>
          </main>
        </div>
      </ToastProvider>
    </BrowserRouter>
  )
}
