import { Alert, Box, Divider, LinearProgress, Paper, Skeleton, Stack, Typography } from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { errorMessage } from '../api/client'
import { getHeatmap, getTrip, planTrip } from '../api/endpoints'
import CheckpointList from '../components/CheckpointList'
import HeatmapControls from '../components/HeatmapControls'
import MapView from '../components/MapView'
import RecommendationBanner from '../components/RecommendationBanner'
import { RiskLegend } from '../components/RiskBar'
import RouteCard from '../components/RouteCard'
import TripForm from '../components/TripForm'
import { formatDateTime, formatLoad } from '../lib/format'
import { positionAt } from '../lib/geometry'
import { hourLabelTime } from '../lib/heatmap'
import { decodePolyline } from '../lib/polyline'

function ResultsSkeleton() {
  return (
    <Stack spacing={1.5}>
      <Skeleton variant="rounded" height={64} />
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} variant="rounded" height={108} />
      ))}
    </Stack>
  )
}

export default function PlannerPage() {
  const { tripId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const tripQuery = useQuery({
    queryKey: ['trip', tripId],
    queryFn: () => getTrip(tripId),
    enabled: Boolean(tripId),
    staleTime: Infinity,
  })
  const trip = tripId ? tripQuery.data : null

  // The heatmap is fetched separately so routes paint first; it never refetches for a trip.
  const heatmapQuery = useQuery({
    queryKey: ['heatmap', tripId],
    queryFn: () => getHeatmap(tripId),
    enabled: Boolean(trip),
    staleTime: Infinity,
    retry: 1,
  })

  const plan = useMutation({
    mutationFn: planTrip,
    onSuccess: (data) => {
      queryClient.setQueryData(['trip', data.id], data)
      queryClient.invalidateQueries({ queryKey: ['trips'] })
      navigate(`/trips/${data.id}`)
    },
  })

  const [selected, setSelected] = useState(null)
  const [hovered, setHovered] = useState(null)
  const [activeCheckpoint, setActiveCheckpoint] = useState(null)
  const [hour, setHour] = useState(0)
  const [metric, setMetric] = useState('risk')
  const [heatVisible, setHeatVisible] = useState(true)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    setSelected(trip?.recommendation.route ?? null)
    setActiveCheckpoint(null)
    setHour(0)
    setPlaying(false)
  }, [trip])

  const routeCoords = useMemo(
    () => Object.fromEntries((trip?.routes ?? []).map((r) => [r.label, decodePolyline(r.geometry)])),
    [trip],
  )
  const selectedRoute = trip?.routes.find((r) => r.label === selected)
  const sortedRoutes = useMemo(() => [...(trip?.routes ?? [])].sort((a, b) => a.rank - b.rank), [trip])

  const heatmap = heatmapQuery.data
  const truck = useMemo(() => {
    if (!heatmap || !selectedRoute) return null
    return positionAt(selectedRoute.checkpoints, hourLabelTime(heatmap, hour))
  }, [heatmap, selectedRoute, hour])
  const truckStatus =
    truck &&
    { before: 'Truck not departed yet', driving: `Truck on Route ${selected}`, arrived: 'Truck has arrived' }[
      truck.status
    ]

  const selectRoute = useCallback((label) => {
    setSelected(label)
    setActiveCheckpoint(null)
  }, [])

  return (
    <Box
      sx={{
        flex: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        overflowY: { xs: 'auto', md: 'hidden' },
      }}
    >
      <Paper
        square
        sx={{
          width: { xs: '100%', md: 420 },
          flexShrink: 0,
          borderRight: { md: '1px solid #e3e7ee' },
          overflowY: 'auto',
          order: { xs: 2, md: 1 },
        }}
      >
        {plan.isPending && <LinearProgress />}
        <Stack spacing={2} sx={{ p: 2 }}>
          <TripForm trip={trip} onSubmit={plan.mutate} busy={plan.isPending} />

          {plan.isError && <Alert severity="error">{errorMessage(plan.error)}</Alert>}
          {tripQuery.isError && <Alert severity="error">{errorMessage(tripQuery.error)}</Alert>}

          {(plan.isPending || (tripId && tripQuery.isLoading)) && <ResultsSkeleton />}

          {trip && !plan.isPending && (
            <>
              <Divider />
              <Typography variant="caption" color="text.secondary">
                {trip.origin.label} → {trip.destination.label} · departs {formatDateTime(trip.departure_at)} ·{' '}
                {formatLoad(trip.load_weight_lb)} · every {trip.sample_interval_mi} mi
              </Typography>
              <RecommendationBanner recommendation={trip.recommendation} />
              <Stack spacing={1}>
                {sortedRoutes.map((route) => (
                  <RouteCard
                    key={route.label}
                    route={route}
                    selected={route.label === selected}
                    onSelect={selectRoute}
                    onHover={setHovered}
                  />
                ))}
              </Stack>
              <RiskLegend />
              {selectedRoute && (
                <CheckpointList
                  route={selectedRoute}
                  activeSeq={activeCheckpoint?.seq}
                  onSelect={setActiveCheckpoint}
                />
              )}
            </>
          )}

          {!tripId && !plan.isPending && (
            <Typography variant="body2" color="text.secondary">
              Enter a trip to compare three truck routes. Each route is checked against the forecast at the
              time the truck reaches every checkpoint, then ranked by Severe miles, High miles, average risk
              and travel time.
            </Typography>
          )}
        </Stack>
      </Paper>

      <Box
        sx={{
          position: 'relative',
          flex: { md: 1 },
          display: 'flex',
          flexDirection: 'column',
          order: { xs: 1, md: 2 },
          flexShrink: 0,
        }}
      >
        <Box sx={{ flex: 1, height: { xs: '52dvh', md: 'auto' } }}>
          <MapView
            trip={plan.isPending ? null : trip}
            routeCoords={routeCoords}
            selected={selected}
            hovered={hovered}
            onSelectRoute={selectRoute}
            activeCheckpoint={activeCheckpoint}
            onCheckpoint={setActiveCheckpoint}
            heatmap={plan.isPending ? null : heatmap}
            heatmapVisible={heatVisible}
            hour={hour}
            metric={metric}
            truck={truck}
          />
        </Box>
        {trip && !plan.isPending && (
          <Box
            sx={{
              position: { xs: 'static', md: 'absolute' },
              left: 12,
              right: 12,
              bottom: 28,
              maxWidth: { md: 560 },
              mx: 'auto',
              width: { xs: '100%', md: 'auto' },
              p: { xs: 1, md: 0 },
            }}
          >
            <HeatmapControls
              heatmap={heatmap}
              loading={heatmapQuery.isLoading}
              error={heatmapQuery.isError}
              hour={hour}
              onHour={setHour}
              metric={metric}
              onMetric={setMetric}
              visible={heatVisible}
              onVisible={setHeatVisible}
              playing={playing}
              onPlaying={setPlaying}
              truckStatus={truckStatus}
            />
          </Box>
        )}
      </Box>
    </Box>
  )
}
