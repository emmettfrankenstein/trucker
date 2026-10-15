import { decodePolyline } from './polyline'

test('decodes Google example polyline into [lon, lat] pairs', () => {
  expect(decodePolyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@')).toEqual([
    [-120.2, 38.5],
    [-120.95, 40.7],
    [-126.453, 43.252],
  ])
})
