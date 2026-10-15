import { expect } from '@playwright/test'

// Swap the online basemap for a blank style so tests never depend on third-party tiles.
export async function stubBasemap(page) {
  await page.route('https://tiles.openfreemap.org/**', (route) =>
    route.fulfill({
      json: {
        version: 8,
        sources: {},
        layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#e9edf1' } }],
      },
    }),
  )
}

export function collectErrors(page) {
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  return errors
}

export async function planSample(page, name) {
  await page.getByText(name).click()
  await page.getByRole('button', { name: /find the safest route/i }).click()
  await page.waitForURL(/\/trips\/[0-9a-f-]{36}$/)
  await expect(page.getByText('Route A', { exact: true })).toBeVisible()
}

export async function openCheckpoints(page) {
  await page.getByRole('button', { name: /checkpoints \(\d+\)/ }).click()
  await expect(page.locator('tbody tr').first()).toBeVisible()
}
