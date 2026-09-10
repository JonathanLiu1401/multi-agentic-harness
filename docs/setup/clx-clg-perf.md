# clx / clg inference speed: measured 2026-09-02

Owner report: "inference speed on both clx and clg are very slow, much slower
than their native CLIs." Asked whether it is the tooling's fault.

## ANSWER (2026-09-02, after owner pushback)

**The gap is permission prompts, not inference.** Grok Build CLI runs with
`always-approve` (visible in its status bar). clx does not, so its tool queue
blocks waiting for a human click, and every queued tool call blocks behind it.

Same prompt, same cwd, `/read-past-sessions grok trellis-dailies ...`:

| Run | Time |
| --- | --- |
| Grok Build CLI, always-approve | **2m34s** |
| clx, interactive, prompting | **10m59s** |
| clx, `--permission-mode bypassPermissions` | **1m54s** |

With approvals out of the way clx is *faster* than the native grok CLI on the
identical task, and returned a correct 2.9 KB answer.

Breakdown of the 11-minute run (session `9f4d159f`, 32 min wall):

- **8 API calls, 59 seconds total** of inference. Median 6.5s, max 12.0s.
- **35 tool calls**, whose real execution cost, re-run by hand, is ~25s
  (`sessions.py` 0.3-0.4s per call, one `--source all` at 16.9s, home-dir glob
  15.1s).
- **Everything else - roughly 9 minutes - is the queue stalled on approvals.**

The signature is unmistakable in the timeline: four tools issued at t=14s return
at 44.9s, then three *simultaneously* at 106s (one approval releasing a blocked
queue), while later `Read` calls, once permissions were settled, return in 0.1s
each.

Secondary and much smaller: clx picked more expensive tools than grok did for the
same job - 9 Bash + 7 Glob + 16 Read + 2 Grep, against grok's 60 `read_file` +
12 `grep` and zero bash/glob. One of clx's globs (`**/daily-memory/**` over all
of `C:\Users\jonny`) costs 15.1s and returned 0 matches.

### Fix

Make clx's approval posture match grok's. Blanket `bypassPermissions` in the
launcher is the crude version; the targeted version is `permissions.allow` rules
in `~/.claude-clx/settings.json` for read-only tools (`Read`, `Glob`, `Grep`, and
the `sessions.py` Bash pattern), which keeps writes prompting. Owner's call -
nothing was changed.

---

## Original per-call analysis (correct, but it answered the wrong question)

Everything below measures per-API-call latency. It is accurate and it is why the
first pass at this concluded "not the tooling's fault" - a conclusion that was
wrong because the benchmarks used were far too small (150 numbers; count 4 files)
to expose a stall that only appears in a long agentic run with many tool calls.
Per-call latency was never the problem.

**Per API call clx and clg are as fast as or faster than the native CLIs.**

## Method

Two independent sources, because a stopwatch alone gives a number with no cause.

1. **Instrumented history.** Native Grok Build CLI logs every turn to
   `~/.grok/logs/unified.jsonl` as `shell.turn.inference_done` with
   `model_elapsed_ms`, `prompt_tokens`, `cached_prompt_tokens`,
   `tokens_per_sec`. Claude Code records `message.usage` plus timestamps per
   response in its session JSONL. Both give per-call timing on real work.
   Claude Code splits one API response across several `assistant` entries, so
   dedupe by `message.id` before timing or the median collapses to ~0.6s.
2. **Headless A/B**, 3 runs per condition. A single pair proved worthless: a
   first pass at this showed 7.8s vs 14.8s vs 5.4s for identical work, a 3x
   spread on n=1.

## Results

### Per API call, real sessions

| Path | calls | median | p90 | median prompt |
| --- | --- | --- | --- | --- |
| native grok CLI | 1565 | 12.6s | 48.3s | 137k |
| clx (gateway) | 96 | 8.2s | 23.9s | 83k |
| clg (gateway) | 317 | 4.7s | 10.5s | 109k |

Native grok runs at `xhigh` (`~/.grok/config.toml`
`default_reasoning_effort = "xhigh"`, `context_window = 500000`) while clx runs
at `high`, so this is not an apples-to-apples effort comparison. It does rule out
the gateway as a per-call tax.

### Headless A/B, 3 runs each

Pure generation, "numbers 1 to 150", no tools:

| Path | runs | median |
| --- | --- | --- |
| native grok CLI | 11.2 / 13.0 / 10.5s | **11.2s** |
| clx gateway | 11.1 / 14.7 / 9.8s | **11.1s** |

Identical. Same task with tool calls:

| Path | runs | median |
| --- | --- | --- |
| native grok CLI | 11.1 / 16.8 / 20.1s | **16.8s** |
| clx gateway | 28.0 / 19.5 / 20.5s | **20.5s** |
| native agy CLI | 11.2 / 14.1 / 22.2s | **14.1s** |
| clg gateway | blocked, see below | - |

clx is ~20% slower end to end on a tool workflow, with heavily overlapping
ranges. That is a different claim from "much slower".

### The discriminator: API calls per user turn

Per-call latency is the wrong unit. What the owner feels is wall-clock per
*turn*, which is calls-per-turn x latency. Counted by grouping assistant
`message.id`s between consecutive non-tool-result `user` entries, and for native
grok from `loop_index` in `inference_done`:

| Path | calls/turn median | mean | p90 | max | x median latency = per turn |
| --- | --- | --- | --- | --- | --- |
| clx | 1.0 | 2.4 | 6 | 16 | ~8-20s |
| native grok | 2.0 | 3.3 | 6 | 54 | ~25-38s (measured 38.5s median) |
| **clg** | **9.0** | **28.9** | **64** | **153** | **~42s to 5min** |

This is the finding. clg's per-call latency (4.7s) is the best of any path
measured, and it is still the slowest to finish a turn, because it takes ~9 calls
where grok takes 2. Consistent with its output shape: clg emits a median of 206
output tokens per call vs clx's 706 - many small tool-calling hops rather than
few large steps.

clx, by contrast, uses *fewer* calls per turn than native grok (1.0 vs 2.0) at
lower latency (8.2s vs 12.6s). Nothing measured supports clx being slower than
the native grok CLI.

## Hypotheses tested and REJECTED

Recording these so they are not re-investigated.

- **Prompt caching is broken.** No. It works: a repeated 50k prefix returned
  `cache_read_input_tokens=36224`. Real sessions cache 73% (clx) and 95% (clg)
  of turns.
- **Cache misses are the cost.** No, and this is the one that looked most
  convincing. clx misses cache on 27% of turns vs 14% native, but **a miss costs
  no measurable time**: clx miss median 8.4s vs hit median 8.1s; clg 4.5s vs
  4.7s. An early n=20 sample suggested +6s; it was noise.
- **The gateway buffers the stream, so it only feels slow.** No. SSE from the
  gateway is fully incremental: `thinking_delta` starts at **0.89s**, text at
  8.36s, 142 text deltas. TTFT is under a second.
- **Effort or the 500k window pin.** No. Native grok runs a *higher* effort and
  the same 500k window and is not faster.
- **clx carries more context per request.** No, it carries less: 83k median vs
  137k native.
- **`count_tokens` round trips.** Real but negligible, and only fired by
  `/context`: 24 calls at 100-130ms, not per turn.

## Secondary, real but narrower: cooldown amplification (Antigravity only)

Scope this carefully. Searching `isApiErrorMessage` across every real session:

| When | Profile | What |
| --- | --- | --- |
| 2026-09-02 09:59-11:05 local | clx | 6 x `429 ... cooling down via provider antigravity` |
| 2026-09-02 19:59-20:06 local | clg | 9 x same - **these are mine**, from `-p` benchmarking |

So the owner *did* hit this for real, in the morning clx sessions - but every
instance is against **Antigravity/Gemini models**, never against grok/xai. There
is no cooldown stall against grok in any real session. The single xai nginx 503 I
saw was during my own testing and did not produce a user-visible stall.

With exactly one credential per provider, any upstream 429 or 503 is a total
stall rather than a failover.

- Antigravity returns `429 RESOURCE_EXHAUSTED` to the gateway's sdk-cli
  fingerprint (CLIProxyAPI issue #5037) while native `agy -p` on the same
  account, minutes apart, works fine and answers correctly.
- On that 429 the gateway puts the only credential into a quota cooldown:
  `auth unavailable: 1 of 1 candidate(s) for model "gemini-3.8-flash-high(high)"
  are in cooldown: [reason=quota, remaining=1m26s]`. Every request in that window
  then fails in ~12ms and Claude Code backs off exponentially.
- One benchmark run sat in that retry/backoff loop for **185 seconds**.
- The same shape hit grok: a transient upstream nginx **503** from
  `cli-chat-proxy.grok.com` put the single xai credential into cooldown.

Relevant knobs in `~/cliproxyapi/config.yaml` (all currently at defaults):

- `request-retry: 3` - additional credential retry rounds on 403/408/429/500/502/503/504.
- `max-retry-interval: 30` - max cooldown wait between rounds.
- `transient-error-cooldown-seconds: 0` - 0 means the legacy 60s cooldown; `-1` disables.
- `disable-cooling: false` - `true` prevents blackout windows entirely.

With one credential per provider, cooldown buys nothing (there is nothing to fail
over to) and costs a hard stall. `disable-cooling: true` and/or
`transient-error-cooldown-seconds: -1` would remove the blackout window, and a
lower `request-retry` would fail fast instead of backing off for minutes.

**These are knobs, not a recommendation, and none were changed.** The gateway is
running stock on purpose. This path accounts for a handful of Antigravity errors,
not for the general slowness - do not tune it hoping to fix speed.

## The `/context` panel is normal

Nothing in the reported output is anomalous: 174.4k/500k is 35% used, with a 33k
autocompact buffer and 292k free. The fixed per-request overhead is ~40k tokens
(16.2k MCP tools + 10.4k system tools + 6.5k memory + 5k skills + 1.8k system
prompt). That is the only part that can be shrunk, by importing fewer MCP servers
into the profile - but it is cached on ~73-95% of turns, so shrinking it will not
move latency much.

## Caveats

- Benchmarking with `claude -p` against clg tripped the Antigravity rate limit
  and left that credential cooling down. Cooldown is in-memory
  (`save-cooldown-status: false`), so a gateway restart clears it.
- Never benchmark clg with `-p`: that is the one mode Antigravity rejects, so it
  measures the fingerprint filter, not the model. Use `~/.cc-bridge/tui_test.py`.
  clg interactive is healthy - the TUI banner reads
  "Gemini 3.8 Flash high with high effort".
- The clx-vs-native workflow comparison is n=3 with wide spread. Treat ~20% as
  directional, not precise.
