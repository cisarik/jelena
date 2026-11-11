# Agent Instructions

<!-- BEGIN MANAGED AP INTEGRATION -->
## Analytic Programming

This project uses Analytic Programming through the pinned Git submodule at `.ap/`.
The exact AP version is the commit recorded by this repository's `.ap` gitlink.

Required reading:
- All participants read `.ap/AP.md`.
- Orchestrators also read `.ap/AP_ORCHESTRATOR.md`.
- Workers also read `.ap/AP_WORKER.md`.
- Prompt structures are in `.ap/PROMPT_CONTRACTS.md`.

Project-specific rules outside this managed block remain authoritative within
their scope. Task authority comes only from the current authoritative
Orchestrator prompt.

Treat `.ap/` as read-only during ordinary project work. Protocol updates require
a separate explicit AP update task.
<!-- END MANAGED AP INTEGRATION -->

# Project-local rules

## Communication

- The Cooperator is Michal. Speak to him in Slovak and use feminine grammatical gender for the assistant's self-reference.
- Worker prompts and formal Worker reports are in English. Formal reports begin exactly `### Report for ORCHESTRATOR_CHAT`.
- The Cooperator's Blender UI is Slovak. Owner UI steps use verified Slovak Blender labels and recognizable English addon labels.
- Shell examples are fish-compatible.
- Manual Cooperator delivery is the selected route. The Cooperator persists prompts, reports and notes; Meta Git operations belong to the Cooperator.

## Environment

- Verified on 2026-11-11: macOS Apple silicon, 8 GB RAM; Blender 5.2.3 LTS; Cursor 3.29.15; local MCP server `blender` via `uvx --python 3.11 mcp-for-blender`; Blender addon `MCP for Blender` 1.8, protocol 15; loopback `127.0.0.1:9876`.
- MCP remains local. Optional paid generators and external asset services remain disabled. `MCP_DISABLE_TELEMETRY=1` is set in the Cooperator's MCP configuration.
- One live Blender instance. No background Blender, second instance, or file replacement without an exact grant.
- No paid assets, paid generation services, credential changes, or external uploads without a specific Cooperator decision.

## Blender safety

- No scene mutation, save, close, reopen or render without an explicit task grant and a recoverable checkpoint.
- A server listed in Cursor is not proof of the correct scene. Require direct MCP evidence of the live file and scene.
- Preserve `Jelena/Jelena.blend` and `Jelena/Jelena_Realistic_v001.blend` as baselines. Do not overwrite them without a Cooperator decision.
- Judge visible quality through inspected images, not object counts or successful script execution alone.

## Assets, binaries and renders

- Use ordinary Git for the current small binaries. Do not add Git LFS without a concrete measured need.
- Keep backups, local checkpoints, caches and temporary renders out of Git via `.gitignore`.
- Commit retained render evidence only when a task grant names the exact path and manifest.
- Preserve original deliverables and their hashes; no history rewriting.
- Record external asset source, license and acquisition date before use.

## Protocol

- The governing AP source is the pinned `.ap` submodule. `AP.md` alone owns protocol meaning.
- Do not copy universal AP files into the project root.
- Do not silently update AP or use a newer public revision.
- Project-local rules extend but do not override universal AP.

## Closure

- The only authoritative closure signal is `JELENA — LOGICKÝ CELOK UZAVRETÝ ORCHESTRÁTOROM`.
- Only the ORCHESTRATOR emits it. Workers signal completion through their terminal report status.
