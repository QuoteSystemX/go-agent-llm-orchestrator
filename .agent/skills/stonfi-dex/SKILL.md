---
name: stonfi-dex
description: Expert integration with Ston.fi DEX — Swap, Liquidity, Routing, SDK usage, Jetton Wallet interaction, and fee estimation on TON.
allowed-tools: Read, Write, Edit, Glob, Grep
version: 1.0.0
files: examples/swap-execution.ts, scripts/query_stonfi_rates.py
---

# 💎 Ston.fi DEX Integration (2026)

Expert guidelines for integrating with Ston.fi, the leading decentralized exchange on the TON blockchain.

## 🏗 Core Integration Patterns

Ston.fi uses a request-response pattern for swaps and liquidity provision.

### Basic Swap Pattern (SDK)

**Always let the STON.fi API pick the router via `simulateSwap()` rather than hardcoding a router
address** — that stays compatible with future router upgrades. (An older pattern using
`StonApiClient.getSwapQuote()` / `Router.buildSwapTx()` shows up in some tutorials — it's
outdated; the API replaced those with `simulateSwap()` + `getSwap*TxParams()`.)

```typescript
import { StonApiClient } from '@ston-fi/api';
import { dexFactory } from '@ston-fi/sdk';

const stonApi = new StonApiClient();

// 1. Simulate to get a quote + which router to use
const simulation = await stonApi.simulateSwap({
    offerAddress: JETTON_A,
    askAddress: JETTON_B,
    offerUnits: '1000000',
    slippageTolerance: '0.01',
});

// 2. Build swap tx params via the router the simulation picked
const dexContracts = dexFactory(simulation.router);
const router = tonClient.open(dexContracts.Router.create(simulation.router.address));
const txParams = await router.getSwapJettonToJettonTxParams({
    userWalletAddress: USER_WALLET,
    offerJettonAddress: simulation.offerAddress,
    askJettonAddress: simulation.askAddress,
    offerAmount: simulation.offerUnits,
    minAskAmount: simulation.minAskUnits,
});
```

Full flow including the TON-to-jetton / jetton-to-TON branches and sending via TonConnect:
see `examples/swap-execution.ts`.

## 🚀 Swap Execution Logic

To execute a swap on Ston.fi:
1. **Fetch Rates**: Query the API or use the SDK to get the current expected output and price impact.
2. **Jetton Wallets**: Find the **User's Jetton Wallet** address for that specific Jetton by calling `get_wallet_address` on the Jetton Master.
3. **Prepare Transaction**: Build a Jetton transfer with a custom payload containing the swap parameters.
4. **Gas Constants**: Swap (~0.15 - 0.25 TON), Jetton Transfer (~0.05 TON).

## 🛠 Tools & Verification

### 1. Pool Data Query
Use the internal script to fetch live data for any Ston.fi pool:

```bash
python3 .agent/skills/stonfi-dex/scripts/query_stonfi_rates.py <POOL_ADDRESS>
```

### 2. Implementation Reference
Refer to `examples/swap-execution.ts` for a "Golden Path" implementation using the `@ston-fi/sdk`.

## 📈 Integration Checklist
- [ ] Is the Router address correct for the target network (Mainnet/Testnet)?
- [ ] Have you calculated slippage and set `min_out` accordingly?
- [ ] Is the Jetton transfer payload properly formatted?
- [ ] Are you handling the router's "Excesses" and "Success" notifications?
- [ ] Is there a timeout/retry strategy for network congestion?

---
> **Note**: This skill ensures that Paperclip's DeFi integrations on TON are efficient and secure.

## When to Use

- **Building a TON DEX** — use the official TON libraries
  (ton-core, ton-crypto) and follow STON.fi reference patterns.
- **Smart contract integration** — use Tact or FunC for new
  contracts, audit before deploy.
- **AMM logic** — constant-product (Uniswap V2) or concentrated
  liquidity (Uniswap V3) — match to the project's liquidity model.
- **Price oracles** — use multiple sources (TON, Chainlink,
  RedStone) to avoid manipulation.
- **MEV protection** — use commit-reveal or private mempools
  for high-value swaps.

Avoid using this skill for:
- Non-TON chains (use chain-specific skills).
- CeFi (use `@backend-specialist` for backend integration).
- Token design (use `@crypto-go-architect`).

## Anti-Patterns

- **Don't use a single price oracle** — always combine
  multiple sources. Single oracle = single point of failure.
- **Don't skip smart contract audits** — even small AMM changes
  need a third-party audit before mainnet.
- **Don't store private keys in the frontend** — use a backend
  signer or wallet abstraction.
- **Don't allow unlimited slippage** — cap it at a sensible
  default (0.5% for liquid pairs, 2% for illiquid).
- **Don't ignore the reentrancy guard** — use Checks-Effects-
  Interactions pattern.
- **Don't launch without emergency pause** — every contract
  needs a kill switch.

## Changelog

- **1.0.0** (2026-05-13): Initial version
