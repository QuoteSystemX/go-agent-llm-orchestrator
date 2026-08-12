/**
 * Golden Path: execute a swap on Ston.fi via @ston-fi/sdk + @ston-fi/api.
 *
 * Adapted from the official ston-fi/sdk repo's Next.js example app:
 * https://github.com/ston-fi/sdk/tree/main/examples/next-js-app/app/swap
 * (build-swap-transaction.ts + swap-simulation-query.ts + swap-button.tsx, MIT License)
 * — condensed into a single framework-agnostic script covering the same flow.
 *
 * IMPORTANT — this uses the *current* v2 API. An older pattern using
 * `StonApiClient.getSwapQuote()` / `Router.buildSwapTx()` shows up in some
 * tutorials; per the official docs it's outdated. Always let the STON.fi API
 * pick the router via simulateSwap() rather than hardcoding a router/contract
 * address — that stays compatible with future router upgrades.
 *
 * Requires: @ston-fi/sdk, @ston-fi/api, @tonconnect/sdk (or @tonconnect/ui
 * in a browser app), @ton/ton (for the RPC client).
 */

import { StonApiClient, type SwapSimulation } from "@ston-fi/api";
import { dexFactory, toUnits } from "@ston-fi/sdk";
import { TonClient } from "@ton/ton";
import TonConnect from "@tonconnect/sdk";

const TON_ADDRESS = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c";

const tonClient = new TonClient({
  endpoint: "https://toncenter.com/api/v2/jsonRPC",
});
const stonApi = new StonApiClient();

/** Step 1: simulate the swap to get a quote + which router to use. */
async function simulate(
  offerJettonAddress: string,
  askJettonAddress: string,
  offerAmountHuman: string,
  offerDecimals: number,
  slippageTolerance = "0.01",
): Promise<SwapSimulation> {
  return stonApi.simulateSwap({
    offerAddress: offerJettonAddress,
    askAddress: askJettonAddress,
    offerUnits: toUnits(offerAmountHuman, offerDecimals).toString(),
    slippageTolerance,
  });
}

/**
 * Step 2: build the transaction params for the simulated swap. Branches on
 * TON vs. Jetton on either side of the pair, matching the real swap flow —
 * TON never has its own jetton wallet, so it goes through a pTON proxy.
 */
async function buildSwapTxParams(
  simulation: SwapSimulation,
  userWalletAddress: string,
  useRecommendedSlippage = true,
) {
  const dexContracts = dexFactory(simulation.router);
  const router = tonClient.open(
    dexContracts.Router.create(simulation.router.address),
  );

  const shared = {
    userWalletAddress,
    offerAmount: simulation.offerUnits,
    minAskAmount: useRecommendedSlippage
      ? simulation.recommendedMinAskUnits
      : simulation.minAskUnits,
  };

  if (
    simulation.offerAddress !== TON_ADDRESS &&
    simulation.askAddress !== TON_ADDRESS
  ) {
    // Jetton -> Jetton
    return router.getSwapJettonToJettonTxParams({
      ...shared,
      offerJettonAddress: simulation.offerAddress,
      askJettonAddress: simulation.askAddress,
      gasAmount: simulation.gasParams.gasBudget,
      forwardGasAmount: simulation.gasParams.forwardGas,
    });
  }

  const proxyTon = dexContracts.pTON.create(
    simulation.router.ptonMasterAddress,
  );

  if (simulation.offerAddress === TON_ADDRESS) {
    // TON -> Jetton
    return router.getSwapTonToJettonTxParams({
      ...shared,
      proxyTon,
      askJettonAddress: simulation.askAddress,
      forwardGasAmount: simulation.gasParams.forwardGas,
    });
  }

  // Jetton -> TON
  return router.getSwapJettonToTonTxParams({
    ...shared,
    proxyTon,
    offerJettonAddress: simulation.offerAddress,
    gasAmount: simulation.gasParams.gasBudget,
    forwardGasAmount: simulation.gasParams.forwardGas,
  });
}

/** Step 3: send the built message via TonConnect. */
async function sendSwap(
  connector: TonConnect,
  txParams: Awaited<ReturnType<typeof buildSwapTxParams>>,
) {
  return connector.sendTransaction({
    validUntil: Math.floor(Date.now() / 1000) + 5 * 60, // 5 minute window
    messages: [
      {
        address: txParams.to.toString(),
        amount: txParams.value.toString(),
        payload: txParams.body?.toBoc().toString("base64"),
      },
    ],
  });
}

/** End-to-end example: swap 1 unit of JETTON_A for JETTON_B. */
async function executeSwap(connector: TonConnect, userWalletAddress: string) {
  const JETTON_A = "<offer jetton master address>";
  const JETTON_B = "<ask jetton master address>";
  const JETTON_A_DECIMALS = 9;

  const simulation = await simulate(JETTON_A, JETTON_B, "1", JETTON_A_DECIMALS);
  const txParams = await buildSwapTxParams(simulation, userWalletAddress);
  const result = await sendSwap(connector, txParams);

  console.log("Swap sent:", result);
  return result;
}

export { simulate, buildSwapTxParams, sendSwap, executeSwap };
