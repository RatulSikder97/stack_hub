import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Studio } from './pages/Studio'
import { LibraryPage } from './pages/Library'
import { PostDetailPage } from './pages/PostDetail'
import { TranslatePage } from './pages/Translate'
import { SettingsPage } from './pages/Settings'
import { ToastProvider } from './components/ToastProvider'

function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/studio" replace />} />
          <Route path="studio" element={<Studio />} />
          <Route path="library" element={<LibraryPage />} />
          <Route path="library/:postId" element={<PostDetailPage />} />
          <Route path="translate" element={<TranslatePage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/studio" replace />} />
        </Route>
      </Routes>
    </ToastProvider>
  )
}

export default App
