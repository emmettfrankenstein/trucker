import { defineConfig, devices } from '@playwright/test'

// End-to-end tests run the real Django API with deterministic fake providers
// (backend/tests/fakes.py), so they need no API keys and never flake on live weather.
const PY = process.env.E2E_PYTHON ?? 'python'
const fakeProviders = {
  ROUTING_PROVIDER: 'tests.fakes.FakeRouting',
  GEOCODING_PROVIDER: 'tests.fakes.FakeGeocoding',
  WEATHER_PROVIDER: 'tests.fakes.FakeWeather',
  DEBUG: '1',
  DATABASE_URL: 'sqlite:////tmp/trucker-e2e.sqlite3',
  THROTTLE_PLAN: '1000/hour',
}

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: 'http://localhost:4173',
    trace: 'retain-on-failure',
    launchOptions: process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {},
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, testMatch: /smoke/ },
  ],
  webServer: [
    {
      command: `rm -f /tmp/trucker-e2e.sqlite3 && ${PY} manage.py migrate --noinput && ${PY} manage.py runserver 8000 --noreload`,
      cwd: '../backend',
      url: 'http://localhost:8000/api/health/',
      env: fakeProviders,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: 'npm run build && npx vite preview --port 4173 --strictPort',
      url: 'http://localhost:4173',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
})
