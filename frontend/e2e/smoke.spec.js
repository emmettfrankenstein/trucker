import { expect, test } from '@playwright/test'

import { collectErrors, openCheckpoints, planSample, stubBasemap } from './helpers'

test.beforeEach(async ({ page }) => stubBasemap(page))

test('plans a trip end to end: routes, recommendation, checkpoints, heatmap', async ({ page }) => {
  const errors = collectErrors(page)
  await page.goto('/')
  await planSample(page, 'Dallas → Atlanta')

  // Three ranked routes, exactly one recommended, with a reason.
  for (const label of ['A', 'B', 'C'])
    await expect(page.getByText(`Route ${label}`, { exact: true })).toBeVisible()
  await expect(page.getByText('Recommended', { exact: true })).toHaveCount(1)
  await expect(page.getByText(/^Take Route [ABC]$/)).toBeVisible()
  await expect(page.getByText(/is recommended:/)).toBeVisible()

  // Checkpoints table with ETAs and risk levels.
  // Checkpoint table starts collapsed, then opens with ETAs and risk levels.
  await expect(page.locator('tbody tr')).toHaveCount(0)
  await openCheckpoints(page)
  await expect(page.locator('tbody tr').first()).toContainText('Low')

  // Heatmap loads and the slider moves the clock without errors.
  const slider = page.getByRole('slider', { name: 'Forecast hour' })
  await expect(slider).toBeVisible()
  const label = page.getByText(/from departure\)/)
  await expect(label).toContainText('+0h')
  await slider.focus()
  for (let i = 0; i < 6; i++) await page.keyboard.press('ArrowRight')
  await expect(label).toContainText('+6h')

  expect(errors).toEqual([])
})
