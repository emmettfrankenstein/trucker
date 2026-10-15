import { fireEvent, render, screen } from '@testing-library/react'

import RouteCard from './RouteCard'

const route = {
  label: 'B',
  rank: 1,
  is_recommended: true,
  duration_s: 3 * 3600 + 25 * 60,
  distance_mi: 201.4,
  avg_risk: 0.42,
  max_level: 2,
  summary: '12 mi High, 30 mi Moderate',
  miles_by_level: { LOW: 159.4, MODERATE: 30, HIGH: 12, SEVERE: 0, NO_TRAVEL: 0 },
}

test('shows the summary, recommendation and selects on click', () => {
  const onSelect = vi.fn()
  render(<RouteCard route={route} selected={false} onSelect={onSelect} />)
  expect(screen.getByText('Route B')).toBeInTheDocument()
  expect(screen.getByText('Recommended')).toBeInTheDocument()
  expect(screen.getByText('3 h 25 min')).toBeInTheDocument()
  expect(screen.getByText('201 mi')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /12 miles High/ })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button'))
  expect(onSelect).toHaveBeenCalledWith('B')
})
