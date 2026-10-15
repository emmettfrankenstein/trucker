import RouteIcon from '@mui/icons-material/AltRoute'
import SwapVertIcon from '@mui/icons-material/SwapVert'
import {
  Box,
  Button,
  Chip,
  IconButton,
  InputAdornment,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material'
import { DateTimePicker } from '@mui/x-date-pickers'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'

import PlaceAutocomplete from './PlaceAutocomplete'

const SAMPLES = [
  {
    name: 'Denver → Salt Lake City',
    origin: { label: 'Denver, CO', lat: 39.7392, lon: -104.9903 },
    destination: { label: 'Salt Lake City, UT', lat: 40.7608, lon: -111.891 },
  },
  {
    name: 'Chicago → Minneapolis',
    origin: { label: 'Chicago, IL', lat: 41.8781, lon: -87.6298 },
    destination: { label: 'Minneapolis, MN', lat: 44.9778, lon: -93.265 },
  },
  {
    name: 'Dallas → Atlanta',
    origin: { label: 'Dallas, TX', lat: 32.7767, lon: -96.797 },
    destination: { label: 'Atlanta, GA', lat: 33.749, lon: -84.388 },
  },
]

const nextHour = () => dayjs().add(1, 'hour').startOf('hour')

function fromTrip(trip) {
  return {
    origin: trip.origin,
    destination: trip.destination,
    departure: dayjs(trip.departure_at).isBefore(dayjs()) ? nextHour() : dayjs(trip.departure_at),
    load: String(trip.load_weight_lb),
    interval: trip.sample_interval_mi,
  }
}

export default function TripForm({ trip, onSubmit, busy }) {
  const [form, setForm] = useState(() =>
    trip
      ? fromTrip(trip)
      : { origin: null, destination: null, departure: nextHour(), load: '36000', interval: 25 },
  )
  const [touched, setTouched] = useState(false)

  useEffect(() => {
    if (trip) setForm(fromTrip(trip))
  }, [trip])

  const set = (field) => (value) => setForm((f) => ({ ...f, [field]: value }))
  const load = Number(form.load)
  const errors = {
    origin: !form.origin && 'Pick an origin from the list',
    destination: !form.destination && 'Pick a destination from the list',
    load: !(load >= 1 && load <= 200_000) && 'Enter a weight between 1 and 200,000 lb',
    departure:
      (!form.departure?.isValid() && 'Pick a departure time') ||
      (form.departure.isBefore(dayjs().subtract(1, 'hour')) && 'Departure is in the past') ||
      (form.departure.isAfter(dayjs().add(7, 'day')) && 'Forecasts reach 7 days ahead at most'),
  }
  const valid = !Object.values(errors).some(Boolean)

  function submit(e) {
    e.preventDefault()
    setTouched(true)
    if (!valid) return
    onSubmit({
      origin: form.origin,
      destination: form.destination,
      departure_at: form.departure.toISOString(),
      load_weight_lb: load,
      sample_interval_mi: form.interval,
    })
  }

  const show = (field) => touched && errors[field]

  return (
    <Box component="form" onSubmit={submit} noValidate>
      <Stack spacing={1.5}>
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Stack spacing={1.5} sx={{ flex: 1 }}>
            <PlaceAutocomplete
              label="Origin"
              value={form.origin}
              onChange={set('origin')}
              error={Boolean(show('origin'))}
              helperText={show('origin') || undefined}
            />
            <PlaceAutocomplete
              label="Destination"
              value={form.destination}
              onChange={set('destination')}
              error={Boolean(show('destination'))}
              helperText={show('destination') || undefined}
            />
          </Stack>
          <Tooltip title="Swap origin and destination">
            <IconButton
              aria-label="Swap origin and destination"
              onClick={() => setForm((f) => ({ ...f, origin: f.destination, destination: f.origin }))}
            >
              <SwapVertIcon />
            </IconButton>
          </Tooltip>
        </Stack>

        <DateTimePicker
          label="Departure"
          value={form.departure}
          onChange={set('departure')}
          minDateTime={dayjs().subtract(1, 'hour')}
          maxDateTime={dayjs().add(7, 'day')}
          slotProps={{
            textField: {
              size: 'small',
              fullWidth: true,
              error: Boolean(show('departure')),
              helperText: show('departure') || undefined,
            },
          }}
        />

        <Stack direction="row" spacing={1} alignItems="flex-start">
          <TextField
            label="Load weight"
            type="number"
            size="small"
            value={form.load}
            onChange={(e) => set('load')(e.target.value)}
            error={Boolean(show('load'))}
            helperText={show('load') || undefined}
            sx={{ flex: 1 }}
            slotProps={{
              input: { endAdornment: <InputAdornment position="end">lb</InputAdornment> },
              htmlInput: { min: 1, step: 500 },
            }}
          />
          <Tooltip title="Weather checkpoint spacing along each route">
            <ToggleButtonGroup
              exclusive
              size="small"
              value={form.interval}
              onChange={(_, v) => v && set('interval')(v)}
              aria-label="Checkpoint interval"
            >
              {[10, 25, 50].map((mi) => (
                <ToggleButton key={mi} value={mi} sx={{ px: 1.25, height: 40 }}>
                  {mi} mi
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
          </Tooltip>
        </Stack>

        <Button type="submit" variant="contained" size="large" startIcon={<RouteIcon />} disabled={busy}>
          {busy ? 'Checking routes and weather…' : 'Find the safest route'}
        </Button>

        {!trip && (
          <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
            <Typography variant="caption" color="text.secondary" sx={{ width: '100%' }}>
              Try a sample:
            </Typography>
            {SAMPLES.map((s) => (
              <Chip
                key={s.name}
                label={s.name}
                size="small"
                variant="outlined"
                onClick={() => setForm((f) => ({ ...f, origin: s.origin, destination: s.destination }))}
              />
            ))}
          </Stack>
        )}
      </Stack>
    </Box>
  )
}
