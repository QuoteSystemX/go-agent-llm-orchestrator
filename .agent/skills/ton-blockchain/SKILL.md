---
name: ton-blockchain
description: Expert TON (The Open Network) development — ton-core, ton-crypto, Tact/FunC contracts, BOC/Cell handling, Jettons, NFTs, and asynchronous architecture patterns.
allowed-tools: Read, Write, Edit, Glob, Grep
version: 1.0.0
---

# TON Blockchain Skill (2026)

> Mastery of the Open Network: Async-first, Cell-based, high-performance blockchain engineering.

---

## 🧠 Core TON Philosophy

| Concept | Description | Why It Matters |
|---------|-------------|----------------|
| **Asynchronous** | Every contract call is a message that can fail/timeout. | No atomicity across contracts; needs callback/state machine patterns. |
| **Cells (BOC)** | Data is stored in trees of cells (1023 bits + 4 refs). | Efficient storage, but requires precise serialization/deserialization. |
| **Actor Model** | Contracts are isolated actors communicating via messages. | Parallel execution, but requires careful handling of "bounced" messages. |
| **Workchains** | Scalable sharding (Masterchain vs Basechain). | Most apps live on Workchain 0. |

---

## 🌐 API & Infrastructure Reference

### Public API Providers
- **Toncenter**: `https://toncenter.com/api/v2/jsonRPC` (Standard, needs API Key)
- **TonAPI**: `https://tonapi.io` (Rich indexed data, REST/Streaming)
- **GetBlock**: Multi-chain provider with high limits.
- **Testnet**: Swap `toncenter.com` → `testnet.toncenter.com`.

### Explorers
- **Tonviewer**: `https://tonviewer.com` (Best for debugging BOCs)
- **Tonscan**: `https://tonscan.org` (Classic explorer)
- **dTON**: `https://dton.io` (GraphQL for complex queries)

---

## 🛠️ SDK Master (ton-core / ton-crypto)

### BOC Handling (TypeScript)
```typescript
import { BeginCell, Cell, Address } from 'ton-core';

// ✅ Encoding a message
const body = beginCell()
    .storeUint(0, 32) // OpCode
    .storeStringTail("Hello TON")
    .endCell();

// ❌ Never forget to check Cell limits (1023 bits)
```

### Wallet Interaction
```typescript
import { TonClient, WalletContractV4, HighloadWalletV2 } from 'ton';

// ✅ Standard V4R2 (seqno-based)
const wallet = WalletContractV4.create({ publicKey: Buffer.from(...), workchain: 0 });

// ✅ Highload V2 (Concurrent sends)
const highload = HighloadWalletV2.create({ publicKey: Buffer.from(...), workchain: 0 });
```

---

## 🏦 TON Wallet Taxonomy

### 1. Classical Wallets (V3, V4)
The most common wallets used by individuals.
- **V3R1 / V3R2**: Legacy standard. `seqno`-based. Only 1 transaction per `seqno`.
- **V4R2**: Current standard. Adds **Plugins** support. Still `seqno`-based.
- **Mechanics**: You must wait for the current `seqno` to increment on-chain before sending the next transaction. Parallelism is NOT possible from a single V4 wallet without risking "external message rejected".

### 2. Highload Wallet V2
Designed for exchanges and services sending thousands of transactions.
- **No `seqno` bottleneck**: Uses a bitmask/query_id system.
- **Batching**: Allows sending up to **254 messages** in a single external message.
- **Concurrency**: Can send multiple external messages in parallel as long as `query_id` (usually a timestamp) is unique within the expiration window.

### 3. Wallet V5 (W5)
The new 2025-2026 standard.
- **Flexible**: Supports extension modules and flexible permission management.
- **Gas Efficient**: Optimized for modern TVL operations.
- **Internal Signing**: Can be controlled by other contracts more easily.

### 4. Multi-sig Wallets
- **Logic**: Requires N of M signatures to authorize a message.
- **Process**: Signature collection happens off-chain or via a separate orchestrator contract on-chain.

---

## 🚦 Wallet Selection Decision Tree

```
Need to send transactions?
│
├── Personal use / Single user? 
│   └── YES → Wallet V4R2 or V5
│
├── Bulk payments / Airdrops / Exchange?
│   └── YES → Highload Wallet V2 (batching + concurrency)
│
├── Multi-party treasury / Cold storage?
│   └── YES → Multi-sig (Safe)
│
└── Subscription / Recurring payments?
    └── YES → Wallet V4 with Plugins or V5
```

---

## 📜 Smart Contract Standards (Tact/FunC)

### Tact (Preferred for 2026)
```tact
contract SimpleCounter {
    counter: Int as uint32;

    init() {
        self.counter = 0;
    }

    receive("increment") {
        self.counter = self.counter + 1;
    }
}
```

### Standards
- **TEP-62**: NFT Standard
- **TEP-74**: Jetton (Fungible Token) Standard
- **TEP-85**: SBT (Soulbound Token)

---

## 🔒 Security & Pitfalls

| Danger | Fix |
|--------|-----|
| **Asynchronous Race** | Use `nonce` or state locks to prevent double-spending in async callbacks. |
| **Out of Gas** | Always calculate gas limits for complex message chains. |
| **Bounced Messages** | Implement `bounced(src: Slice)` to handle failed contract calls. |
| **Cell Overflow** | Use `storeRef` for large data structures instead of packing one cell. |

---

## 🚀 Execution Protocol
Before deploying or signing:
1. **Simulation**: Run `ton-emulator` or `blueprint test`.
2. **Analysis**: Check BOC size and depth (max 1024).
3. **Audit**: Verify `op` codes match TEP standards.

---

## 🏗️ Data Structures (TL-B Schemes)

### Internal Message Layout
Every message between contracts follows this structure:
```
- Tag (0 or 1)
- IHR Disabled (Bool)
- Bounce (Bool)
- Bounced (Bool)
- Source (Address)
- Destination (Address)
- Value (CurrencyCollection: Grams + ExtraCurrencies)
- IHR Fee (Grams)
- Fwd Fee (Grams)
- CreatedLT (Uint64)
- CreatedAt (Uint32)
- Body (Either Slice or Ref Cell)
```

### Jetton Transfer (TEP-74)
Standard layout for sending tokens:
```typescript
// OpCode: 0xf8a7ea5 (transfer)
const body = beginCell()
    .storeUint(0xf8a7ea5, 32)      // op: transfer
    .storeUint(query_id, 64)       // query_id
    .storeCoins(amount)            // amount in nanoJettons
    .storeAddress(destination)     // new owner
    .storeAddress(response_dest)   // where to send excess gas
    .storeBit(0)                   // custom_payload (null)
    .storeCoins(forward_amount)    // nanoTON to forward to recipient
    .storeBit(1)                   // forward_payload (as Ref)
    .storeRef(payloadCell)         // comment or data
    .endCell();
```

### Common OpCodes
| Operation | Hex Code | Purpose |
|-----------|----------|---------|
| **Transfer** | `0xf8a7ea5` | Send Jettons |
| **Notify** | `0x7362d09c` | Receiver notification |
| **Burn** | `0x595f07bc` | Destroy Jettons |
| **NFT Transfer** | `0x5fcc3d14` | Send NFT |
| **Excesses** | `0xd53276db` | Gas return |

## Changelog

- **1.0.0** (2026-05-13): Initial version
