import {parseCommand, type CallCommand, type TaskCommand} from "../chat/commandParser.js";
import {resolveTaskCommand} from "../chat/taskInterpreter.js";
import {executeMcpCommand, formatMcpResult} from "../runtime/mcp.js";
import {runScriptTaskToString} from "../runtime/script.js";
import type {TaskContext} from "../tasks/types.js";

export interface CommandExecutionContext extends TaskContext {}

export async function executeSlashCommand(
  input: string,
  context: CommandExecutionContext
): Promise<{lines: string[]; isError?: boolean; shouldExit?: boolean}> {
  const parsed = parseCommand(input);

  switch (parsed.kind) {
    case "help":
      return {lines: [overviewMessage()]};

    case "exit":
      return {lines: ["Goodbye! 👋"], shouldExit: true};

    case "ping":
    case "list":
    case "init":
      return await executeMcp(parsed.kind, context);

    case "call":
      return await executeCall(parsed, context);

    case "task": {
      const resolution = resolveTaskCommand(parsed as TaskCommand);
      if ("error" in resolution) {
        return {lines: [resolution.error], isError: true};
      }
      const result = await runScriptTaskToString(parsed.category, resolution.task, resolution.values, context);
      const lines = [
        `$ ${result.command.command} ${result.command.args.join(" ")}`,
        result.stdout.trim(),
        result.stderr ? `stderr:\n${result.stderr.trim()}` : "",
        `exitCode: ${result.exitCode ?? 0}`
      ]
        .filter((line) => line && line.trim().length > 0)
        .join("\n\n");
      return {lines: [lines]};
    }

    case "unknown":
    default:
      return {lines: [parsed.message], isError: true};
  }
}

async function executeMcp(command: "ping" | "list" | "init", context: CommandExecutionContext) {
  const {handshake, response} = await executeMcpCommand(
    command,
    context.gatewayUrl,
    context.gatewayToken,
    context.backendToken
  );
  const lines = formatMcpResult(command, handshake, response);
  return {lines};
}

async function executeCall(parsed: CallCommand, context: CommandExecutionContext) {
  if (!parsed.tool) {
    return {lines: ["Tool name is required for /call."], isError: true};
  }

  let args: Record<string, unknown> = {};
  if (parsed.argsJson) {
    try {
      args = JSON.parse(parsed.argsJson);
    } catch (error) {
      return {lines: [`Invalid JSON for args: ${(error as Error).message}`], isError: true};
    }
  }

  const {handshake, response} = await executeMcpCommand(
    "call",
    context.gatewayUrl,
    context.gatewayToken,
    context.backendToken,
    {tool: parsed.tool, args}
  );
  const lines = formatMcpResult("call", handshake, response, parsed.tool);
  return {lines};
}

export function overviewMessage(): string {
  const commands = [
    { cmd: "/ping", desc: "Check MCP gateway connectivity" },
    { cmd: "/list", desc: "List MCP tools" },
    { cmd: "/call", args: "tool=<name> args='<json>'", desc: "Invoke a tool" },
    { cmd: "/init", desc: "Initialise a session" },
    { cmd: "/exit", desc: "Exit the CLI (aliases: /quit, /q)" },
    { cmd: "/help", desc: "Show this help message" },
    { cmd: "/retry", desc: "Retry authentication" },
    { cmd: "/refresh", desc: "Refresh OAuth tokens (auto-runs generate_creds.sh)" }
  ];

  const maxCmdLength = Math.max(...commands.map(c => (c.cmd + (c.args ? " " + c.args : "")).length));

  const formatted = commands.map(({ cmd, args, desc }) => {
    const fullCmd = cmd + (args ? " " + args : "");
    const padding = " ".repeat(maxCmdLength - fullCmd.length + 2);
    return `  ${fullCmd}${padding}${desc}`;
  });

  return [
    "Available commands:",
    ...formatted,
    "",
    "Registry scripts:",
    "  /service <subcommand>         Service management (add, delete, monitor, test, groups)",
    "  /import <subcommand>          Import from registry (dry, apply)",
    "  /user <subcommand>            User management (create-m2m, create-human, delete, list)",
    "  /diagnostic <subcommand>      Run diagnostics (run-suite, run-test)",
    "",
    "Tip: Use natural language when ANTHROPIC_API_KEY is set to let Claude decide which tools to call."
  ].join("\n");
}
