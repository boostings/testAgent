# Interaction timings | Hyperliquid Docs

Copy

  1. [For developers](/hyperliquid-docs/for-developers)
  2. [HyperEVM](/hyperliquid-docs/for-developers/hyperevm)

# Interaction timings

## 

Transfer Timing

Transfers from HyperCore to HyperEVM are queued on the L1 until the next HyperEVM block. Transfers from HyperEVM to HyperCore happen in the same L1 block as the HyperEVM block, immediately after the HyperEVM block is built.

## 

Timing within a HyperEVM block

On an L1 block that produces a HyperEVM block:

  1. L1 block is built

  2. EVM block is built

  3. EVM -> Core transfers are processed 

  4. CoreWriter actions are processed 

[PreviousHyperCore <> HyperEVM transfers](/hyperliquid-docs/for-developers/hyperevm/hypercore-less-than-greater-than-hyperevm-transfers)[NextWrapped HYPE](/hyperliquid-docs/for-developers/hyperevm/wrapped-hype)

Last updated 1 month ago