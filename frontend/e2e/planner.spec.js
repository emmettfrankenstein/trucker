import { expect, test } from '@playwright/test'

import { collectErrors, openCheckpoints, planSample, stubBasemap } from './helpers'

test.beforeEach(async ({ page }) => stubBasemap(page))

test('flags an unsafe departure when every route crosses No Travel weather', async ({ page }) => {
  await page.goto('/')
  await planSample(page, 'Chicago → Minneapolis') // the fake storm covers this corridor
  await expect(page.getByText('No route is safe at this departure time')).toBeVisible()
  await expect(page.getByRole('button', { name: /checkpoints \(\d+\)/ })).toContainText('No Travel')
  await openCheckpoints(page)
  await expect(page.locator('tbody tr').first()).toContainText('No Travel')
})

test('selecting a route card swaps the checkpoint table; a row opens a popup', async ({ page }) => {
  await page.goto('/')
  await planSample(page, 'Dallas → Atlanta')
  await page.getByText('Route C', { exact: true }).click()
  await expect(page.getByText(/Route C checkpoints/)).toBeVisible()
  await openCheckpoints(page)
  await page.locator('tbody tr').nth(2).click()
  await expect(page.locator('.maplibregl-popup')).toContainText('Route C · mile')
})

test('heatmap metric toggle and play button work', async ({ page }) => {
  const errors = collectErrors(page)
  await page.goto('/')
  await planSample(page, 'Dallas → Atlanta')
  await page.getByRole('button', { name: 'Wind' }).click()
  await expect(page.getByText('≥ 55 mph')).toBeVisible()
  await page.getByRole('button', { name: 'Play forecast animation' }).click()
  await expect(page.getByText(/\+[1-9]\d*h from departure/)).toBeVisible()
  await page.getByRole('button', { name: 'Pause forecast animation' }).click()
  expect(errors).toEqual([])
})

test('a trip link reloads straight into the saved result', async ({ page }) => {
  await page.goto('/')
  await planSample(page, 'Dallas → Atlanta')
  await page.reload()
  await expect(page.getByText(/^Take Route [ABC]$/)).toBeVisible()
})

test('shows validation errors instead of calling the API', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Load weight').fill('0')
  await page.getByRole('button', { name: /find the safest route/i }).click()
  await expect(page.getByText('Pick an origin from the list')).toBeVisible()
  await expect(page.getByText('Enter a weight between 1 and 200,000 lb')).toBeVisible()
  await expect(page).toHaveURL(/\/$/)
})

test('origin autocomplete uses the geocoding endpoint', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('combobox', { name: 'Origin' }).fill('springfield')
  await page.getByRole('option', { name: 'Springfield, IL' }).click()
  await expect(page.getByRole('combobox', { name: 'Origin' })).toHaveValue('Springfield, IL')
})

test('sign up, plan, find it in history, delete it', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('tab', { name: 'Create account' }).click()
  await page.getByLabel('Username').fill(`driver${Date.now()}`)
  await page.getByLabel('Password').fill('Long-enough-pass-1')
  await page.getByRole('button', { name: 'Create account' }).last().click()
  await expect(page.getByRole('link', { name: 'My trips' })).toBeVisible()

  await planSample(page, 'Dallas → Atlanta')
  await page.getByRole('link', { name: 'My trips' }).click()
  await expect(page.getByText('Dallas, TX → Atlanta, GA')).toBeVisible()
  await page.getByRole('button', { name: 'Delete trip' }).click()
  await expect(page.getByText('No saved trips yet')).toBeVisible()

  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
})
