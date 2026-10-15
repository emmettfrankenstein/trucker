import StarIcon from '@mui/icons-material/Star'
import { Box, Card, CardActionArea, Chip, Stack, Typography } from '@mui/material'
import { memo } from 'react'

import { formatDuration, formatMiles } from '../lib/format'
import { riskColor } from '../lib/risk'
import RiskBar from './RiskBar'

function RouteCard({ route, selected, onSelect, onHover }) {
  return (
    <Card
      sx={{
        borderColor: selected ? 'primary.main' : undefined,
        boxShadow: selected ? '0 0 0 1px #0b5cad' : 'none',
        transition: 'box-shadow 120ms, border-color 120ms',
      }}
      onMouseEnter={() => onHover?.(route.label)}
      onMouseLeave={() => onHover?.(null)}
    >
      <CardActionArea onClick={() => onSelect(route.label)} sx={{ p: 1.5 }} aria-pressed={selected}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
          <Box
            sx={{
              width: 26,
              height: 26,
              borderRadius: '50%',
              display: 'grid',
              placeItems: 'center',
              fontWeight: 700,
              fontSize: 13,
              color: '#fff',
              bgcolor: riskColor(route.max_level),
            }}
          >
            {route.label}
          </Box>
          <Typography variant="subtitle2" sx={{ flex: 1 }}>
            Route {route.label}
          </Typography>
          {route.is_recommended && (
            <Chip icon={<StarIcon />} label="Recommended" color="success" size="small" />
          )}
          {!route.is_recommended && (
            <Typography variant="caption" color="text.secondary">
              #{route.rank}
            </Typography>
          )}
        </Stack>
        <Stack direction="row" spacing={2} sx={{ mb: 1 }}>
          <Typography variant="body2">
            <b>{formatDuration(route.duration_s)}</b>
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {formatMiles(route.distance_mi)}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            avg risk {route.avg_risk.toFixed(2)}
          </Typography>
        </Stack>
        <RiskBar milesByLevel={route.miles_by_level} />
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.75 }}>
          {route.summary}
        </Typography>
      </CardActionArea>
    </Card>
  )
}

export default memo(RouteCard)
