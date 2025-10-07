# HIP-3: Builder-deployed perpetuals | Hyperliquid Docs

Copy

  1. [Hyperliquid Improvement Proposals (HIPs)](/hyperliquid-docs/hyperliquid-improvement-proposals-hips)

# HIP-3: Builder-deployed perpetuals

Advanced feature: Testnet-only

The Hyperliquid protocol will support builder-deployed perps (HIP-3), a key milestone toward fully decentralizing the perp listing process. An MVP of this feature is live on testnet. Feedback is appreciated during this testing phase. Note that numbers and specifications below are not finalized. Builder-deployed perps share many features with HyperCore spot deployments:

  1. Deployments allocate new performant onchain orderbooks on HyperCore.

  2. Deployment gas in HYPE is paid through a Dutch auction every 31 hours. There is a single Dutch auction across all HIP-3 perp DEXs.

  3. Deployers can set a fee share of up to 50%. A difference is that the deployer can configure additional fees on top of the base fee rate. Fee share applies to the total configured fee. The fee share configuration transaction for deployers will be documented once live on testnet.

  4. Deployments are fully permissionless.

The deployer of a perp market is also responsible for

  1. Market definition, including the oracle definition and contract specifications

  2. Market operation, including setting oracle prices, leverage limits, and settling the market if needed

Perp deployment composes with HyperCore multisig to support protocolized market deployment and operation. 

To ensure high quality markets and protect users, deployers must maintain 1M staked HYPE. In the event of malicious market operation, validators have the authority to slash the deployer’s stake by conducting a stake-weighted vote during the deployer’s 7-day unstaking queue. 

## 

Settlement

The deployer may settle an asset using the `haltTrading` action. This cancels all orders and settles positions to the current mark price. The same action can be used to resume trading, effectively recycling the asset. This could be used to list dated contracts without participating in the deployment auction for each new contract.

Once all assets are settled, a deployer's required stake is free to be unstaked.

## 

Oracle

While the oracle is completely general at the protocol level, perps make the most mathematical sense when there is a well-defined underlying asset or data feed which is difficult to manipulate and has underlying economic significance. Most price indices are not amenable as perp oracle sources. Deployers should consider edge cases carefully before listing markets, as they are subject to slashing for all listed markets on their DEX.

## 

Open interest caps

Builder-deployed perp markets are subject to two types of open interest caps: notional (sum of absolute position size times mark price) and size (sum of absolute position sizes). 

Notional open interest caps are enforced on the total open interest summed over all assets within the DEX, as well as per-asset. Perp deployers can set a custom open interest cap per asset, which is documented in <https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/hip-3-deployer-actions>[](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/hip-3-deployer-actions).

Size-denominated open interest caps are only enforced per-asset. Size-denominated open interest caps are currently a constant 1B per asset, so a reasonable default would be to set `szDecimals` such that the minimal size increment is $1-10 at the initial mark price.

[PreviousHIP-2: Hyperliquidity](/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-2-hyperliquidity)[NextFrontend checks](/hyperliquid-docs/hyperliquid-improvement-proposals-hips/frontend-checks)

Last updated 6 days ago