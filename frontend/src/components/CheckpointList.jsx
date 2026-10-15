import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material'
import { memo, useEffect, useMemo, useRef, useState } from 'react'

import { formatTime } from '../lib/format'
import { RISK_LEVELS, riskColor } from '../lib/risk'

const riskChipSx = (level) => ({
  bgcolor: riskColor(level),
  color: '#fff',
  height: 20,
  fontSize: 11,
  fontWeight: 600,
})

function CheckpointList({ route, activeSeq, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  const rowRefs = useRef({})

  // Picking a checkpoint on the map opens the table and brings that row into view.
  useEffect(() => {
    if (activeSeq == null) return
    setExpanded(true)
    const id = requestAnimationFrame(() =>
      rowRefs.current[activeSeq]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }),
    )
    return () => cancelAnimationFrame(id)
  }, [activeSeq])

  // Collapsed summary: how many checkpoints sit at each level above Low.
  const counts = useMemo(() => {
    const byLevel = new Map()
    route.checkpoints.forEach((cp) => byLevel.set(cp.risk_level, (byLevel.get(cp.risk_level) ?? 0) + 1))
    return RISK_LEVELS.filter((r) => r.level > 0 && byLevel.get(r.level)).map((r) => ({
      ...r,
      n: byLevel.get(r.level),
    }))
  }, [route])

  return (
    <Accordion
      expanded={expanded}
      onChange={(_, open) => setExpanded(open)}
      disableGutters
      variant="outlined"
      slotProps={{ transition: { unmountOnExit: true } }}
      sx={{ borderRadius: 1, '&:before': { display: 'none' } }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreIcon />}
        aria-controls="checkpoint-table"
        sx={{ minHeight: 44 }}
      >
        <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap sx={{ pr: 1 }}>
          <Typography variant="subtitle2">
            Route {route.label} checkpoints ({route.checkpoints.length})
          </Typography>
          {counts.length === 0 ? (
            <Typography variant="caption" color="text.secondary">
              all Low
            </Typography>
          ) : (
            counts.map((c) => (
              <Chip key={c.key} size="small" label={`${c.n} ${c.label}`} sx={riskChipSx(c.level)} />
            ))
          )}
        </Stack>
      </AccordionSummary>
      <AccordionDetails sx={{ p: 0 }} id="checkpoint-table">
        <TableContainer sx={{ maxHeight: { xs: 320, md: 'min(46vh, 420px)' } }}>
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
                    ref={(el) => (rowRefs.current[cp.seq] = el)}
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
                      <Chip label={cp.risk_label} size="small" sx={riskChipSx(cp.risk_level)} />
                    </TableCell>
                  </TableRow>
                </Tooltip>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', px: 1, py: 0.75 }}>
          Wind in mph, rain and snow in in/hr, forecast at the truck&apos;s ETA. Click a row to show it on the
          map.
        </Typography>
      </AccordionDetails>
    </Accordion>
  )
}

export default memo(CheckpointList)
