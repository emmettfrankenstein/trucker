import { Box, CircularProgress } from '@mui/material'
import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import TopBar from './components/TopBar'

// The planner pulls in the map engine, so it loads as its own chunk.
const PlannerPage = lazy(() => import('./pages/PlannerPage'))
const HistoryPage = lazy(() => import('./pages/HistoryPage'))

export default function App() {
  return (
    <Box sx={{ height: '100dvh', display: 'flex', flexDirection: 'column' }}>
      <TopBar />
      <Suspense
        fallback={
          <Box sx={{ flex: 1, display: 'grid', placeItems: 'center' }}>
            <CircularProgress />
          </Box>
        }
      >
        <Routes>
          <Route path="/" element={<PlannerPage />} />
          <Route path="/trips/:tripId" element={<PlannerPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Box>
  )
}
