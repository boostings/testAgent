# How to use the HyperEVM | Hyperliquid Docs

Copy

  1. [Onboarding](/hyperliquid-docs/onboarding)

# How to use the HyperEVM

## 

For users:

### 

How do I add the HyperEVM to my wallet extension?

You can add the HyperEVM to your wallet extension by using Chainlist (<https://chainlist.org/chain/999>[](https://chainlist.org/chain/999)) or following these steps: [ ](https://chainlist.org/chain/999)

In your wallet extension, click “Add Custom Network” and enter the information below: 

Chain ID: 999 

Network Name: Hyperliquid 

RPC URL:[ https://rpc.hyperliquid.xyz/evm](https://rpc.hyperliquid.xyz/evm)

Block explorer URL (optional): 

  1. <https://hyperevmscan.io/>[](https://hyperevmscan.io/)

  2. <https://purrsec.com/>[](https://purrsec.com/)

  3. <https://www.hyperscan.com/>[](https://www.hyperscan.com/)

Currency Symbol: HYPE

![](https://hyperliquid.gitbook.io/hyperliquid-docs/~gitbook/image?url=https%3A%2F%2F2356094849-files.gitbook.io%2F%7E%2Ffiles%2Fv0%2Fb%2Fgitbook-x-prod.appspot.com%2Fo%2Fspaces%252FyUdp569E6w18GdfqlGvJ%252Fuploads%252Fv6qDC8gb3VDKlyizuuY9%252Fimage.png%3Falt%3Dmedia%26token%3Dd84bee95-9b5c-4dda-b395-6b4464ff78fc&width=768&dpr=4&quality=100&sign=59b381f3&sv=2)

### 

How do I move assets to and from the HyperEVM?

You can send assets to the HyperEVM from your Spot balances on HyperCore and vice versa by clicking the “Transfer to/from EVM” button on the Balances table of the Trade or Portfolio pages or clicking the "EVM <-> Core Transfer" button at the top of the Portfolio page. 

You can also send your HYPE to 0x2222222222222222222222222222222222222222 from either your Spot balances or from the EVM to transfer. Note that this only works for HYPE; sending other assets will lead to them being lost. Each spot asset has a unique transfer address. 

Sending from the HyperEVM to your Spot balances costs gas in HYPE on the HyperEVM. Sending from your Spot balances to the HyperEVM cost gas in HYPE on HyperCore (Spot). 

![](https://hyperliquid.gitbook.io/hyperliquid-docs/~gitbook/image?url=https%3A%2F%2F2356094849-files.gitbook.io%2F%7E%2Ffiles%2Fv0%2Fb%2Fgitbook-x-prod.appspot.com%2Fo%2Fspaces%252FyUdp569E6w18GdfqlGvJ%252Fuploads%252FBYObU8WVK89lpgV9OkO9%252Fimage.png%3Falt%3Dmedia%26token%3D5a752e35-39f8-4dc6-a6ef-2950d8c0ccdf&width=768&dpr=4&quality=100&sign=60d6a2dc&sv=2)

### 

What can I do on the HyperEVM?

Various teams are building applications, tooling, etc. on the HyperEVM. There are many community initiatives to track new releases on the HyperEVM, including:

<https://www.hypurr.co/ecosystem-projects>[](https://www.hypurr.co/ecosystem-projects),[ https://hyperliquid.wiki/](https://hyperliquid.wiki/),[ https://data.asxn.xyz/dashboard/hyperliquid-ecosystem](https://data.asxn.xyz/dashboard/hyperliquid-ecosystem), <https://hl.eco/>[](https://hl.eco/), and the #hyperevm-eco channel in <https://discord.gg/hyperliquid>[](https://discord.gg/hyperliquid)

### 

How does the HyperEVM interact with the rest of the Hyperliquid blockchain? 

Hyperliquid is one state with HyperCore state (e.g., perps, spot, order books, other trading features) and HyperEVM state. Because everything is secured by the same HyperBFT consensus, there will ultimately be seamless integration between the two. You can build an application on the HyperEVM involving lending, trading, yield generation, etc. That application can directly access the liquidity on the order books, so that defi has CEX-like functionality for the first time. The application token can also list on native Hyperliquid trading permissionlessly, so that trading happens on the same chain as building.

### 

Why does gas spike?

While the Hyperliquid native blockchain is one of the most performant, high throughput blockchains today, the HyperEVM was intentionally launched with lower initial throughput. Because HyperCore and the HyperEVM share the same state, it is technically risky to allow the HyperEVM to consume more bandwidth on initial launch. The HyperEVM throughput will be increased over time in a gradual technical rollout.

Gas spikes on any chain when there is more demand than supply of blockspace. The HyperEVM uses the same gas system as Ethereum and many L2s, where there is a base fee and a priority fee: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1559.md

### 

Can I send HYPE on the HyperEVM to a centralized exchange?

First confirm with the CEX that they support the HyperEVM. Note that the HyperEVM is one part of the Hyperliquid blockchain. HyperCore (e.g., perps, spot, and other trading features) and the HyperEVM are separate parts of the same blockchain. Some CEXs support sending and receiving HYPE from Spot balances on HyperCore, but not the HyperEVM. Always remember to do a test transaction when you are trying something for the first time. 

### 

How do I bridge assets to the HyperEVM from another chain? 

There are many different bridges / swaps, including: 

  * LayerZero: <https://www.hyperbridge.xyz/>[](https://www.hyperbridge.xyz/)

  * DeBridge: [https://app.debridge.finance/](https://app.debridge.finance/?inputChain=1&outputChain=999&inputCurrency=&outputCurrency=&dlnMode=simple)

  * Gas.zip: <https://www.gas.zip/>[](https://www.gas.zip/)

  * Jumper: <https://jumper.exchange/>[](https://jumper.exchange/)

  * Cortex for HYPE: <https://cortexprotocol.com/agent?q=buy%20hype>[](https://cortexprotocol.com/agent?q=buy%20hype)

  * Garden for BTC: <https://app.garden.finance/>[](https://app.garden.finance/)

  * Mintify for ETH: <https://mintify.xyz/crypto>[](https://mintify.xyz/crypto)

  * USDT0 for USDT0: <https://usdt0.to/transfer>[](https://usdt0.to/transfer)

  * Stargate for USDe: [https://stargate.finance/bridge?srcChain=ethereum&srcToken=0x4c9EDD5852cd905f086C759E8383e09bff1E68B3&dstChain=hyperliquid&dstToken=0x5d3a1Ff2b6BAb83b63cd9AD0787074081a52ef34](https://stargate.finance/bridge?srcChain=ethereum&srcToken=0x4c9EDD5852cd905f086C759E8383e09bff1E68B3&dstChain=hyperliquid&dstToken=0x5d3a1Ff2b6BAb83b63cd9AD0787074081a52ef34)

## 

For builders: 

### 

What can I build on the HyperEVM?

Any application from other chains can already be built with the limited launch. The HyperEVM is a fully functional EVM of its own. Other features live on testnet will gradually roll out to mainnet.

### 

How do I set up an RPC? What RPCs are available?

There is one rpc hosted at rpc.hyperliquid.xyz/evm

Other builders are launching their own as well. Users may run a node, but it is not a requirement to serve an RPC, as all data is uploaded real-time to S3. See python SDK for an example: https://github.com/hyperliquid-dex/hyperliquid-python-sdk/blob/master/examples/evm_block_indexer.py

### 

How do I get gas on the HyperEVM?

The native token, HYPE, is the gas token on the HyperEVM. You can buy HYPE with USDC on Hyperliquid and then transfer from HyperCore to the HyperEVM. You can also use the bridges mentioned in [How do I bridge assets to the HyperEVM from another chain? ](/hyperliquid-docs/onboarding/how-to-use-the-hyperevm#how-do-i-bridge-assets-to-the-hyperevm-from-another-chain)

### 

What version of the EVM is the HyperEVM based on?

Cancun without blobs

### 

What is the difference between the HyperEVM and other EVMs, like Ethereum?

Functionality is largely the same, which makes it easy to build similar tooling and applications. The main differences are:

  1. Dual block system: fast small blocks and slow big blocks

  2. Interactions with the native side of the Hyperliquid state, providing a seamless onboarding for all Hyperliquid users to the HyperEVM

[PreviousHow to start trading](/hyperliquid-docs/onboarding/how-to-start-trading)[NextHow to stake HYPE](/hyperliquid-docs/onboarding/how-to-stake-hype)

Last updated 24 days ago