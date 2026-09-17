# Local worker capacity: T610

This document defines what the current local worker can reasonably do, what it should not do, and how `alt-claude` should use it alongside Codex/Copilot and other providers.

The goal is not to turn the T610 into a general-purpose AI server. The goal is to exploit an already-owned machine for bounded, asynchronous development work and other backend jobs without spending on new subscriptions, API credits, GPUs, or hardware.

## Current machine

Observed hardware:

- Dell PowerEdge T610;
- 2 x Intel Xeon E5620 @ 2.40 GHz;
- 8 physical cores / 16 hardware threads total;
- 64 GB DDR3 ECC Registered RAM;
- Westmere generation CPU, without AVX/AVX2;
- no useful GPU for modern LLM inference.

This is a machine with useful RAM capacity and reasonable aggregate CPU concurrency, but low single-thread performance and poor inference efficiency compared with modern hardware.

The practical consequence is important: **the T610 is more valuable as a general development/background worker than as a dedicated LLM appliance.**

## Measured LLM behavior

The local worker currently uses `llama.cpp` and Qwen2.5-Coder-1.5B-Instruct GGUF.

Measurements from the current acceptance benchmarks on the T610:

- prompt evaluation: about 10-12 tokens/s in the tested prompts;
- generation: about 0.39-0.40 tokens/s;
- easy bounded edit: about 98 seconds end-to-end;
- medium function implementation with rules and tests: about 195 seconds end-to-end;
- successful medium example: implementation of `clamp(value, minimum, maximum)` including validation and passing unit tests.

These numbers are measurements, not guarantees. Runtime depends on prompt size, generated output, context, contention and task shape.

The critical design lesson is that generation is expensive while deterministic local work is cheap. Therefore the worker should ask the model for the shortest useful artifact possible, while Python/Git/test tooling performs validation, diff generation, file restrictions and test execution.

## What the local LLM is for

Use the local model for bounded implementation where the planner already knows what must be done.

Good candidates:

- implement one small function from a precise contract;
- small CRUD or adapter boilerplate;
- mechanical refactors with an explicit file allow-list;
- add or repair a small test;
- transform a clearly identified piece of code;
- produce a small configuration or data file;
- repetitive implementation that Codex/Copilot can review afterward.

Do not delegate to the local model:

- architecture decisions;
- broad repository exploration;
- ambiguous product requirements;
- distributed-system debugging across many components;
- security-sensitive changes without external review;
- large rewrites;
- tasks that require long explanations or large generated files;
- autonomous commit, push or merge decisions.

The intended topology is:

```text
Codex / Copilot / capable planner
        |
        | bounded task contract
        v
alt-claude-slave on T610
        |
        | final file content
        v
Deterministic executor
  - allowed-file validation
  - Git diff generation
  - tests
  - safety checks
        |
        v
Codex / Copilot review
```

The local model is a worker, not the planner and not the final reviewer.

## The T610 should not be LLM-only

LLM inference is one of the least efficient workloads for this hardware. The server should also be used for work that benefits from RAM, background execution and many ordinary CPU threads.

Good non-LLM workloads include:

- Git mirrors and repository caches;
- CI runners for small and medium projects;
- unit/integration test jobs;
- lint and static analysis;
- release/package generation;
- documentation generation;
- backup, synchronization and archival jobs;
- crawlers and scheduled automation;
- Python, Node.js and Go workers/APIs;
- RabbitMQ/Redis-style development services;
- PostgreSQL for development and internal tooling;
- MinIO or other internal object storage when appropriate;
- batch audio/transcription jobs where latency is not important;
- indexing and document-processing jobs;
- nightly agents and maintenance tasks.

In other words, treat the T610 as a **general development worker with a local LLM capability**, not as a local-LLM box that happens to run other services.

## Workload classes

### Class A - interactive/latency-sensitive

Examples: user-facing production API, critical database, real-time service.

Do not colocate these with unrestricted LLM inference. The local model can consume CPU continuously for minutes and cause latency spikes.

If such a service must live on the T610, give it explicit CPU and memory guarantees and keep the LLM in a separate container/cgroup with hard limits.

### Class B - normal development services

Examples: dev databases, internal APIs, queues, Git services, dashboards.

These can coexist with the LLM if isolated with Incus/cgroups. Expect degraded response time while inference is active unless CPU affinity/limits keep sufficient capacity free.

### Class C - batch/background

Examples: tests, builds, indexing, backups, transcription, crawlers, local LLM tasks.

This is the natural workload class for the T610. These jobs can queue, run asynchronously and share the machine according to priority.

## Initial resource policy

The current LLM benchmark uses 12 inference threads. That is a useful measured starting point, not a permanent reservation.

Recommended operating policy:

1. Run the LLM in its own Incus container.
2. Allow only one inference task at a time.
3. Start with up to 12 threads for inference because that is what the successful benchmarks used.
4. Keep at least some CPU capacity outside the LLM container for SSH, Incus, monitoring and ordinary services.
5. Do not run heavy build/transcription/indexing jobs concurrently with an LLM benchmark unless deliberately testing contention.
6. Queue Class C jobs instead of letting all of them saturate the server simultaneously.
7. Prefer `nice`/cgroup priority and explicit CPU limits over relying on good behavior from individual processes.
8. Measure before changing thread count, CPU pinning, context size or NUMA placement.

Because the machine has two sockets, CPU placement may matter. Future benchmarks should compare thread counts and CPU affinity before adopting a fixed cpuset. Do not assume that `16 threads` is automatically faster than 8 or 12 on this generation of hardware.

## Memory policy

64 GB is one of the T610's strongest remaining assets.

The 1.5B/3B quantized coding models fit comfortably, leaving substantial memory for development services and filesystem cache. Memory therefore is usually not the first bottleneck; CPU generation speed is.

Avoid filling RAM merely because it exists. Keep enough headroom for filesystem cache, Incus, development databases and concurrent background jobs. Swap activity during inference/builds should be treated as a warning sign.

## Context and output policy for local models

Large context is not free. Even though the model configuration may allow a larger context, the planner should send only what the worker needs.

Preferred task contract:

- one objective;
- explicit allowed files;
- explicit tests;
- only relevant source snippets/files;
- short expected output;
- no repository-wide context unless proven necessary.

Prefer final-file-content responses over asking a small model to manufacture a Git patch. Git is deterministic and should remain outside the model.

For the current 1.5B worker, minimize generated tokens aggressively. A model that generates at roughly 0.4 token/s spends about 2.5 seconds per generated token. A needlessly verbose 200-token response can therefore consume roughly eight minutes just in generation.

## Delegation policy for alt-claude

When a capable planner has quota available, the preferred flow is:

```text
plan/reason: Codex (primary) or Copilot
implement bounded subtask: local slave when suitable
validate/test: local deterministic tools
review/integrate: Codex or Copilot
```

The planner should keep the task itself when any of these are true:

- it needs architectural reasoning;
- the change spans many files or subsystems;
- the expected generated code is large;
- failure would be difficult to detect with tests;
- the specification is still being discovered;
- turnaround of several minutes is worse than doing it directly.

Delegate locally when all or most of these are true:

- task is precisely specified;
- small allowed-file set;
- strong tests or deterministic validation exist;
- generated output is short;
- it can run asynchronously;
- saving external quota is valuable.

## Other profitable uses of the machine

When the LLM is idle, the same worker pool can consume queued jobs such as:

```text
repo sync -> lint -> unit tests -> build -> package -> artifact
          -> docs/indexing
          -> backups
          -> transcription
          -> local-model task
```

A future scheduler can assign priority classes and resource limits so an LLM task does not compete blindly with a build or transcription job.

A useful target is not maximum CPU utilization at every moment. It is maximum useful work per day without making interactive development unreliable.

## What not to put here

Avoid using the T610 as the sole home of:

- latency-critical production databases;
- high-traffic public APIs without redundancy;
- heavy video processing;
- high-volume embedding generation;
- large-model inference;
- workloads that require modern vector CPU instructions;
- anything where power efficiency is economically important;
- anything whose failure would make this development worker a single point of business failure.

## Capacity decisions must be measured

Do not convert current observations into permanent folklore.

Maintain benchmark evidence for:

- model and quantization;
- context size;
- prompt tokens;
- generated tokens;
- prompt-evaluation tokens/s;
- generation tokens/s;
- end-to-end task time;
- tests passed/failed;
- thread count;
- concurrent system load.

The same rule applies to non-LLM jobs: record wall time and contention for builds, transcription and CI before assigning permanent CPU shares.

## Current conclusion

The T610 is useful.

It is not a fast AI machine, but it has already demonstrated that a 1.5B coding model can complete bounded programming work and pass tests. Its better long-term role is broader: **an asynchronous development worker that runs local LLM implementation, CI, automation and batch processing under explicit resource controls.**

The architecture should exploit the difference between expensive reasoning/generation and cheap deterministic computation: use capable external planners sparingly for reasoning, the T610 for bounded local work, and normal code/tools for everything that does not require a model.
