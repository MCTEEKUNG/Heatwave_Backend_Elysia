import { Elysia, t } from "elysia";
import { cors } from "@elysiajs/cors";
import { spawn } from "child_process";
import {
  getProvinces,
  getProvinceForecast,
  getForecastMap,
  getThresholds,
} from "./routes/forecast";
import { promises as fsAsync, existsSync, readdirSync } from "fs";
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

// Whitelist of supported model keys
const VALID_MODELS = new Set(["balanced_rf", "xgboost", "lightgbm", "mlp", "kan"]);

// Max CSV payload size: 1 MB
const MAX_CSV_BYTES = 1_048_576;

// Rate limiting: max requests per IP per window
const RATE_LIMIT_MAX = 10;
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

    proc.stdout.on("data", (chunk: Buffer) => { stdout += chunk.toString(); });
    proc.stderr.on("data", (chunk: Buffer) => { stderr += chunk.toString(); });

    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`Python script exited with code ${code}: ${stderr.slice(0, 500)}`));
      } else {
        resolve({ stdout, stderr });
      }
    });

    proc.on("error", (err) => {
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
    availableModels: ["balanced_rf"],
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

  // Retired 2026-06-10: GET /api/forecast/latest and POST /api/forecast served
  // on-box forecasts from the stale v1 balanced_rf model. The live forecast
  // path is the Supabase-backed Forecast Service API below (written daily by
  // the lgbm-v1 77-province job). Old clients receive 410 Gone.
  .get("/api/forecast/latest", ({ set }) => {
    set.status = 410;
    return { error: "Retired endpoint. Use /api/forecast/map or /api/forecast/province/:id" };
  })

  // ─── Forecast Service API (private `heatwave` schema via direct Postgres) ─────
  // These serve the model's forecasts written to Supabase by the Python daily job
  // (scripts/run_daily_forecast.py). Reads only; on a DB/config error they return
  // 503 with a clear message rather than crashing the server.

  .get("/api/provinces", async ({ set }) => {
    try {
      return await getProvinces();
    } catch (error: any) {
      set.status = 503;
      log("ERROR", "getProvinces failed", { error: error.message });
      return { error: "Database unavailable" };
    }
  })

  .get("/api/forecast/province/:id", async ({ params, query, set }) => {
    const id = Number(params.id);
    if (!Number.isInteger(id) || id <= 0) {
      set.status = 400;
      return { error: "Invalid province id" };
    }
    let days = Number(query.days ?? 7);
    if (!Number.isInteger(days) || days <= 0) days = 7;
    if (days > 16) days = 16;
    try {
      return await getProvinceForecast(id, days);
    } catch (error: any) {
      set.status = 503;
      log("ERROR", "getProvinceForecast failed", { error: error.message });
      return { error: "Database unavailable" };
    }
  })

  .get("/api/forecast/map", async ({ set }) => {
    try {
      return await getForecastMap();
    } catch (error: any) {
      set.status = 503;
      log("ERROR", "getForecastMap failed", { error: error.message });
      return { error: "Database unavailable" };
    }
  })

  .get("/api/thresholds/:id", async ({ params, set }) => {
    const id = Number(params.id);
    if (!Number.isInteger(id) || id <= 0) {
      set.status = 400;
      return { error: "Invalid province id" };
    }
    try {
      const rows = await getThresholds(id);
      return { province_id: id, thresholds: rows };
    } catch (error: any) {
      set.status = 503;
      log("ERROR", "getThresholds failed", { error: error.message });
      return { error: "Database unavailable" };
    }
  })

  .listen(process.env.PORT || 3000);

log("INFO", "Heatwave AI Backend started", {
  port: app.server?.port,
  host: app.server?.hostname,
});
