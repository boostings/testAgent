# Timeouts and heartbeats | Hyperliquid Docs

Copy

  1. [For developers](/hyperliquid-docs/for-developers)
  2. [API](/hyperliquid-docs/for-developers/api)
  3. [Websocket](/hyperliquid-docs/for-developers/api/websocket)

# Timeouts and heartbeats

This page describes the measures to keep WebSocket connections alive.

The server will close any connection if it hasn't sent a message to it in the last 60 seconds. If you are subscribing to a channel that doesn't receive messages every 60 seconds, you can send heartbeat messages to keep your connection alive. The format for these messages are:

Copy
    
    
    { "method": "ping" }

The server will respond with:

Copy
    
    
    { "channel": "pong" }

[PreviousPost requests](/hyperliquid-docs/for-developers/api/websocket/post-requests)[NextError responses](/hyperliquid-docs/for-developers/api/error-responses)

Last updated 5 months ago