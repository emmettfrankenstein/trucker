const R_MI = 3958.7613
const rad = (d) => (d * Math.PI) / 180

export function haversineMi([lon1, lat1], [lon2, lat2]) {
  const h =
    Math.sin(rad(lat2 - lat1) / 2) ** 2 +
    Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2
  return 2 * R_MI * Math.asin(Math.sqrt(h))
}

function cumulative(coords) {
  const out = [0]
  for (let i = 1; i < coords.length; i++) out.push(out[i - 1] + haversineMi(coords[i - 1], coords[i]))
  return out
}

function pointAt(coords, cum, mile) {
  if (mile <= 0) return coords[0]
  const last = cum.length - 1
  if (mile >= cum[last]) return coords[last]
  let lo = 0
  let hi = last
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (cum[mid] <= mile) lo = mid
    else hi = mid
  }
  const t = (mile - cum[lo]) / (cum[hi] - cum[lo] || 1)
  const [x0, y0] = coords[lo]
  const [x1, y1] = coords[hi]
  return [x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]
}

/**
 * Cut a route line into the stretches each checkpoint represents, so the line itself
 * is coloured by risk. Checkpoint miles use the router's distance, so rescale to geometry.
 */
export function splitBySpans(coords, checkpoints, routeMiles) {
  const cum = cumulative(coords)
  const scale = routeMiles > 0 ? cum[cum.length - 1] / routeMiles : 1
  return checkpoints.map((cp) => {
    const start = cp.span_start_mi * scale
    const end = cp.span_end_mi * scale
    const inner = []
    for (let i = 0; i < coords.length; i++) if (cum[i] > start && cum[i] < end) inner.push(coords[i])
    return {
      coordinates: [pointAt(coords, cum, start), ...inner, pointAt(coords, cum, end)],
      level: cp.risk_level,
    }
  })
}

/** Where the truck is at ``time`` (ms), interpolated between checkpoint ETAs. */
export function positionAt(checkpoints, time) {
  if (!checkpoints?.length) return null
  const t = checkpoints.map((c) => Date.parse(c.eta))
  if (time < t[0]) return { lon: checkpoints[0].lon, lat: checkpoints[0].lat, status: 'before' }
  const last = checkpoints.length - 1
  if (time >= t[last]) return { lon: checkpoints[last].lon, lat: checkpoints[last].lat, status: 'arrived' }
  let i = 1
  while (t[i] <= time) i++
  const a = checkpoints[i - 1]
  const b = checkpoints[i]
  const f = (time - t[i - 1]) / (t[i] - t[i - 1] || 1)
  return { lon: a.lon + (b.lon - a.lon) * f, lat: a.lat + (b.lat - a.lat) * f, status: 'driving' }
}

export function boundsOf(coordsList) {
  let w = Infinity
  let s = Infinity
  let e = -Infinity
  let n = -Infinity
  for (const coords of coordsList)
    for (const [x, y] of coords) {
      if (x < w) w = x
      if (x > e) e = x
      if (y < s) s = y
      if (y > n) n = y
    }
  return [
    [w, s],
    [e, n],
  ]
}
