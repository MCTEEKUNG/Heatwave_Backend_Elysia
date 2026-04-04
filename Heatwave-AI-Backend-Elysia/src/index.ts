import { Elysia, t } from "elysia";
import { cors } from "@elysiajs/cors";
import { exec } from "child_process";
import { readFileSync, writeFileSync, existsSync, unlinkSync, readdirSync, mkdirSync } from "fs";
import { join, dirname } from "path";

const BACKEND_ROOT = join(__dirname, "..");
const TRAIN_DIR = BACKEND_ROOT;
const MODELS_DIR = join(BACKEND_ROOT, "models");
const RESULTS_DIR = join(BACKEND_ROOT, "experiments", "results");
const FORECASTS_DIR = join(BACKEND_ROOT, "experiments", "forecasts");

interface PredictionRequest {
  model: string;
  inputData: string;
  includeProba?: boolean;
}

interface PredictionResult {
  success: boolean;
  predictions: Record<string, string>[];
  model: string;
  log?: string;
  error?: string;
}

function runPythonScript(script: string, args: string[]): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const pythonCmd = process.platform === "win32" ? "python" : "python3";
    const quotedArgs = args.map(a => `"${a.replace(/"/g, '\\"')}"`).join(" ");
    const scriptCmd = `${pythonCmd} "${script}" ${quotedArgs}`;
    const cmd = process.platform === "win32" ? `cmd /c ${scriptCmd}` : scriptCmd;

    exec(cmd, { cwd: TRAIN_DIR }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error(`Python script failed: ${stderr || error.message}`));
      } else {
        resolve({ stdout, stderr });
      }
    });
  });
}

function readJsonFile(filePath: string): any {
  if (!existsSync(filePath)) return null;
  return JSON.parse(readFileSync(filePath, "utf-8"));
}

const app = new Elysia()
  .use(cors())
  .get("/", () => ({
    service: "Heatwave AI Backend",
    version: "1.0.0",
    status: "running"
  }))

  .get("/api/health", () => ({
    status: "healthy",
    timestamp: new Date().toISOString()
  }))

  .get("/api/results/leaderboard", () => {
    const leaderboard = readJsonFile(join(RESULTS_DIR, "leaderboard.json"));
    if (!leaderboard) {
      return { error: "Leaderboard not found" };
    }
    return leaderboard;
  })

  .get("/api/results/best", () => {
    const leaderboard = readJsonFile(join(RESULTS_DIR, "leaderboard.json"));
    if (!leaderboard || leaderboard.length === 0) {
      return { error: "No results available" };
    }
    return leaderboard[0];
  })

  .get("/api/results/all", () => {
    const results: any[] = [];
    if (!existsSync(RESULTS_DIR)) {
      return { error: "Results directory not found" };
    }

    const files = readdirSync(RESULTS_DIR).filter(
      f => f.endsWith("_result.json")
    );

    for (const file of files) {
      const data = readJsonFile(join(RESULTS_DIR, file));
      if (data) results.push(data);
    }

    return results;
  })

  .get("/api/results/:model", ({ params }) => {
    const modelMap: Record<string, string> = {
      "xgboost": "xgboost_result.json",
      "lightgbm": "lightgbm_result.json",
      "balanced_rf": "balanced_random_forest_result.json",
      "mlp": "mlp_neural_network_result.json",
      "kan": "kan_result.json"
    };

    const filename = modelMap[params.model];
    if (!filename) {
      return { error: `Unknown model: ${params.model}` };
    }

    const result = readJsonFile(join(RESULTS_DIR, filename));
    if (!result) {
      return { error: `Results not found for ${params.model}` };
    }

    return result;
  })

  .get("/api/predict/models", () => ({
    availableModels: ["balanced_rf"]
  }))

  .get("/api/predict/status", async () => {
    try {
      const configPath = join(TRAIN_DIR, "config.yaml");
      if (!existsSync(configPath)) {
        return { available: false, message: "Configuration not found" };
      }

      if (!existsSync(MODELS_DIR)) {
        return { available: false, message: "Models directory not found" };
      }

      const models = readdirSync(MODELS_DIR).filter(f => f.endsWith(".pkl"));
      return {
        available: true,
        trainedModels: models
      };
    } catch (error: any) {
      return { available: false, message: error.message };
    }
  })

  .post("/api/predict", async ({ body }) => {
    const { model = "balanced_rf", inputData, includeProba = false } = body as PredictionRequest;
    const inputPath = join(TRAIN_DIR, "temp_input.csv");
    const outputPath = join(TRAIN_DIR, "temp_output.csv");

    try {
      writeFileSync(inputPath, inputData);

      const args = [
        "--model", model,
        "--input", inputPath,
        "--output", outputPath,
        "--config", join(TRAIN_DIR, "config.yaml")
      ];

      if (includeProba) {
        args.push("--proba");
      }

      await runPythonScript(join(TRAIN_DIR, "prediction", "predict.py"), args);

      const output = readFileSync(outputPath, "utf-8");
      const lines = output.trim().split("\n");
      const headers = lines[0].split(",").map(h => h.trim());
      const predictions = lines.slice(1).map(line => {
        const values = line.split(",");
        return headers.reduce((obj, header, i) => {
          obj[header] = values[i]?.trim() || "";
          return obj;
        }, {} as Record<string, string>);
      });

      return {
        success: true,
        predictions,
        model
      } as PredictionResult;
    } catch (error: any) {
      return {
        success: false,
        predictions: [],
        model,
        error: error.message
      } as PredictionResult;
    } finally {
      if (existsSync(inputPath)) unlinkSync(inputPath);
      if (existsSync(outputPath)) unlinkSync(outputPath);
    }
  }, {
    body: t.Object({
      model: t.String(),
      inputData: t.String(),
      includeProba: t.Optional(t.Boolean())
    })
  })

  .get("/api/forecast/latest", () => {
    if (!existsSync(FORECASTS_DIR)) {
      return { error: "No forecasts available" };
    }

    const files = readdirSync(FORECASTS_DIR)
      .filter(f => f.endsWith(".json"))
      .sort()
      .reverse();

    if (files.length === 0) {
      return { error: "No forecast files found" };
    }

    const data = readJsonFile(join(FORECASTS_DIR, files[0]));
    return {
      filename: files[0],
      forecast: data,
      totalDays: Array.isArray(data) ? data.length : 0
    };
  })

  .post("/api/forecast", async ({ body }) => {
    const { model, days = 30, cycles = 1, startDate } = body as {
      model: string;
      days?: number;
      cycles?: number;
      startDate?: string;
    };

    if (!existsSync(FORECASTS_DIR)) {
      mkdirSync(FORECASTS_DIR, { recursive: true });
    }

    const args = [
      "--model", model,
      "--days", String(days),
      "--cycles", String(cycles),
      "--config", join(TRAIN_DIR, "config.yaml")
    ];

    if (startDate) {
      args.push("--start-date", startDate);
    }

    try {
      const result = await runPythonScript(join(TRAIN_DIR, "prediction", "forecast.py"), args);

      const files = readdirSync(FORECASTS_DIR)
        .filter(f => f.endsWith(".json"))
        .sort()
        .reverse();

      if (files.length > 0) {
        const data = readJsonFile(join(FORECASTS_DIR, files[0]));
        return {
          success: true,
          filename: files[0],
          forecast: data,
          totalDays: Array.isArray(data) ? data.length : 0,
          log: result.stdout
        };
      }

      return {
        success: false,
        error: "Forecast generated but no output file found"
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message
      };
    }
  }, {
    body: t.Object({
      model: t.String(),
      days: t.Optional(t.Number()),
      cycles: t.Optional(t.Number()),
      startDate: t.Optional(t.String())
    })
  })

  .listen(process.env.PORT || 3000);

console.log(
  `🦊 Heatwave AI Backend running at ${app.server?.hostname}:${app.server?.port}`
);
