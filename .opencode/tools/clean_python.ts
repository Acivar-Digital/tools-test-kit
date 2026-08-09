// verify_and_commit_code.ts
//
// Production-Ready OpenCode Tool: Validated Python File Writer.
// Synthesized and refined for strict security, performance, and deterministic LLM constraints.

import { tool } from "@opencode-ai/plugin";
import { execFile } from "node:child_process";
import * as crypto from "node:crypto";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

// --- CONFIGURATION ---
const MAX_VALIDATION_ATTEMPTS = 10;
const RADON_COMPLEXITY_LIMIT = 6;
const OUTPUT_LIMIT = 20_000;
const MAX_TRACKER_SIZE = 1000;

// --- STATE MANAGEMENT ---
interface RetryState {
    count: number;
}
const retryTracker = new Map<string, RetryState>();

interface ExecResult {
    stdout: string;
    stderr: string;
    exitCode: number;
}

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
function escapeRegExp(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function truncate(value: string, limit: number = OUTPUT_LIMIT): string {
    if (!value) return "";
    if (value.length <= limit) return value;
    return `${value.slice(0, limit)}\n... output truncated`;
}

function sanitizeOutput(rawOutput: string, tempPath: string, targetPath: string): string {
    if (!rawOutput) return "";
    try {
        const escapedTempPath = escapeRegExp(tempPath);
        return rawOutput.replace(new RegExp(escapedTempPath, "g"), targetPath).trim();
    } catch {
        return rawOutput.trim();
    }
}

function isWithinWorkspace(parent: string, child: string): boolean {
    const rel = path.relative(parent, child);
    if (rel === "") return true;
    if (path.isAbsolute(rel)) return false;
    return rel.split(path.sep)[0] !== "..";
}

// --- PYTHON INFRASTRUCTURE ---
async function getPythonEnvironment(workspaceDir: string): Promise<{ pythonBin: string; venvDir: string }> {
    const venvDir = path.join(workspaceDir, ".venv");
    const candidates = [
        path.join(venvDir, "Scripts", "python.exe"), // Windows
        path.join(venvDir, "bin", "python"),         // Unix
        path.join(venvDir, "bin", "python3"),        // Unix fallback
    ];

    for (const candidate of candidates) {
        const stats = await fs.stat(candidate).catch(() => null);
        if (stats?.isFile()) {
            return { pythonBin: candidate, venvDir };
        }
    }

    throw new InfrastructureError(
        "Python virtual environment not found. Expected a usable Python binary in .venv/bin/python or .venv/Scripts/python.exe."
    );
}

function buildSubprocessEnv(venvDir: string): NodeJS.ProcessEnv {
    const env: NodeJS.ProcessEnv = { ...process.env };
    env.VIRTUAL_ENV = venvDir;
    env.PYTHONIOENCODING = "utf-8";
    env.PYTHONDONTWRITEBYTECODE = "1";
    return env;
}

async function runSubprocess(cmd: string, args: string[], cwd: string, env: NodeJS.ProcessEnv): Promise<ExecResult> {
    try {
        const { stdout, stderr } = await execFileAsync(cmd, args, {
            cwd,
            timeout: 30_000,
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

async function checkLinterDependencies(pythonBin: string, workspaceDir: string, env: NodeJS.ProcessEnv): Promise<void> {
    const linters = ["ruff", "mypy", "radon"];
    const missing: string[] = [];

    for (const linter of linters) {
        const result = await runSubprocess(pythonBin, ["-m", linter, "--version"], workspaceDir, env);
        if (result.exitCode !== 0) {
            missing.push(linter);
        }
    }

    if (missing.length > 0) {
        throw new InfrastructureError(
            `Required Python modules missing or broken: ${missing.join(", ")}. Please run 'pip install ruff mypy radon' inside .venv.`
        );
    }
}

// --- SECURITY & PATH SANITIZATION ---
async function resolveSecureTargetPath(workspaceDir: string, filePath: string): Promise<string> {
    if (typeof filePath !== "string" || filePath.trim().length === 0) {
        throw new SecurityError("file_path must be a non-empty string.");
    }

    if (/[\0\n\r]/.test(filePath)) {
        throw new SecurityError("file_path contains forbidden control characters.");
    }

    if (path.isAbsolute(filePath)) {
        throw new SecurityError("file_path must be a relative workspace path.");
    }

    const candidatePath = path.resolve(workspaceDir, filePath);
    const rel = path.relative(workspaceDir, candidatePath);

    if (!rel || rel === "." || path.isAbsolute(rel) || rel.split(path.sep)[0] === "..") {
        throw new SecurityError("file_path resolves outside the allowed workspace (Path traversal detected).");
    }

    const normalizedRel = rel.split(path.sep).join("/").toLowerCase();
    const deniedDirectories = [".git", ".opencode", ".venv", "node_modules"];

    for (const denied of deniedDirectories) {
        if (normalizedRel === denied || normalizedRel.startsWith(`${denied}/`)) {
            throw new SecurityError(`Writing into '${denied}' is strictly forbidden.`);
        }
    }

    const basenameLower = path.basename(candidatePath).toLowerCase();
    const deniedFiles = [".env", "package.json", "package-lock.json", "bun.lockb", "tsconfig.json", ".gitignore"];

    if (basenameLower.startsWith(".env") || deniedFiles.includes(basenameLower)) {
        throw new SecurityError(`Writing configuration file '${basenameLower}' is forbidden.`);
    }

    if (path.extname(candidatePath).toLowerCase() !== ".py") {
        throw new SecurityError("Only .py files are allowed to be written by this tool.");
    }

    return candidatePath;
}

// --- LINTER EXECUTION ---

const AST_POLICY_CHECKER = `
import ast, json, sys

if len(sys.argv) < 2: sys.exit(3)
path = sys.argv[1]

try:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()
    tree = ast.parse(source, filename=path)
except SyntaxError as exc:
    print(json.dumps({"syntax_error": f"{exc.lineno}:{exc.offset}: {exc.msg}"}))
    sys.exit(2)
except Exception:
    sys.exit(3)

issues = []
for node in ast.walk(tree):
    if not isinstance(node, ast.ExceptHandler): continue
    if node.type is None:
        issues.append(f"line {node.lineno}: bare 'except:' is forbidden; catch a specific exception")
    handler_is_broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"})
    if handler_is_broad and node.body and all(isinstance(stmt, ast.Pass) for stmt in node.body):
        issues.append(f"line {node.lineno}: swallowed broad exception with 'pass' is forbidden (anti-slop policy)")

print(json.dumps(issues))
sys.exit(1 if issues else 0)
`;

async function runAstPolicyCheck(pythonBin: string, tempFilePath: string, workspaceDir: string, env: NodeJS.ProcessEnv, displayPath: string): Promise<string[]> {
    const result = await runSubprocess(pythonBin, ["-c", AST_POLICY_CHECKER, tempFilePath], workspaceDir, env);
    if (result.exitCode === 0) return [];

    const output = result.stdout || result.stderr;
    if (result.exitCode === 2) {
        try {
            const parsed = JSON.parse(result.stdout);
            if (parsed?.syntax_error) return [`[PYTHON SYNTAX ERROR] ${displayPath}: ${parsed.syntax_error}`];
        } catch { }
        return [`[PYTHON SYNTAX ERROR]\n${truncate(sanitizeOutput(output, tempFilePath, displayPath))}`];
    }

    try {
        const parsed = JSON.parse(result.stdout);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed.map(issue => `[AST POLICY] ${String(issue)}`);
    } catch { }

    return [`[AST POLICY ERROR]\n${truncate(sanitizeOutput(output, tempFilePath, displayPath))}`];
}

async function runRuff(pythonBin: string, tempFilePath: string, workspaceDir: string, env: NodeJS.ProcessEnv, displayPath: string): Promise<string[]> {
    const result = await runSubprocess(pythonBin, ["-m", "ruff", "check", "--output-format", "json", tempFilePath], workspaceDir, env);
    if (result.exitCode === 0) return [];

    const output = result.stdout || result.stderr;
    try {
        const parsed = JSON.parse(output);
        const diagnostics = Array.isArray(parsed) ? parsed : (Array.isArray(parsed?.diagnostics) ? parsed.diagnostics : []);
        if (diagnostics.length === 0) throw new Error();

        return diagnostics.map((d: any) => {
            const line = d?.location?.row ?? d?.location?.line ?? "?";
            return `${displayPath}:${line}: [${d.code || "ERR"}] ${d.message}`;
        });
    } catch {
        return [`[RUFF LINTER ERRORS]\n${truncate(sanitizeOutput(output, tempFilePath, displayPath))}`];
    }
}

async function runMypy(pythonBin: string, tempFilePath: string, finalTargetPath: string, targetExists: boolean, workspaceDir: string, env: NodeJS.ProcessEnv, displayPath: string): Promise<string[]> {
    const args = ["-m", "mypy", "--strict"];
    if (targetExists) {
        args.push("--shadow-file", finalTargetPath, tempFilePath, finalTargetPath);
    } else {
        args.push(tempFilePath);
    }

    const result = await runSubprocess(pythonBin, args, workspaceDir, env);
    if (result.exitCode === 0) return [];

    const output = result.stdout || result.stderr;
    return [`[MYPY TYPE ERRORS]\n${truncate(sanitizeOutput(output, tempFilePath, displayPath))}`];
}

async function runRadon(pythonBin: string, tempFilePath: string, workspaceDir: string, env: NodeJS.ProcessEnv, displayPath: string): Promise<string[]> {
    const result = await runSubprocess(pythonBin, ["-m", "radon", "cc", "-j", tempFilePath], workspaceDir, env);
    const output = result.stdout || result.stderr;

    try {
        const parsed = JSON.parse(output);
        const violations: string[] = [];

        // Radon wraps output in an object keyed by filename
        for (const [, blocks] of Object.entries(parsed)) {
            if (!Array.isArray(blocks)) continue;

            for (const block of blocks as any[]) {
                const complexity = typeof block?.complexity === "number" ? block.complexity : NaN;
                if (complexity >= RADON_COMPLEXITY_LIMIT) {
                    violations.push(`Line ${block.lineno ?? '?'}: ${block.type} '${block.name}' has CC ${complexity} (Limit: < ${RADON_COMPLEXITY_LIMIT})`);
                }
            }
        }

        if (result.exitCode !== 0 && violations.length === 0) {
            return [`[RADON ERROR]\n${truncate(sanitizeOutput(output, tempFilePath, displayPath))}`];
        }
        return violations.length > 0 ? [`[CYCLOMATIC COMPLEXITY]\n${violations.join("\n")}`] : [];

    } catch {
        if (result.exitCode === 0) return [];
        return [`[RADON ERROR]\n${truncate(sanitizeOutput(output, tempFilePath, displayPath))}`];
    }
}

// --- TOOL EXPORT ---
export default tool({
    description:
        "Deterministically verifies Python code against strict quality constraints (Ruff, MyPy strict, Radon CC < 6, AST anti-slop) before writing to disk. Enforces secure writes inside the workspace.",
    args: {
        file_path: tool.schema.string().describe("Relative target path inside the workspace, e.g., 'src/models/user.py'"),
        pydantic_architecture_plan: tool.schema.string().describe("Workflow explanation proving architecture safety & constraint adherence."),
        code_payload: tool.schema.string().describe("Complete Python source code to verify and save."),
    },

    async execute(args, context) {
        try {
            console.log(`[VERIFIER AUDIT TRAIL] Target: ${args.file_path}`);

            const rawWorkspaceDir = path.resolve(context?.directory || process.cwd());
            let workspaceDir: string;
            try {
                workspaceDir = await fs.realpath(rawWorkspaceDir);
            } catch {
                return "INFRASTRUCTURE ERROR: Workspace directory could not be resolved.";
            }

            const absoluteTargetPath = await resolveSecureTargetPath(workspaceDir, args.file_path);
            const displayPath = path.relative(workspaceDir, absoluteTargetPath).split(path.sep).join("/");

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

            // Determine if editing or creating (used by MyPy Shadowing)
            let targetExists = false;
            try {
                const stat = await fs.lstat(absoluteTargetPath);
                if (stat.isSymbolicLink() || stat.isDirectory()) {
                    return "SECURITY VIOLATION: Target file must not be a symlink or directory.";
                }
                targetExists = true;
            } catch (err: any) {
                if (err.code !== "ENOENT") return `INFRASTRUCTURE ERROR: Unable to stat target file: ${err.message}`;
            }

            // Python Environment Resolution
            const { pythonBin, venvDir } = await getPythonEnvironment(workspaceDir);
            const subprocessEnv = buildSubprocessEnv(venvDir);
            await checkLinterDependencies(pythonBin, workspaceDir, subprocessEnv);

            // Create secure temporary file
            const tempFileName = `.tmp-${crypto.randomUUID()}-${path.basename(absoluteTargetPath)}`;
            const tempFilePath = path.join(targetDir, tempFileName);
            let tempFileCreated = false;

            try {
                // 'wx' flag ensures we don't overwrite an existing file (race condition defense)
                const handle = await fs.open(tempFilePath, "wx", 0o600);
                tempFileCreated = true;
                await handle.writeFile(args.code_payload, "utf-8");
                await handle.close();

                // Run Linters sequentially to give deterministic feedback order
                const validationErrors: string[] = [];
                validationErrors.push(...(await runAstPolicyCheck(pythonBin, tempFilePath, workspaceDir, subprocessEnv, displayPath)));
                validationErrors.push(...(await runRuff(pythonBin, tempFilePath, workspaceDir, subprocessEnv, displayPath)));
                validationErrors.push(...(await runMypy(pythonBin, tempFilePath, absoluteTargetPath, targetExists, workspaceDir, subprocessEnv, displayPath)));
                validationErrors.push(...(await runRadon(pythonBin, tempFilePath, workspaceDir, subprocessEnv, displayPath)));

                if (validationErrors.length > 0) {
                    const activeCount = (retryTracker.get(absoluteTargetPath)?.count || 0) + 1;

                    if (activeCount >= MAX_VALIDATION_ATTEMPTS) {
                        retryTracker.delete(absoluteTargetPath);
                        return [
                            `[FATAL QUALITY FAILURE] Could not satisfy MyPy/Radon/Ruff constraints for '${displayPath}' after ${MAX_VALIDATION_ATTEMPTS} attempts.`,
                            "Action: Fix errors manually, refine prompt/model, or set DISABLE_CLEAN_PYTHON=true in .env to bypass.",
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

                return `SUCCESS: Code passed Ruff, MyPy Strict, Radon (CC < ${RADON_COMPLEXITY_LIMIT}), and AST anti-slop policies. Saved to '${displayPath}'.`;

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