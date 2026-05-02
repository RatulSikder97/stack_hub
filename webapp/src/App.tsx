import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { RequireAdmin, RequireAuth } from './components/RequireAuth'
import { ToastProvider } from './components/ToastProvider'
import { AdminPage } from './pages/Admin'
import { HomePage } from './pages/Home'
import { LibraryPage } from './pages/Library'
import { LoginPage } from './pages/Login'
import { MeetingsPage } from './pages/Meetings'
import { PostDetailPage } from './pages/PostDetail'
import { SettingsPage } from './pages/Settings'
import { Studio } from './pages/Studio'
import { TranslatePage } from './pages/Translate'

function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/home" replace />} />
            <Route path="home" element={<HomePage />} />
            <Route path="studio" element={<Studio />} />
            <Route path="library" element={<LibraryPage />} />
            <Route path="library/:postId" element={<PostDetailPage />} />
            <Route path="meetings" element={<MeetingsPage />} />
            <Route path="translate" element={<TranslatePage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route element={<RequireAdmin />}>
              <Route path="admin" element={<AdminPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/home" replace />} />
          </Route>
        </Route>
      </Routes>
    </ToastProvider>
  )
}

export default App
