/** Decode a Google encoded polyline (precision 5) into [lon, lat] pairs for GeoJSON. */
export function decodePolyline(encoded) {
  const coords = []
  let index = 0
  let lat = 0
  let lon = 0
  while (index < encoded.length) {
    for (const axis of [0, 1]) {
      let shift = 0
      let result = 0
      let b
      do {
        b = encoded.charCodeAt(index++) - 63
        result |= (b & 0x1f) << shift
        shift += 5
      } while (b >= 0x20)
      const delta = result & 1 ? ~(result >> 1) : result >> 1
      if (axis === 0) lat += delta
      else lon += delta
    }
    coords.push([lon / 1e5, lat / 1e5])
  }
  return coords
}
