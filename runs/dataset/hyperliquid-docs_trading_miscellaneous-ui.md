# Miscellaneous UI | Hyperliquid Docs

Copy

  1. [Trading](/hyperliquid-docs/trading)

# Miscellaneous UI

### 

Max Drawdown

The max drawdown on the portfolio page is only used on the frontend for users' convenience. It does not affect any margining or computations on Hyperliquid. Users who care about the precise formula can get their account value and pnl history and compute it however they choose.

The formula used on the frontend is the maximum over times `end > start` of the value `(pnl(end) - pnl(start)) / account_value(start)`

Note that the denominator is account value and the numerator is pnl. Also note that this not equal to absolute max drawdown divided by some account value. Each possible time range considered uses its own denominator. 

[PreviousFunding](/hyperliquid-docs/trading/funding)[NextAuto-deleveraging](/hyperliquid-docs/trading/auto-deleveraging)

Last updated 5 months ago