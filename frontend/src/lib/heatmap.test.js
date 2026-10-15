import { cellsToGeoJSON, fillColor, hourLabelTime } from './heatmap'

const HEATMAP = {
  start: '2026-10-16T10:00:00Z',
  step_deg: 0.5,
  cells: [
    [40, -100],
    [40.5, -100],
  ],
}

test('cells become square polygons with stable numeric ids for feature-state', () => {
  const fc = cellsToGeoJSON(HEATMAP)
  expect(fc.features.map((f) => f.id)).toEqual([0, 1])
  expect(fc.features[0].geometry.coordinates[0][0]).toEqual([-100.25, 39.75])
  expect(fc.features[0].geometry.coordinates[0][2]).toEqual([-99.75, 40.25])
})

test('risk uses discrete steps, raw metrics a ramp on the rule thresholds', () => {
  expect(fillColor('risk')[0]).toBe('step')
  const wind = fillColor('wind')
  expect(wind[0]).toBe('interpolate')
  expect(wind.filter((x) => typeof x === 'number')).toEqual([0, 25, 35, 45, 55])
})

test('hour index maps to wall-clock time', () => {
  expect(new Date(hourLabelTime(HEATMAP, 3)).toISOString()).toBe('2026-10-16T13:00:00.000Z')
})
