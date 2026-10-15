import { boundsOf, haversineMi, positionAt, splitBySpans } from './geometry'

const LINE = Array.from({ length: 11 }, (_, i) => [i * 0.1, 0]) // ~69 mi along the equator

test('haversine matches a known distance', () => {
  expect(haversineMi([-87.6298, 41.8781], [-104.9903, 39.7392])).toBeCloseTo(920, -1)
})

test('splitBySpans covers the line end to end with one segment per checkpoint', () => {
  const total = haversineMi(LINE[0], LINE[10])
  const checkpoints = [
    { span_start_mi: 0, span_end_mi: total / 2, risk_level: 0 },
    { span_start_mi: total / 2, span_end_mi: total, risk_level: 3 },
  ]
  const segs = splitBySpans(LINE, checkpoints, total)
  expect(segs).toHaveLength(2)
  expect(segs[0].coordinates[0]).toEqual(LINE[0])
  expect(segs[1].coordinates.at(-1)).toEqual(LINE[10])
  expect(segs[0].coordinates.at(-1)[0]).toBeCloseTo(0.5, 5)
  expect(segs[1].level).toBe(3)
})

test('splitBySpans rescales router miles onto geometry', () => {
  const total = haversineMi(LINE[0], LINE[10])
  const segs = splitBySpans(LINE, [{ span_start_mi: 0, span_end_mi: 50, risk_level: 1 }], 100)
  expect(segs[0].coordinates.at(-1)[0]).toBeCloseTo((0.5 * total) / total, 5)
})

test('positionAt interpolates between checkpoint ETAs', () => {
  const cps = [
    { lat: 0, lon: 0, eta: '2026-10-16T10:00:00Z' },
    { lat: 0, lon: 1, eta: '2026-10-16T12:00:00Z' },
  ]
  expect(positionAt(cps, Date.parse('2026-10-16T09:00:00Z')).status).toBe('before')
  const mid = positionAt(cps, Date.parse('2026-10-16T11:00:00Z'))
  expect(mid.lon).toBeCloseTo(0.5)
  expect(mid.status).toBe('driving')
  expect(positionAt(cps, Date.parse('2026-10-16T13:00:00Z')).status).toBe('arrived')
  expect(positionAt([], 0)).toBeNull()
})

test('boundsOf spans every route', () => {
  expect(
    boundsOf([
      [
        [0, 1],
        [2, 3],
      ],
      [[-1, 5]],
    ]),
  ).toEqual([
    [-1, 1],
    [2, 5],
  ])
})
