import 'maplibre-gl/dist/maplibre-gl.css'

import FlagIcon from '@mui/icons-material/Flag'
import TripOriginIcon from '@mui/icons-material/TripOrigin'
import { Box, Divider, Typography } from '@mui/material'
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Map, { Layer, Marker, NavigationControl, Popup, ScaleControl, Source } from 'react-map-gl/maplibre'

import { formatTime } from '../lib/format'
import { boundsOf, splitBySpans } from '../lib/geometry'
import { cellsToGeoJSON, fillColor, fillOpacity } from '../lib/heatmap'
import { riskColor } from '../lib/risk'

const BASEMAP = 'https://tiles.openfreemap.org/styles/positron'
const INITIAL_VIEW = { longitude: -96, latitude: 38.5, zoom: 3.6 }
const INTERACTIVE = ['checkpoints', 'route-lines']

// Zoom must be the top-level interpolation input, so the casing gets its own expression.
function widthExpr(emphasised, extra) {
  const isEmphasised = ['==', ['get', 'label'], emphasised ?? '']
  return [
    'interpolate',
    ['linear'],
    ['zoom'],
    4,
    ['case', isEmphasised, 5 + extra, 2.5 + extra],
    10,
    ['case', isEmphasised, 9 + extra, 4.5 + extra],
  ]
}

function Pin({ color, icon }) {
  return (
    <Box
      sx={{
        width: 26,
        height: 26,
        borderRadius: '50% 50% 50% 0',
        transform: 'rotate(-45deg)',
        bgcolor: color,
        border: '2px solid #fff',
        boxShadow: 2,
        display: 'grid',
        placeItems: 'center',
      }}
    >
      <Box sx={{ transform: 'rotate(45deg)', color: '#fff', display: 'flex', '& svg': { fontSize: 14 } }}>
        {icon}
      </Box>
    </Box>
  )
}

function CheckpointPopup({ route, cp, onClose }) {
  return (
    <Popup
      longitude={cp.lon}
      latitude={cp.lat}
      onClose={onClose}
      closeOnClick={false}
      maxWidth="260px"
      offset={10}
    >
      <Box sx={{ fontFamily: 'Inter, sans-serif', minWidth: 200 }}>
        <Typography variant="subtitle2">
          Route {route.label} · mile {Math.round(cp.mile)}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          ETA {formatTime(cp.eta)}
        </Typography>
        <Box
          sx={{
            my: 0.75,
            px: 1,
            py: 0.25,
            borderRadius: 1,
            bgcolor: riskColor(cp.risk_level),
            color: '#fff',
            fontWeight: 600,
            fontSize: 13,
            width: 'fit-content',
          }}
        >
          {cp.risk_label}
        </Box>
        <Typography variant="body2">
          Wind {Math.round(cp.wind_mph)} mph (gusts {Math.round(cp.gust_mph)})
        </Typography>
        <Typography variant="body2">Rain {cp.rain_in_hr.toFixed(2)} in/hr</Typography>
        <Typography variant="body2">Snow {cp.snow_in_hr.toFixed(2)} in/hr</Typography>
        {cp.reasons.length > 0 && (
          <>
            <Divider sx={{ my: 0.75 }} />
            {cp.reasons.map((r) => (
              <Typography key={r} variant="caption" sx={{ display: 'block' }}>
                {r}
              </Typography>
            ))}
          </>
        )}
      </Box>
    </Popup>
  )
}

function MapView({
  trip,
  routeCoords,
  selected,
  hovered,
  onSelectRoute,
  activeCheckpoint,
  onCheckpoint,
  heatmap,
  heatmapVisible,
  hour,
  metric,
  truck,
}) {
  const mapRef = useRef(null)
  const [ready, setReady] = useState(false)
  const [cursor, setCursor] = useState('')

  // --- Static per-trip GeoJSON, built once per trip -------------------------------------
  const routesGeo = useMemo(() => {
    if (!trip) return null
    const features = []
    trip.routes.forEach((route) => {
      splitBySpans(routeCoords[route.label], route.checkpoints, route.distance_mi).forEach((seg, i) => {
        features.push({
          type: 'Feature',
          properties: { label: route.label, level: seg.level, color: riskColor(seg.level), seg: i },
          geometry: { type: 'LineString', coordinates: seg.coordinates },
        })
      })
    })
    return { type: 'FeatureCollection', features }
  }, [trip, routeCoords])

  const checkpointsGeo = useMemo(() => {
    if (!trip) return null
    return {
      type: 'FeatureCollection',
      features: trip.routes.flatMap((route) =>
        route.checkpoints.map((cp) => ({
          type: 'Feature',
          properties: { label: route.label, seq: cp.seq, color: riskColor(cp.risk_level) },
          geometry: { type: 'Point', coordinates: [cp.lon, cp.lat] },
        })),
      ),
    }
  }, [trip])

  const cellsGeo = useMemo(() => (heatmap ? cellsToGeoJSON(heatmap) : null), [heatmap])

  // --- Fit the camera to a new trip ------------------------------------------------------
  useEffect(() => {
    if (!ready || !trip) return
    mapRef.current?.fitBounds(boundsOf(Object.values(routeCoords)), {
      padding: { top: 60, bottom: 220, left: 60, right: 60 },
      duration: 900,
    })
  }, [ready, trip, routeCoords])

  // --- Heatmap frames: push values into feature-state ------------------------------------
  // Changing feature-state only re-colours on the GPU; there is no re-tiling and no React
  // re-render, which is what keeps scrubbing and playback smooth.
  useEffect(() => {
    const map = mapRef.current?.getMap()
    if (!ready || !map || !heatmap) return
    const apply = () => {
      if (!map.getSource('heat')) return
      const row = heatmap.frames[metric][hour]
      for (let id = 0; id < row.length; id++) map.setFeatureState({ source: 'heat', id }, { v: row[id] })
    }
    apply()
    // A freshly added source is parsed in a worker; re-apply once its tiles exist.
    const onData = (e) => e.sourceId === 'heat' && e.isSourceLoaded && apply()
    map.on('sourcedata', onData)
    return () => map.off('sourcedata', onData)
  }, [ready, heatmap, metric, hour, cellsGeo])

  const emphasised = hovered ?? selected
  const lineWidth = useMemo(() => widthExpr(emphasised, 0), [emphasised])
  const casingWidth = useMemo(() => widthExpr(emphasised, 3), [emphasised])
  const lineOpacity = useMemo(
    () => ['case', ['==', ['get', 'label'], emphasised ?? ''], 1, 0.45],
    [emphasised],
  )
  const routeSort = useMemo(() => ['case', ['==', ['get', 'label'], emphasised ?? ''], 1, 0], [emphasised])
  const cpFilter = useMemo(() => ['==', ['get', 'label'], selected ?? ''], [selected])
  const heatPaint = useMemo(
    () => ({ 'fill-color': fillColor(metric), 'fill-opacity': fillOpacity(metric) }),
    [metric],
  )

  const onClick = useCallback(
    (e) => {
      const f = e.features?.[0]
      if (!f) return
      if (f.layer.id === 'checkpoints') {
        const route = trip.routes.find((r) => r.label === f.properties.label)
        onCheckpoint(route.checkpoints.find((c) => c.seq === f.properties.seq))
      } else {
        onSelectRoute(f.properties.label)
      }
    },
    [trip, onCheckpoint, onSelectRoute],
  )

  const selectedRoute = trip?.routes.find((r) => r.label === selected)

  return (
    <Map
      ref={mapRef}
      initialViewState={INITIAL_VIEW}
      mapStyle={BASEMAP}
      onLoad={() => setReady(true)}
      interactiveLayerIds={trip ? INTERACTIVE : undefined}
      onClick={onClick}
      onMouseEnter={() => setCursor('pointer')}
      onMouseLeave={() => setCursor('')}
      cursor={cursor}
      dragRotate={false}
      style={{ width: '100%', height: '100%' }}
      attributionControl={{ compact: true }}
    >
      <NavigationControl position="top-right" showCompass={false} />
      <ScaleControl position="bottom-left" unit="imperial" />

      {cellsGeo && (
        <Source id="heat" type="geojson" data={cellsGeo}>
          <Layer
            id="heat-fill"
            type="fill"
            paint={heatPaint}
            layout={{ visibility: heatmapVisible ? 'visible' : 'none' }}
          />
        </Source>
      )}

      {routesGeo && (
        <Source id="routes" type="geojson" data={routesGeo}>
          <Layer
            id="route-casing"
            type="line"
            layout={{ 'line-join': 'round', 'line-cap': 'round', 'line-sort-key': routeSort }}
            paint={{ 'line-color': '#ffffff', 'line-width': casingWidth, 'line-opacity': lineOpacity }}
          />
          <Layer
            id="route-lines"
            type="line"
            layout={{ 'line-join': 'round', 'line-cap': 'round', 'line-sort-key': routeSort }}
            paint={{ 'line-color': ['get', 'color'], 'line-width': lineWidth, 'line-opacity': lineOpacity }}
          />
        </Source>
      )}

      {checkpointsGeo && (
        <Source id="checkpoints" type="geojson" data={checkpointsGeo}>
          <Layer
            id="checkpoints"
            type="circle"
            filter={cpFilter}
            paint={{
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 4, 10, 8],
              'circle-color': ['get', 'color'],
              'circle-stroke-color': '#fff',
              'circle-stroke-width': 2,
            }}
          />
        </Source>
      )}

      {trip && (
        <>
          <Marker longitude={trip.origin.lon} latitude={trip.origin.lat} anchor="bottom">
            <Pin color="#0b5cad" icon={<TripOriginIcon />} />
          </Marker>
          <Marker longitude={trip.destination.lon} latitude={trip.destination.lat} anchor="bottom">
            <Pin color="#1f2937" icon={<FlagIcon />} />
          </Marker>
        </>
      )}

      {truck && heatmapVisible && (
        <Marker longitude={truck.lon} latitude={truck.lat} anchor="center">
          <Box
            title="Truck position at this hour"
            sx={{
              fontSize: 22,
              lineHeight: 1,
              filter: 'drop-shadow(0 1px 2px rgba(0,0,0,.5))',
              transform: 'scaleX(-1)',
            }}
          >
            🚚
          </Box>
        </Marker>
      )}

      {activeCheckpoint && selectedRoute && (
        <CheckpointPopup route={selectedRoute} cp={activeCheckpoint} onClose={() => onCheckpoint(null)} />
      )}
    </Map>
  )
}

export default memo(MapView)
