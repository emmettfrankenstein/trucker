import {
  Box,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material'
import { memo } from 'react'

import { formatTime } from '../lib/format'
import { riskColor } from '../lib/risk'

function CheckpointList({ route, activeSeq, onSelect }) {
  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
        Route {route.label} checkpoints ({route.checkpoints.length})
      </Typography>
      <Table size="small" stickyHeader sx={{ '& td, & th': { px: 0.75, py: 0.5, fontSize: 12.5 } }}>
        <TableHead>
          <TableRow>
            <TableCell>Mile</TableCell>
            <TableCell>ETA</TableCell>
            <TableCell align="right">Wind</TableCell>
            <TableCell align="right">Rain</TableCell>
            <TableCell align="right">Snow</TableCell>
            <TableCell>Risk</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {route.checkpoints.map((cp) => (
            <Tooltip
              key={cp.seq}
              title={cp.reasons.join(' · ') || 'No weather concerns'}
              placement="right"
              arrow
            >
              <TableRow
                hover
                selected={cp.seq === activeSeq}
                onClick={() => onSelect(cp)}
                sx={{ cursor: 'pointer' }}
              >
                <TableCell>{Math.round(cp.mile)}</TableCell>
                <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatTime(cp.eta)}</TableCell>
                <TableCell align="right">{Math.round(cp.wind_mph)}</TableCell>
                <TableCell align="right">{cp.rain_in_hr.toFixed(2)}</TableCell>
                <TableCell align="right">{cp.snow_in_hr.toFixed(2)}</TableCell>
                <TableCell>
                  <Stack direction="row">
                    <Chip
                      label={cp.risk_label}
                      size="small"
                      sx={{
                        bgcolor: riskColor(cp.risk_level),
                        color: '#fff',
                        height: 20,
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    />
                  </Stack>
                </TableCell>
              </TableRow>
            </Tooltip>
          ))}
        </TableBody>
      </Table>
      <Typography variant="caption" color="text.secondary">
        Wind in mph, rain and snow in in/hr, forecast at the truck&apos;s ETA.
      </Typography>
    </Box>
  )
}

export default memo(CheckpointList)
