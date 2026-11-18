import { defineConfig, devices } from "@playwright/test";

// Two projects:
//   mocked - the API is faked with page.route(). Fast, deterministic, runs in CI.
//   live   - the real FastAPI + Ollama stack. Slow and non-deterministic, so answers are
//            checked by meaning (embedding similarity), not exact text. Run with LIVE=1.
const live = !!process.env.LIVE;
const repoRoot = "..";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "mocked",
      testDir: "./e2e/mocked",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile",
      testDir: "./e2e/mocked",
      grep: /@responsive/,
      use: { ...devices["Pixel 7"] },
    },
    {
      name: "live",
      testDir: "./e2e/live",
      // One model on an 8 GB laptop answers one question at a time.
      workers: 1,
      fullyParallel: false,
      timeout: 120_000,
      expect: { timeout: 90_000 },
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
    },
    ...(live
      ? [
          {
            command: ".venv/bin/uvicorn app.main:app --port 8000",
            cwd: repoRoot,
            url: "http://localhost:8000/health",
            reuseExistingServer: true,
            timeout: 120_000,
          },
        ]
      : []),
  ],
});
