---
name: stonfi-dex
description: Expert integration with Ston.fi DEX — Swap, Liquidity, Routing, SDK usage, Jetton Wallet interaction, and fee estimation on TON.
allowed-tools: Read, Write, Edit, Glob, Grep
version: 1.0.0
---

# Ston.fi DEX Skill (2026)

> Mastering the primary liquidity hub on TON.

---

## 🏗️ SDK Integration (Ston.fi SDK)

### Basic Swap Pattern
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

---

## 💧 Liquidity Provision

| Action | Pattern |
|--------|---------|
| **Add Liquidity** | Provide both Jettons to the Pool contract via Router. |
| **Remove Liquidity** | Burn LP tokens to receive underlying Jettons. |
| **Claim Fees** | Fees are usually auto-compounded in V2. |

---

## 🚦 Operational Rules

### 1. Jetton Wallets
In TON, you don't interact with the Token contract directly for transfers. You must find the **User's Jetton Wallet** address for that specific Jetton.
- **Action**: `get_wallet_address` call on the Jetton Master.

### 2. Slippage Management
Ston.fi V2 uses aggressive routing. Always calculate `minAskAmount` based on `slippage` to prevent front-running.

### 3. Gas Constants
TON gas is non-deterministic but follows predictable ranges:
- **Swap**: ~0.15 - 0.25 TON
- **Jetton Transfer**: ~0.05 TON

---

## 📊 Monitoring & Analytics

Use Ston.fi API for:
- **Pool Volume**: Check 24h volume before recommending a route.
- **TVL**: High TVL = lower price impact.
- **Pairs**: Verify if a direct pair exists or if multi-hop routing is needed.

---

## 🛠 Automation Tools

| Tool | Action |
| :--- | :--- |
| `stonfi_analyzer.py` | Fetches pool health and price impact for a given pair. |
| `boc_inspector.py` | Decodes swap messages to verify `minAskAmount` before signing. |

---

> **Rule:** Always verify the Router address. Phishing routers are common in DeFi.
