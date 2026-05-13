---
name: stonfi-dex
description: Expert integration with Ston.fi DEX — Swap, Liquidity, Routing, SDK usage, Jetton Wallet interaction, and fee estimation on TON.
allowed-tools: Read, Write, Edit, Glob, Grep
version: 1.0.0
---

# 💎 Ston.fi DEX Integration (2026)

Expert guidelines for integrating with Ston.fi, the leading decentralized exchange on the TON blockchain.

## 🏗 Core Integration Patterns

Ston.fi uses a request-response pattern for swaps and liquidity provision.

### Basic Swap Pattern (SDK)
```typescript
import { StonApiClient, Router } from '@ston-fi/sdk';

const client = new StonApiClient();
const router = new Router(client, { address: ROUTER_ADDRESS });

// 1. Get a quote
const quote = await client.getSwapQuote({
    askAddress: JETTON_A,
    bidAddress: JETTON_B,
    offerAmount: '1000000',
    slippage: 0.01,
});

// 2. Build swap message
const tx = await router.buildSwapTx({
    userAddress: USER_WALLET,
    offerAmount: quote.offerAmount,
    askAddress: quote.askAddress,
    minAskAmount: quote.minAskAmount,
});
```

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

## Changelog

- **1.0.0** (2026-05-13): Initial version
