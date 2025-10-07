# HyperEVM | Hyperliquid Docs

Copy

  1. [For developers](/hyperliquid-docs/for-developers)

# HyperEVM

The HyperEVM consists of EVM blocks built as part of Hyperliquid's execution, inheriting all security from HyperBFT consensus. HYPE is the native gas token on the HyperEVM. To move HYPE from HyperCore to HyperEVM, send HYPE to `0x2222222222222222222222222222222222222222`. See the instructions in [Native Transfers](/hyperliquid-docs/for-developers/hyperevm/hypercore-less-than-greater-than-hyperevm-transfers) for more details on how this works.

Note that there are currently no official frontend components of the EVM. Users can build their own frontends or port over existing EVM applications. All interaction with the EVM happens through the JSON-RPC. For example, users can add the chain to their wallets by entering the RPC URL and chain ID. There is currently no websocket JSON-RPC support for the RPC at `rpc.hyperliquid.xyz/evm`but other RPC implementations may support it.

The HyperEVM uses the Cancun hardfork without blobs. In particular, EIP-1559 is enabled on the HyperEVM. Base fees are burned as usual, implemented in the standard way where the burned fees are removed from the total EVM supply. Unlike most other EVM chains, priority fees are also burned because the HyperEVM uses HyperBFT consensus. The burned priority fees are sent to the zero address's EVM balance. 

On both mainnet and testnet, HYPE on the HyperEVM has 18 decimals. A few differences between testnet and mainnet HyperEVM are highlighted below:

### 

Mainnet

Chain ID: 999

JSON-RPC endpoint: `https://rpc.hyperliquid.xyz/evm` for mainnet 

### 

Testnet

Chain ID: 998 

JSON-RPC endpoint: `https://rpc.hyperliquid-testnet.xyz/evm`

[PreviousHIP-3 deployer actions](/hyperliquid-docs/for-developers/api/hip-3-deployer-actions)[NextDual-block architecture](/hyperliquid-docs/for-developers/hyperevm/dual-block-architecture)

Last updated 3 months ago