// clean_python.ts
//
// Thin OpenCode Plugin: Validated Python File Writer.
// Delegates all quality checks (Ruff, Pyright, Radon CC < 6, AST anti-slop)
// to the `clean_py` pip package. This file handles security gating,
// virtual environment resolution, temp-file hygiene, and retry tracking.

import type { Plugin } from "@opencode-ai/plugin";
import { tool } from "@opencode-ai/plugin";
import { execFile } from "node:child_process";
import * as crypto from "node:crypto";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

// --- CONFIGURATION ---
const MAX_VALIDATION_ATTEMPTS = 10;
const OUTPUT_LIMIT = 20_000;
const MAX_TRACKER_SIZE = 1000;

// --- STATE MANAGEMENT ---
const retryTracker = new Map<string, { count: number }>();

class SecurityError extends Error {
    constructor(message: string) {
        super(message);
        this.name = "SecurityError";
    }
}

class InfrastructureError extends Error {
    constructor(message: string) {
        super(message);
        this.name = "InfrastructureError";
    }
}

// --- UTILITIES ---
function truncate(value: string, limit: number = OUTPUT_LIMIT): string {
    if (!value) return "";
    if (value.length <= limit) return value;
    return `${value.slice(0, limit)}\n... output truncated`;
}

function sanitizeOutput(rawOutput: string, tempPath: string, targetPath: string): string {
    if (!rawOutput) return "";
    try {
        const escapedTempPath = tempPath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return rawOutput.replace(new RegExp(escapedTempPath, "g"), targetPath).trim();
    } catch {
        return rawOutput.trim();
    }
}

// --- PYTHON INFRASTRUCTURE RESOLUTION ---
async function getPythonEnvironment(
    targetPath: string,
    workspaceDir: string
): Promise<{ pythonBin: string; venvDir: string }> {
    const candidateDirs: string[] = [];

    // 1. Walk up from target path
    let curr = path.dirname(targetPath);
    while (curr && curr !== path.dirname(curr)) {
        candidateDirs.push(curr);
        curr = path.dirname(curr);
    }

    // 2. Add workspaceDir and known project locations
    candidateDirs.push(workspaceDir);
    candidateDirs.push("/home/yapilwsl/arthityap/baziforecaster");
    candidateDirs.push("/home/yapilwsl/arthityap");

    const binaries = [
        path.join("bin", "python"),
        path.join("bin", "python3"),
        path.join("Scripts", "python.exe"),
    ];

    for (const dir of candidateDirs) {
        const venvDir = path.join(dir, ".venv");
        for (const relBin of binaries) {
            const candidateBin = path.join(venvDir, relBin);
            const stats = await fs.stat(candidateBin).catch(() => null);
            if (stats?.isFile()) {
                return { pythonBin: candidateBin, venvDir };
            }
        }
    }

    // 3. Check VIRTUAL_ENV environment variable
    if (process.env.VIRTUAL_ENV) {
        const venvDir = process.env.VIRTUAL_ENV;
        for (const relBin of binaries) {
            const candidateBin = path.join(venvDir, relBin);
            const stats = await fs.stat(candidateBin).catch(() => null);
            if (stats?.isFile()) {
                return { pythonBin: candidateBin, venvDir };
            }
        }
    }

    throw new InfrastructureError(
        "Python virtual environment not found. Expected a usable Python binary in .venv/bin/python."
    );
}

function buildSubprocessEnv(venvDir: string): NodeJS.ProcessEnv {
    const env: NodeJS.ProcessEnv = { ...process.env };
    env.VIRTUAL_ENV = venvDir;
    env.PYTHONIOENCODING = "utf-8";
    env.PYTHONDONTWRITEBYTECODE = "1";
    return env;
}

async function runSubprocess(
    cmd: string,
    args: string[],
    cwd: string,
    env: NodeJS.ProcessEnv
): Promise<{ stdout: string; stderr: string; exitCode: number }> {
    try {
        const { stdout, stderr } = await execFileAsync(cmd, args, {
            cwd,
            timeout: 60_000,
            maxBuffer: 10 * 1024 * 1024,
            env,
        });
        return { stdout, stderr, exitCode: 0 };
    } catch (error: any) {
        return {
            stdout: error.stdout ?? "",
            stderr: error.stderr ?? error.message ?? "",
            exitCode: typeof error.code === "number" ? error.code : 1,
        };
    }
}

// --- DELEGATED VALIDATION: clean_py validate <temp_file> ---
async function runCleanPy(
    pythonBin: string,
    tempFilePath: string,
    displayPath: string,
    effectiveWorkspace: string,
    env: NodeJS.ProcessEnv
): Promise<string[]> {
    const args = [
        "-m",
        "clean_py",
        "validate",
        tempFilePath,
        "--target",
        displayPath,
        "--workspace",
        effectiveWorkspace,
        "--json",
    ];

    const result = await runSubprocess(pythonBin, args, effectiveWorkspace, env);

    if (result.exitCode === 0) {
        try {
            const parsed = JSON.parse(result.stdout);
            if (parsed && Array.isArray(parsed.errors) && parsed.errors.length === 0) {
                return [];
            }
            if (parsed && Array.isArray(parsed.errors)) {
                return parsed.errors.map((e: unknown) => String(e));
            }
        } catch {
            return [];
        }
        return [];
    }

    try {
        const parsed = JSON.parse(result.stdout || result.stderr);
        if (parsed && Array.isArray(parsed.errors)) {
            return parsed.errors.map((e: unknown) => String(e));
        }
    } catch {
        const output = result.stdout || result.stderr;
        return [`[CLEAN_PY ERROR]\n${truncate(sanitizeOutput(output, tempFilePath, displayPath))}`];
    }

    return [`[CLEAN_PY ERROR] Non-zero exit (${result.exitCode}) but malformed JSON response.`];
}

// --- SECURITY & PATH SANITIZATION ---
async function resolveSecureTargetPath(
    workspaceDir: string,
    filePath: string
): Promise<{ absoluteTargetPath: string; effectiveWorkspace: string; displayPath: string }> {
    if (typeof filePath !== "string" || filePath.trim().length === 0) {
        throw new SecurityError("file_path must be a non-empty string.");
    }

    if (/[\0\n\r]/.test(filePath)) {
        throw new SecurityError("file_path contains forbidden control characters.");
    }

    let candidatePath: string;
    if (path.isAbsolute(filePath)) {
        candidatePath = path.normalize(filePath);
    } else {
        candidatePath = path.resolve(workspaceDir, filePath);
    }

    // Find effective repository workspace root
    let effectiveWorkspace = workspaceDir;
    let curr = path.dirname(candidatePath);
    while (curr && curr !== path.dirname(curr)) {
        const hasPyproject = await fs.stat(path.join(curr, "pyproject.toml")).catch(() => null);
        const hasGit = await fs.stat(path.join(curr, ".git")).catch(() => null);
        if (hasPyproject?.isFile() || hasGit) {
            effectiveWorkspace = curr;
            break;
        }
        curr = path.dirname(curr);
    }

    const rel = path.relative(effectiveWorkspace, candidatePath);
    if (!rel || rel === "." || rel.split(path.sep)[0] === "..") {
        const relWs = path.relative(workspaceDir, candidatePath);
        if (!relWs || relWs === "." || relWs.split(path.sep)[0] === "..") {
            throw new SecurityError("file_path resolves outside the allowed workspace.");
        }
    }

    const normalizedRel = rel.split(path.sep).join("/").toLowerCase();
    const deniedDirectories = [".git", ".opencode", ".venv", "node_modules"];

    for (const denied of deniedDirectories) {
        if (normalizedRel === denied || normalizedRel.startsWith(`${denied}/`)) {
            throw new SecurityError(`Writing into '${denied}' is strictly forbidden.`);
        }
    }

    if (path.extname(candidatePath).toLowerCase() !== ".py") {
        throw new SecurityError("Only .py files are allowed to be written by this tool.");
    }

    const displayPath = path.relative(effectiveWorkspace, candidatePath).split(path.sep).join("/");
    return { absoluteTargetPath: candidatePath, effectiveWorkspace, displayPath };
}

// --- TOOL EXPORT ---
export const cleanPythonTool = tool({
    description:
        "Deterministically verifies Python code against strict quality constraints (Ruff, MyPy strict, Radon CC < 6, AST anti-slop) by delegating to the `clean_py` pip package, before atomically writing to disk. Enforces secure writes inside the workspace.",
    args: {
        file_path: tool.schema.string().describe("Target path (relative or absolute) inside the workspace, e.g., 'src2/models/user.py'"),
        pydantic_architecture_plan: tool.schema.string().describe("Workflow explanation proving architecture safety & constraint adherence."),
        code_payload: tool.schema.string().describe("Complete Python source code to verify and save."),
    },

    async execute(args, context) {
        try {
            console.log(`[CLEAN PYTHON AUDIT TRAIL] Target: ${args.file_path}`);

            const rawWorkspaceDir = path.resolve(context?.directory || process.cwd());
            let workspaceDir: string;
            try {
                workspaceDir = await fs.realpath(rawWorkspaceDir);
            } catch {
                workspaceDir = rawWorkspaceDir;
            }

            const { absoluteTargetPath, effectiveWorkspace, displayPath } = await resolveSecureTargetPath(
                workspaceDir,
                args.file_path
            );

            const targetDir = path.dirname(absoluteTargetPath);
            await fs.mkdir(targetDir, { recursive: true });

            // Check for Bypass Flag
            if (process.env.DISABLE_CLEAN_PYTHON === "true") {
                await fs.writeFile(absoluteTargetPath, args.code_payload, "utf-8");
                retryTracker.delete(absoluteTargetPath);
                return `[BYPASS ACTIVE] Code written directly to '${displayPath}' without linter checks (DISABLE_CLEAN_PYTHON=true).`;
            }

            // Manage Tracker Size
            if (retryTracker.size > MAX_TRACKER_SIZE) {
                const oldestKey = retryTracker.keys().next().value;
                if (oldestKey) retryTracker.delete(oldestKey);
            }

            try {
                const stat = await fs.lstat(absoluteTargetPath);
                if (stat.isSymbolicLink() || stat.isDirectory()) {
                    return "SECURITY VIOLATION: Target file must not be a symlink or directory.";
                }
            } catch (err: any) {
                if (err.code !== "ENOENT") return `INFRASTRUCTURE ERROR: Unable to stat target file: ${err.message}`;
            }

            const { pythonBin, venvDir } = await getPythonEnvironment(absoluteTargetPath, effectiveWorkspace);
            const subprocessEnv = buildSubprocessEnv(venvDir);

            // Create secure temporary file in the target directory
            const tempFileName = `.tmp-${crypto.randomUUID()}-${path.basename(absoluteTargetPath)}`;
            const tempFilePath = path.join(targetDir, tempFileName);
            let tempFileCreated = false;

            try {
                const handle = await fs.open(tempFilePath, "wx", 0o600);
                tempFileCreated = true;
                await handle.writeFile(args.code_payload, "utf-8");
                await handle.close();

                const validationErrors = await runCleanPy(
                    pythonBin,
                    tempFilePath,
                    displayPath,
                    effectiveWorkspace,
                    subprocessEnv
                );

                if (validationErrors.length > 0) {
                    const activeCount = (retryTracker.get(absoluteTargetPath)?.count || 0) + 1;

                    if (activeCount >= MAX_VALIDATION_ATTEMPTS) {
                        retryTracker.delete(absoluteTargetPath);
                        return [
                            `[FATAL QUALITY FAILURE] Could not satisfy quality constraints for '${displayPath}' after ${MAX_VALIDATION_ATTEMPTS} attempts.`,
                            "Action: Fix errors manually, refine prompt/model, or set DISABLE_CLEAN_PYTHON=true to bypass.",
                            "---",
                            validationErrors.join("\n\n"),
                        ].join("\n");
                    }

                    retryTracker.set(absoluteTargetPath, { count: activeCount });

                    return [
                        "VALIDATION FAILED. Do not apologize. Do not output conversational text.",
                        `Fix the specific errors below and invoke the tool again. (Attempt ${activeCount}/${MAX_VALIDATION_ATTEMPTS})`,
                        "---",
                        validationErrors.join("\n\n"),
                    ].join("\n");
                }

                // Atomic File System Rename
                await fs.rename(tempFilePath, absoluteTargetPath);
                retryTracker.delete(absoluteTargetPath);

                return `SUCCESS: Code passed clean_py quality constraints (Ruff, Pyright, Radon CC < 6, AST anti-slop). Saved to '${displayPath}'.`;

            } finally {
                if (tempFileCreated) {
                    await fs.unlink(tempFilePath).catch(() => { });
                }
            }
        } catch (error: any) {
            if (error instanceof SecurityError) return `SECURITY VIOLATION: ${error.message}`;
            if (error instanceof InfrastructureError) return `INFRASTRUCTURE ERROR: ${error.message}`;
            return `FATAL ERROR: ${error?.message ?? String(error)}`;
        }
    },
});

export const cleanPythonPlugin: Plugin = async () => {
    return {
        tool: {
            clean_python: cleanPythonTool,
        },
    };
};

(cleanPythonPlugin as any).id = "clean-python";

export default {
    id: "clean-python",
    server: cleanPythonPlugin,
};
