# Auto-deleveraging | Hyperliquid Docs

Copy

  1. [Trading](/hyperliquid-docs/trading)

# Auto-deleveraging

Auto-deleveraging strictly ensures that the platform stays solvent. If a user's account value or isolated position value becomes negative, the users on the opposite side of the position are ranked by unrealized pnl and leverage used. The specific sorting index to determine the affected users in profit is `(mark_price / entry_price) * (notional_position / account_value)`. Those traders' positions are closed at the previous mark price against the now underwater user, ensuring that the platform has no bad debt. 

Auto-deleveraging is an important final safeguard on the solvency of the platform. There is a strict invariant that under all operations, a user who has no open positions will not socialize any losses of the platform.

[PreviousMiscellaneous UI](/hyperliquid-docs/trading/miscellaneous-ui)[NextRobust price indices](/hyperliquid-docs/trading/robust-price-indices)

Last updated 1 minute ago