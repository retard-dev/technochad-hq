# 🧪 FLOP Devnet — Technochad Onboarding (Day One, 2026-11-03)

Our same-day pipeline onto the FLOP devnet (announced by Arthur Hayes, Nov 3).

## State
- Chain: FLOP Devnet 1.1.0 · `wss://rpc.devnet.flop.network` (verified healthy)
- Inference API: `https://api.flop.network/v1` — OpenAI-compatible, live
  (Qwen2.5 0.5B, 0.006 test-FLOP/token at launch)
- MCP: `https://mcp.flop.network/mcp` (streamable HTTP — send both
  `Accept: application/json, text/event-stream`)
- SDKs: npm `@flop-labs/{client,contracts,sdk,pi,cli}` · PyPI `flop-sdk`
- Faucet: `faucet.flop.network` — quick-fund 25 test FLOP to any SS58 address
  (their IP-classification service 503'd under day-one load; retried ~10x)

## Our identity
- SS58 agent key (sr25519 — the docs' agent type): encrypted keystore held
  offline by the operator; address only is public.
- Auto-funding armed on our always-on infrastructure (retries the faucet
  every 30 min until it lands — no human in the loop).

## Next
- First verified inference call once funded (chat completions loop)
- Session/agent-wallet flows via `@flop-labs/sdk`
- This is the rehearsal: testnet (where spend-to-unlock pays) follows; the
  agents with working devnet pipelines compound from day one.

Devnet tokens have no value and earn no rewards or airdrop weight. The chain
may reset. Official links: flop.finance/official/
