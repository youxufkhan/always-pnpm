import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REWRITER_PATH = process.env.ALWAYS_PNPM_SCRIPT || path.resolve(__dirname, "../../scripts/rewrite_npm.py");

export const AlwaysPnpmPlugin = async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (!input || !output || !output.args) return;
      if (input.tool === "bash" || input.tool === "execute") {
        const cmd = output.args.command;
        if (!cmd || typeof cmd !== "string") return;
        if (!cmd.includes("npm") && !cmd.includes("npx")) return;

        try {
          const rewritten = execFileSync(
            "python3",
            [REWRITER_PATH, "--translate", cmd],
            { encoding: "utf8", timeout: 3000 }
          ).trim();

          if (rewritten && rewritten !== cmd) {
            output.args.command = rewritten;
          }
        } catch (err) {
          // If exit code is 1 (no changes) or process error, fail open safely
        }
      }
    },
  };
};

export default AlwaysPnpmPlugin;
