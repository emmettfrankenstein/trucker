import { Box, Stack, Tooltip, Typography } from '@mui/material'

import { RISK_LEVELS } from '../lib/risk'

export function RiskLegend() {
  return (
    <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap>
      {RISK_LEVELS.map((r) => (
        <Stack key={r.key} direction="row" spacing={0.5} alignItems="center">
          <Box sx={{ width: 10, height: 10, borderRadius: '2px', bgcolor: r.color }} />
          <Typography variant="caption" color="text.secondary">
            {r.label}
          </Typography>
        </Stack>
      ))}
    </Stack>
  )
}

/** Stacked bar of route miles by risk level. */
export default function RiskBar({ milesByLevel, height = 10 }) {
  const total = RISK_LEVELS.reduce((sum, r) => sum + (milesByLevel[r.key] ?? 0), 0) || 1
  return (
    <Box>
      <Box
        sx={{ display: 'flex', height, borderRadius: height / 2, overflow: 'hidden', bgcolor: 'grey.200' }}
        role="img"
        aria-label={RISK_LEVELS.map((r) => `${Math.round(milesByLevel[r.key] ?? 0)} miles ${r.label}`).join(
          ', ',
        )}
      >
        {RISK_LEVELS.map((r) => {
          const miles = milesByLevel[r.key] ?? 0
          if (miles <= 0) return null
          return (
            <Tooltip key={r.key} title={`${r.label}: ${Math.round(miles)} mi`} arrow>
              <Box sx={{ width: `${(miles / total) * 100}%`, bgcolor: r.color, minWidth: 3 }} />
            </Tooltip>
          )
        })}
      </Box>
    </Box>
  )
}
