import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

// install.sh substitutes the installed rewrite_npm.py path; unsubstituted means we're running from the repo.
const INSTALLED = "__ALWAYS_PNPM_SCRIPT__";
const REWRITER_PATH = process.env.ALWAYS_PNPM_SCRIPT ||
  (INSTALLED.startsWith("__") ? fileURLToPath(new URL("../../scripts/rewrite_npm.py", import.meta.url)) : INSTALLED);

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
          // Exit 1 = nothing to rewrite. Anything else: fail open, but say so.
          if (err.status !== 1) console.error(`always-pnpm: rewriter failed (${REWRITER_PATH}): ${err.message}`);
        }
      }
    },
  };
};

export default AlwaysPnpmPlugin;
