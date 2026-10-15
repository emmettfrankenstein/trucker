import dayjs from 'dayjs'

export function formatDuration(seconds) {
  const minutes = Math.round(seconds / 60)
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h ? `${h} h ${m} min` : `${m} min`
}

export const formatMiles = (mi) => `${Math.round(mi).toLocaleString()} mi`
export const formatTime = (iso) => dayjs(iso).format('ddd h:mm A')
export const formatDateTime = (iso) => dayjs(iso).format('MMM D, h:mm A')
export const formatLoad = (lb) => `${Number(lb).toLocaleString()} lb`
