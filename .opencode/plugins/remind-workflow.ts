import type { Plugin } from "@opencode-ai/plugin";
import { execSync } from "child_process";

let cachedPrimeOutput = "";
try {
  cachedPrimeOutput = execSync("bd prime", { encoding: "utf-8", timeout: 10000 });
} catch {
  cachedPrimeOutput = "";
}

export const RemindWorkflowPlugin: Plugin = async ({ project }) => {
  console.log(`[Plugin] RemindWorkflowPlugin loaded for: ${project.name}`);

  return {
    "experimental.chat.system.transform": async (_input, output) => {
      if (!output.system) {
        output.system = [];
      }

      const workflowReminder = `
# ═══════════════════════════════════════════════════════════════════════
# MANDATORY WORKFLOW ENFORCEMENT (PROJECT RULES)
# ═══════════════════════════════════════════════════════════════════════
At every single turn, you MUST strictly adhere to the following rules:

1. MANDATORY USE OF clean_python TOOL FOR ALL PYTHON (.py) FILES:
   - NEVER use 'write' or 'edit' to create or modify Python (.py) files!
   - You MUST use the 'clean_python' tool (verify_and_commit_code) for ALL Python code additions, modifications, and updates.
   - Provide file_path (relative path), pydantic_architecture_plan, and code_payload when calling 'clean_python'.

2. USE BEADS (bd) FOR TASK TRACKING:
   - Never answer a request or edit code without tracking your active task.
   - Run 'bd ready' to find available work.
`;

      if (output.system.length > 0) {
        output.system[0] += "\n" + workflowReminder;
      } else {
        output.system.push(workflowReminder);
      }

      if (cachedPrimeOutput) {
        output.system.push(cachedPrimeOutput);
      }
    },
  };
};
