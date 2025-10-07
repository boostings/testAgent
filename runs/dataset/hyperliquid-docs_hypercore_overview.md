# Overview | Hyperliquid Docs

Copy

  1. [HyperCore](/hyperliquid-docs/hypercore)

# Overview

### 

Consensus

Hyperliquid is secured by HyperBFT, a variant of HotStuff consensus. Like most proof of stake chains, blocks are produced by validators in proportion to the native token staked to each validator. 

### 

Execution

The Hyperliquid state is comprised of HyperCore and the general purpose HyperEVM. 

HyperCore include margin and matching engine state. Importantly, HyperCore does not rely on the crutch of off-chain order books. A core design principle is full decentralization with one consistent order of transactions achieved through HyperBFT consensus. 

### 

Latency

Consensus currently uses an optimized consensus algorithm called HyperBFT, which is optimized for end-to-end latency. End-to-end latency is measured as duration between sending request to receiving committed response. 

For an order placed from a geographically co-located client, end-to-end latency has a median 0.2 seconds and 99th percentile 0.9 seconds. This performance allows users to port over automated strategies from other crypto venues with minimal changes and gives retail users instant feedback through the UI.

### 

Throughput

Mainnet currently supports approximately 200k orders/sec. The current bottleneck is execution. The consensus algorithm and networking stack can scale to millions of orders per second once the execution can keep up. There are plans to further optimize the execution logic once the need arises. 

[PreviousHyperCore](/hyperliquid-docs/hypercore)[NextBridge](/hyperliquid-docs/hypercore/bridge)

Last updated 5 months ago