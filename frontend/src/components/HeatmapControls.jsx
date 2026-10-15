import PauseIcon from '@mui/icons-material/Pause'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import {
  Box,
  FormControlLabel,
  IconButton,
  LinearProgress,
  Paper,
  Slider,
  Stack,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import dayjs from 'dayjs'
import { memo, useEffect } from 'react'

import { hourLabelTime } from '../lib/heatmap'
import { METRICS, RISK_LEVELS } from '../lib/risk'

const MARKS = [0, 12, 24, 36, 48].map((h) => ({ value: h }))
const FRAME_MS = 280

function Legend({ metric }) {
  const { stops, unit } = METRICS[metric]
  return (
    <Stack direction="row" spacing={0} sx={{ mt: 0.5 }}>
      {RISK_LEVELS.map((r, i) => (
        <Box key={r.key} sx={{ flex: 1 }}>
          <Box sx={{ height: 6, bgcolor: r.color, opacity: i === 0 ? 0.35 : 0.85 }} />
          <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10.5 }}>
            {metric === 'risk' ? r.label : `${i === 0 ? `< ${stops[1]}` : `≥ ${stops[i]}`} ${unit}`}
          </Typography>
        </Box>
      ))}
    </Stack>
  )
}

function HeatmapControls({
  heatmap,
  loading,
  error,
  hour,
  onHour,
  metric,
  onMetric,
  visible,
  onVisible,
  playing,
  onPlaying,
  truckStatus,
}) {
  // Advance one forecast hour per frame while playing; loops back to +0h at the end.
  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => onHour((h) => (h >= 48 ? 0 : h + 1)), FRAME_MS)
    return () => clearInterval(id)
  }, [playing, onHour])

  const time = heatmap ? dayjs(hourLabelTime(heatmap, hour)) : null

  return (
    <Paper sx={{ p: 1.5, pb: 1, border: '1px solid #e3e7ee', boxShadow: '0 4px 18px rgba(16,24,40,.12)' }}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <FormControlLabel
          control={<Switch size="small" checked={visible} onChange={(e) => onVisible(e.target.checked)} />}
          label={<Typography variant="subtitle2">Weather heatmap</Typography>}
          sx={{ mr: 0 }}
        />
        <Box sx={{ flex: 1 }} />
        <ToggleButtonGroup
          exclusive
          size="small"
          value={metric}
          onChange={(_, v) => v && onMetric(v)}
          aria-label="Heatmap metric"
        >
          {Object.entries(METRICS).map(([key, m]) => (
            <ToggleButton key={key} value={key} sx={{ py: 0.25, px: 1, fontSize: 12 }}>
              {m.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Stack>
      {loading && <LinearProgress sx={{ my: 1 }} />}
      {error && (
        <Typography variant="caption" color="error">
          Couldn&apos;t load the forecast grid. Routes and checkpoints are unaffected.
        </Typography>
      )}
      {heatmap && (
        <>
          <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mt: 0.5 }}>
            <IconButton
              size="small"
              color="primary"
              onClick={() => onPlaying(!playing)}
              aria-label={playing ? 'Pause forecast animation' : 'Play forecast animation'}
            >
              {playing ? <PauseIcon /> : <PlayArrowIcon />}
            </IconButton>
            <Slider
              value={hour}
              min={0}
              max={48}
              step={1}
              marks={MARKS}
              onChange={(_, v) => {
                onPlaying(false)
                onHour(v)
              }}
              valueLabelDisplay="auto"
              valueLabelFormat={(v) => `+${v}h`}
              aria-label="Forecast hour"
              size="small"
              sx={{ mx: 1 }}
            />
          </Stack>
          <Stack direction="row" justifyContent="space-between" alignItems="baseline">
            <Typography variant="body2">
              <b>{time.format('ddd MMM D, h:mm A')}</b>{' '}
              <Typography component="span" variant="caption" color="text.secondary">
                (+{hour}h from departure)
              </Typography>
            </Typography>
            {truckStatus && (
              <Typography variant="caption" color="text.secondary">
                {truckStatus}
              </Typography>
            )}
          </Stack>
          <Box sx={{ display: { xs: 'none', sm: 'block' } }}>
            <Legend metric={metric} />
          </Box>
        </>
      )}
    </Paper>
  )
}

export default memo(HeatmapControls)
