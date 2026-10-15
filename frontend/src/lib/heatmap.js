import { METRICS, RISK_LEVELS } from './risk'

/** Square cell polygons with numeric ids, so per-hour values can go into feature-state. */
export function cellsToGeoJSON(heatmap) {
  const half = heatmap.step_deg / 2
  return {
    type: 'FeatureCollection',
    features: heatmap.cells.map(([lat, lon], id) => ({
      type: 'Feature',
      id,
      properties: {},
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [lon - half, lat - half],
            [lon + half, lat - half],
            [lon + half, lat + half],
            [lon - half, lat + half],
            [lon - half, lat - half],
          ],
        ],
      },
    })),
  }
}

const COLORS = RISK_LEVELS.map((r) => r.color)

/** Fill colour driven by feature-state ``v``: steps for risk, a smooth ramp for raw values. */
export function fillColor(metric) {
  const value = ['coalesce', ['feature-state', 'v'], 0]
  const { stops } = METRICS[metric]
  if (metric === 'risk')
    return ['step', value, COLORS[0], 1, COLORS[1], 2, COLORS[2], 3, COLORS[3], 4, COLORS[4]]
  return ['interpolate', ['linear'], value, ...stops.flatMap((s, i) => [s, COLORS[i]])]
}

/** Calm cells stay faint so the base map and routes remain readable. */
export function fillOpacity(metric) {
  const value = ['coalesce', ['feature-state', 'v'], 0]
  const moderate = METRICS[metric].stops[1]
  return ['interpolate', ['linear'], value, 0, 0.06, moderate, 0.38, METRICS[metric].stops[4], 0.6]
}

export function hourLabelTime(heatmap, hour) {
  return Date.parse(heatmap.start) + hour * 3600 * 1000
}
