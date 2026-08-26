# CSE Workbench research

Status: paused
Last reviewed: 2026-08-25

This document family investigates whether Agentic Computational Science and
Engineering should grow from a Codex plugin into a standalone application for
computational science and physical-world engineering.

The research is deliberately separate from the accepted plugin design. The
current plugin remains the installed and validated product. Nothing in this
directory selects a runtime, commits the project to a desktop framework, or
changes the eight workflow stages and six supporting tools.

## Current decision

A standalone CSE Workbench remains worth investigating, but implementation is
paused. The Codex plugin is the current product and should mature through real
computational, coding, analysis, and document work before its behavior is moved
into a separate harness.

The most promising implementation boundary is:

- the CSE application owns the scientific working method, project state,
  native figures, retained values, equations, source evidence, numerical
  checks, permissions, and result presentation;
- an existing agent runtime owns model calls, message history, tool execution,
  interruption, and compaction; and
- the current plugin remains a portable adapter until a standalone application
  proves that it is more useful.

Two runtimes currently deserve direct comparison:

1. Codex app-server, which retains OpenAI's Codex agent loop, sandbox, and
   approval system.
2. Pi, which provides a small multi-provider agent runtime with unusually deep
   prompt, tool, event, and compaction customization.

Pi has moved from a secondary alternative to a leading prototype candidate.
It has an embeddable SDK, an RPC mode for non-Node clients, and several
third-party desktop and web interfaces. The remaining concern is that Pi does
not include a built-in permission sandbox; the CSE application would own that
boundary.

## Documents

- [Harness landscape](HARNESS-LANDSCAPE.md) explains how the surrounding agent
  runtime changes model behavior and speed, compares the investigated systems,
  and maps the current plugin into a possible CSE Workbench.
- [Pi feasibility](PI-FEASIBILITY.md) records Pi's supported embedding and
  extension surfaces, existing graphical applications, security limitations,
  and the smallest useful prototype.
- [Pi ecosystem audit](PI-ECOSYSTEM-AUDIT.md) identifies open-source Pi
  packages and graphical shells that can supply notebook execution, previews,
  external tools, permissions, and desktop integration without rebuilding each
  capability for CSE.

## Research discipline

Each document separates:

- observed behavior stated by an authoritative source;
- an inference about CSE applicability;
- a provisional product recommendation; and
- an unresolved question requiring a prototype or measurement.

New research should update the existing document that owns the question. Add a
new file only when the subject has a distinct decision and enough evidence to
remain useful on its own. Do not turn this directory into a backlog or repeat
accepted plugin doctrine already held under `references/`.

## Resumption condition

Resume Workbench implementation only after repeated plugin use identifies a
material limitation that cannot be addressed cleanly through a thin skill,
shared reference, repository-owned check, or supporting tool. At that point,
the next useful evidence is a narrow vertical prototype, not a complete IDE.
It should compare Pi and Codex app-server on the same CSE tasks with:

- one local repository;
- one model-versus-observation plotting task;
- one numerical convergence task;
- one source-linked equation task;
- one permission-gated file change; and
- the same retained tables, quantities, units, and acceptance checks.

Measure wall time, model and tool calls, input and output tokens, scientific
errors, unnecessary code, user corrections, and whether the final result can
be reproduced from retained files.
