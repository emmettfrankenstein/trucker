// Mirrors trips/domain/risk.py. Colours run green → purple so severity reads at a glance
// and stay distinguishable for the common forms of colour blindness.
export const RISK_LEVELS = [
  { level: 0, key: 'LOW', label: 'Low', color: '#2e9d5b' },
  { level: 1, key: 'MODERATE', label: 'Moderate', color: '#e0b100' },
  { level: 2, key: 'HIGH', label: 'High', color: '#ec7a12' },
  { level: 3, key: 'SEVERE', label: 'Severe', color: '#d32f2f' },
  { level: 4, key: 'NO_TRAVEL', label: 'No Travel', color: '#6a1b9a' },
]

export const riskColor = (level) => RISK_LEVELS[level]?.color ?? '#9e9e9e'
export const riskLabel = (level) => RISK_LEVELS[level]?.label ?? 'Unknown'

// Thresholds from the assignment's table; the heatmap colours raw values on the same scale.
export const METRICS = {
  risk: { label: 'Risk', unit: '', stops: [0, 1, 2, 3, 4], format: (v) => riskLabel(v) },
  wind: { label: 'Wind', unit: 'mph', stops: [0, 25, 35, 45, 55], format: (v) => `${v} mph` },
  rain: { label: 'Rain', unit: 'in/hr', stops: [0, 0.1, 0.25, 0.5, 1.0], format: (v) => `${v} in/hr` },
  snow: { label: 'Snow', unit: 'in/hr', stops: [0, 0.5, 1.0, 2.0, 3.0], format: (v) => `${v} in/hr` },
}
