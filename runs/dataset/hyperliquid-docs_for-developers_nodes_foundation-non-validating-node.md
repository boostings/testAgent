# Foundation non-validating node | Hyperliquid Docs

Copy

  1. [For developers](/hyperliquid-docs/for-developers)
  2. [Nodes](/hyperliquid-docs/for-developers/nodes)

# Foundation non-validating node

### 

Overview

The Hyper Foundation runs a non-validating node to provide reliable, low latency data access. As a reminder, running a non-validating node is permissionless. This non-validating node is available for those who would benefit from a reliable peer with fewer hops to validating nodes.

The Foundation non-validating node is made available on a best-efforts basis to support access to publicly available data on the Hyperliquid blockchain. No guarantees are made regarding availability, latency, performance, or data completeness, and the node should not be relied upon as a sole or authoritative source of data for any trading or time-sensitive activity. Users connecting to the Foundation non-validating node are solely responsible for verifying any data received and for operating their own infrastructure if needed. Access may be modified, rate-limited, or discontinued at any time without notice.

The Foundation non-validating node runs in apne1-az1 on AWS.

### 

Potential use cases

Automated traders can run a non-validating node pointing to the Foundation non-validating node. The local non-validating node can record fills and orders with output file buffering disabled for real-time streaming data. A local API server can also be pointed at this local non-validating node to provide real-time API data. For more details see: <https://github.com/hyperliquid-dex/node>[](https://github.com/hyperliquid-dex/node) and [L1 data schemas](/hyperliquid-docs/for-developers/nodes/l1-data-schemas)

### 

Eligibility 

  * You must have staked 10,000 HYPE. 

  * You must be Tier 1 or above in Maker Rebate Tiers, i.e., >0.5% of 14 day weighted maker volume. 

  * Your connecting peer must be a reliable peer in the public p2p network. This will happen automatically as long as the non-validator ports are open to the public. You should have monitoring and alerting on the node. The requirement is 98% time-weighted uptime.

  * You must comply with applicable laws and regulations. 

  * You must not be from a jurisdiction subject to applicable sanctions, which includes, but is not limited to, Cuba, Iran, Myanmar, North Korea, Syria, and certain Russian-occupied regions of Ukraine.

  * You must not be from a jurisdiction subject to applicable restrictions, including certain activities involving the U.S. or Ontario.

  * The Foundation reserves the right to adjust the above eligibility criteria at any time.

  * If you do not meet these criteria at any time, you will no longer be eligible. 

Access may also be granted, at the Foundation’s discretion, to those whose work contributes meaningfully to the Hyperliquid ecosystem and whose use cases require low-latency data access - provided that all other eligibility criteria are met.

### 

Apply 

If you are eligible, you may fill out the [form](https://docs.google.com/forms/d/e/1FAIpQLSeZrUJuJ5_osJuy-YnHCycvb3yTmulhIo6_jPgGPzZVWIxP8g/viewform). You may use linked trading and staking accounts to meet the requirements. 

[PreviousL1 data schemas](/hyperliquid-docs/for-developers/nodes/l1-data-schemas)

Last updated 1 month ago