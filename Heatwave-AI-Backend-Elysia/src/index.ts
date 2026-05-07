import { Elysia, t } from "elysia";
import { cors } from "@elysiajs/cors";
import { spawn } from "child_process";
import { promises as fsAsync, existsSync, readdirSync, mkdirSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import { randomUUID } from "crypto";

// process.cwd() is /app in Docker (WORKDIR /app in Dockerfile.render),
// which is where config.yaml, prediction/, models/ etc. all live.
// Using process.cwd() is more reliable than __dirname manipulation in Bun.
const BACKEND_ROOT = process.cwd();
const TRAIN_DIR = BACKEND_ROOT;
const MODELS_DIR = join(BACKEND_ROOT, "models");
const RESULTS_DIR = join(BACKEND_ROOT, "experiments", "results");
const FORECASTS_DIR = join(BACKEND_ROOT, "experiments", "forecasts");

// Whitelist of supported model keys
const VALID_MODELS = new Set(["balanced_rf", "xgboost", "lightgbm", "mlp", "kan"]);

// Max CSV payload size: 1 MB
const MAX_CSV_BYTES = 1_048_576;

// Keep only the latest N forecast files (prevents disk exhaustion)
const MAX_FORECAST_FILES = 50;

// Rate limiting: max requests per IP per window
const RATE_LIMIT_MAX = 60;
const RATE_LIMIT_WINDOW_MS = 60_000;
const rateLimitStore = new Map<string, { count: number; resetAt: number }>();

// ─── Structured logging ───────────────────────────────────────────────────────

function log(level: "INFO" | "WARN" | "ERROR", message: string, meta?: Record<string, unknown>) {
  console.log(JSON.stringify({ ts: new Date().toISOString(), level, message, ...meta }));
}

// ─── Rate limiter ─────────────────────────────────────────────────────────────

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const entry = rateLimitStore.get(ip);
  if (!entry || now > entry.resetAt) {
    rateLimitStore.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return false;
  }
  if (entry.count >= RATE_LIMIT_MAX) return true;
  entry.count++;
  return false;
}

// ─── Python runner (spawn — no shell, no injection) ───────────────────────────

const PYTHON_TIMEOUT_MS = 120_000; // 2 minutes

function runPythonScript(script: string, args: string[]): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const pythonCmd = process.platform === "win32" ? "python" : "python3";

    // spawn with explicit arg array: never passed through a shell
    const proc = spawn(pythonCmd, [script, ...args], {
      cwd: TRAIN_DIR,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let settled = false;

    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      proc.kill("SIGKILL");
      reject(new Error("Python script timed out after 120 seconds"));
    }, PYTHON_TIMEOUT_MS);

    proc.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
    proc.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString(); });

    proc.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (code !== 0) {
        reject(new Error(`Python script exited with code ${code}: ${stderr.slice(0, 500)}`));
      } else {
        resolve({ stdout, stderr });
      }
    });

    proc.on("error", (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(new Error(`Failed to start Python process: ${err.message}`));
    });
  });
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

async function readJsonFile(filePath: string): Promise<unknown> {
  if (!existsSync(filePath)) return null;
  const content = await fsAsync.readFile(filePath, "utf-8");
  return JSON.parse(content);
}

/** Trim old forecast files, keeping only the latest `keep` JSON+CSV pairs. */
async function cleanupOldForecasts(dir: string, keep: number): Promise<void> {
  try {
    const all = readdirSync(dir).filter(f => f.endsWith(".json")).sort();
    if (all.length <= keep) return;
    const toDelete = all.slice(0, all.length - keep);
    for (const file of toDelete) {
      const base = file.replace(".json", "");
      await fsAsync.unlink(join(dir, file)).catch(() => {});
      await fsAsync.unlink(join(dir, `${base}.csv`)).catch(() => {});
    }
    log("INFO", "Cleaned up old forecast files", { deleted: toDelete.length });
  } catch (err: any) {
    log("WARN", "Forecast cleanup failed", { error: err.message });
  }
}

/** Parse CSV text into an array of objects; throws on bad format. */
function parseCsvOutput(output: string): Record<string, string>[] {
  const lines = output.trim().split("\n");
  if (lines.length < 2) throw new Error("CSV output has no data rows");
  const headers = lines[0].split(",").map(h => h.trim());
  if (headers.length === 0 || headers.some(h => h === "")) {
    throw new Error("CSV output has empty headers");
  }
  return lines.slice(1).map((line, idx) => {
    const values = line.split(",");
    if (values.length !== headers.length) {
      throw new Error(`CSV row ${idx + 2} has ${values.length} columns, expected ${headers.length}`);
    }
    return headers.reduce((obj, header, i) => {
      obj[header] = values[i]?.trim() ?? "";
      return obj;
    }, {} as Record<string, string>);
  });
}

// ─── App ─────────────────────────────────────────────────────────────────────

const app = new Elysia()
  .use(cors())

  // Request logger
  .onRequest(({ request }) => {
    const url = new URL(request.url);
    log("INFO", "Request", { method: request.method, path: url.pathname });
  })

  .get("/", () => ({
    service: "Heatwave AI Backend",
    version: "1.0.0",
    status: "running",
  }))

  .get("/api/health", () => ({
    status: "healthy",
    timestamp: new Date().toISOString(),
  }))

  .get("/api/results/leaderboard", async () => {
    const leaderboard = await readJsonFile(join(RESULTS_DIR, "leaderboard.json"));
    if (!leaderboard) return { error: "Leaderboard not found" };
    return leaderboard;
  })

  .get("/api/results/best", async () => {
    const leaderboard = await readJsonFile(join(RESULTS_DIR, "leaderboard.json")) as any[];
    if (!leaderboard || leaderboard.length === 0) return { error: "No results available" };
    return leaderboard[0];
  })

  .get("/api/results/all", async () => {
    if (!existsSync(RESULTS_DIR)) return { error: "Results directory not found" };
    const files = readdirSync(RESULTS_DIR).filter(f => f.endsWith("_result.json"));
    const results: unknown[] = [];
    for (const file of files) {
      const data = await readJsonFile(join(RESULTS_DIR, file));
      if (data) results.push(data);
    }
    return results;
  })

  .get("/api/results/:model", async ({ params }) => {
    const modelMap: Record<string, string> = {
      xgboost:     "xgboost_result.json",
      lightgbm:    "lightgbm_result.json",
      balanced_rf: "balanced_random_forest_result.json",
      mlp:         "mlp_neural_network_result.json",
      kan:         "kan_result.json",
    };

    const filename = modelMap[params.model];
    if (!filename) return { error: "Unknown model" };

    const result = await readJsonFile(join(RESULTS_DIR, filename));
    if (!result) return { error: "Results not found for requested model" };
    return result;
  })

  .get("/api/predict/models", () => ({
    availableModels: readdirSync(MODELS_DIR)
      .filter(f => f.endsWith("_model.pkl"))
      .map(f => {
        if (f === "balanced_random_forest_model.pkl") return "balanced_rf";
        return f.replace("_model.pkl", "");
      })
      .filter(model => VALID_MODELS.has(model)),
  }))

  .get("/api/predict/status", async () => {
    try {
      const configPath = join(TRAIN_DIR, "config.yaml");
      if (!existsSync(configPath)) return { available: false, message: "Configuration not found" };
      if (!existsSync(MODELS_DIR)) return { available: false, message: "Models directory not found" };
      const models = readdirSync(MODELS_DIR).filter(f => f.endsWith(".pkl"));
      return { available: true, trainedModels: models };
    } catch {
      return { available: false, message: "Status check failed" };
    }
  })

  .post("/api/predict", async ({ body, request }) => {
    // Rate limiting
    const clientIp = request.headers.get("x-forwarded-for")?.split(",")[0].trim() ?? "unknown";
    if (isRateLimited(clientIp)) {
      log("WARN", "Rate limit exceeded", { ip: clientIp });
      return { success: false, predictions: [], model: "", error: "Too many requests. Please wait before trying again." };
    }

    const { model = "balanced_rf", inputData, includeProba = false } = body as {
      model: string;
      inputData: string;
      includeProba?: boolean;
    };

    // Validate model against whitelist
    if (!VALID_MODELS.has(model)) {
      return { success: false, predictions: [], model, error: "Invalid model selection" };
    }

    // Validate CSV payload size
    if (Buffer.byteLength(inputData, "utf-8") > MAX_CSV_BYTES) {
      return { success: false, predictions: [], model, error: "Input data exceeds maximum allowed size" };
    }

    // Validate minimal CSV structure (must have at least a header line)
    const lines = inputData.trim().split("\n");
    if (lines.length < 2 || !lines[0].includes(",")) {
      return { success: false, predictions: [], model, error: "Input data must be valid CSV with a header row and at least one data row" };
    }

    // Unique temp files per request in OS tmpdir — no collisions
    const reqId = randomUUID();
    const inputPath = join(tmpdir(), `heatwave_input_${reqId}.csv`);
    const outputPath = join(tmpdir(), `heatwave_output_${reqId}.csv`);

    try {
      await fsAsync.writeFile(inputPath, inputData, "utf-8");

      const args = [
        "--model", model,
        "--input", inputPath,
        "--output", outputPath,
        "--config", join(TRAIN_DIR, "config.yaml"),
      ];
      if (includeProba) args.push("--proba");

      await runPythonScript(join(TRAIN_DIR, "prediction", "predict.py"), args);

      const output = await fsAsync.readFile(outputPath, "utf-8");
      const predictions = parseCsvOutput(output);

      log("INFO", "Prediction completed", { model, rows: predictions.length });
      return { success: true, predictions, model };
    } catch (error: any) {
      log("ERROR", "Prediction failed", { model, error: error.message });
      return { success: false, predictions: [], model, error: "Prediction failed. Check server logs for details." };
    } finally {
      await fsAsync.unlink(inputPath).catch(() => {});
      await fsAsync.unlink(outputPath).catch(() => {});
    }
  }, {
    body: t.Object({
      model: t.Optional(t.String()),
      inputData: t.String(),
      includeProba: t.Optional(t.Boolean()),
    }),
  })

  .get("/api/forecast/latest", async () => {
    if (!existsSync(FORECASTS_DIR)) return { error: "No forecasts available" };

    const files = readdirSync(FORECASTS_DIR)
      .filter(f => f.endsWith(".json"))
      .sort()
      .reverse();

    if (files.length === 0) return { error: "No forecast files found" };

    const data = await readJsonFile(join(FORECASTS_DIR, files[0]));
    return {
      filename: files[0],
      forecast: data,
      totalDays: Array.isArray(data) ? data.length : 0,
    };
  })

  .post("/api/forecast", async ({ body, request }) => {
    // Rate limiting
    const clientIp = request.headers.get("x-forwarded-for")?.split(",")[0].trim() ?? "unknown";
    if (isRateLimited(clientIp)) {
      log("WARN", "Rate limit exceeded", { ip: clientIp });
      return { success: false, error: "Too many requests. Please wait before trying again." };
    }

    const { model, days = 7, latitude, longitude } = body as {
      model: string;
      days?: number;
      latitude?: number;
      longitude?: number;
    };

    // Validate model against whitelist
    if (!VALID_MODELS.has(model)) {
      return { success: false, error: "Invalid model selection" };
    }

    // Cap at Open-Meteo's 16-day limit
    const forecastDays = Math.min(Math.max(1, days), 16);

    if (!existsSync(FORECASTS_DIR)) {
      mkdirSync(FORECASTS_DIR, { recursive: true });
    }

    const args = [
      "--model", model,
      "--days", String(forecastDays),
      "--config", join(TRAIN_DIR, "config.yaml"),
    ];

    if (typeof latitude === "number" && Number.isFinite(latitude)) {
      args.push("--latitude", String(latitude));
    }

    if (typeof longitude === "number" && Number.isFinite(longitude)) {
      args.push("--longitude", String(longitude));
    }

    try {
      const result = await runPythonScript(join(TRAIN_DIR, "prediction", "forecast.py"), args);

      const files = readdirSync(FORECASTS_DIR)
        .filter(f => f.endsWith(".json"))
        .sort()
        .reverse();

      if (files.length === 0) {
        return { success: false, error: "Forecast generated but no output file found" };
      }

      const data = await readJsonFile(join(FORECASTS_DIR, files[0]));

      // Clean up old forecasts in the background
      cleanupOldForecasts(FORECASTS_DIR, MAX_FORECAST_FILES);

      log("INFO", "Forecast completed", { model, days: forecastDays, file: files[0] });
      return {
        success: true,
        filename: files[0],
        forecast: data,
        totalDays: Array.isArray(data) ? data.length : 0,
        location: {
          latitude: typeof latitude === "number" && Number.isFinite(latitude) ? latitude : null,
          longitude: typeof longitude === "number" && Number.isFinite(longitude) ? longitude : null,
        },
        log: result.stdout,
      };
    } catch (error: any) {
      log("ERROR", "Forecast failed", { model, error: error.message });
      return { success: false, error: "Forecast generation failed. Check server logs for details." };
    }
  }, {
    body: t.Object({
      model: t.String(),
      days: t.Optional(t.Number()),  // 1–16, defaults to 7 (Open-Meteo limit)
      latitude: t.Optional(t.Number()),
      longitude: t.Optional(t.Number()),
    }),
  })

  .listen(process.env.PORT || 3000);

log("INFO", "Heatwave AI Backend started", {
  port: app.server?.port,
  host: app.server?.hostname,
});
