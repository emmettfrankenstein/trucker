import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Paper,
  Typography,
} from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate, useNavigate } from 'react-router-dom'

import { errorMessage } from '../api/client'
import { deleteTrip, listTrips } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { formatDateTime, formatLoad } from '../lib/format'

export default function HistoryPage() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const trips = useQuery({ queryKey: ['trips'], queryFn: listTrips, enabled: Boolean(user) })
  const remove = useMutation({
    mutationFn: deleteTrip,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['trips'] }),
  })

  if (loading) return null
  if (!user) return <Navigate to="/" replace />

  return (
    <Box sx={{ flex: 1, overflowY: 'auto', p: { xs: 2, md: 4 } }}>
      <Paper sx={{ maxWidth: 760, mx: 'auto', p: 2, border: '1px solid #e3e7ee' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          My trips
        </Typography>
        {trips.isLoading && <CircularProgress size={24} />}
        {trips.isError && <Alert severity="error">{errorMessage(trips.error)}</Alert>}
        {trips.data?.length === 0 && (
          <Typography color="text.secondary">No saved trips yet. Plan one while signed in.</Typography>
        )}
        <List disablePadding>
          {trips.data?.map((t) => (
            <ListItem
              key={t.id}
              disablePadding
              secondaryAction={
                <IconButton edge="end" aria-label="Delete trip" onClick={() => remove.mutate(t.id)}>
                  <DeleteOutlineIcon />
                </IconButton>
              }
            >
              <ListItemButton onClick={() => navigate(`/trips/${t.id}`)}>
                <ListItemText
                  primary={`${t.origin_label} → ${t.destination_label}`}
                  secondary={`Departs ${formatDateTime(t.departure_at)} · ${formatLoad(t.load_weight_lb)} · every ${t.sample_interval_mi} mi`}
                />
                {!t.recommendation_safe && (
                  <Chip label="No safe route" color="error" size="small" sx={{ mr: 2 }} />
                )}
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Paper>
    </Box>
  )
}
