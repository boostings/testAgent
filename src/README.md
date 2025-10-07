## Hyperliquid Docs Scraper + Local RAG Chat
This is a RAG-trained model that users can use in correlation with an MCP server 




This repo lets you:

- Scrape GitBook `.md` pages listed in `links.txt`
- Convert them into clean Markdown files
- Produce a chunked `JSONL` dataset for RAG/training
- Run a simple local RAG retriever and a small HF instruct model for chat

### 1) Install deps (macOS / Linux)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

If you have an NVIDIA GPU (e.g., 2070 Super), install a matching PyTorch CUDA build from `https://pytorch.org`. Example:

```bash
pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
```

### 2) Scrape and prepare dataset

```bash
python scrape_and_prepare.py \
  --links ./links.txt \
  --out ./runs/hf_hello_rte_hard \
  --max-chars 2000 \
  --overlap 200 \
  --rps 2
```

Outputs:

- `runs/hf_hello_rte_hard/raw_markdown/*.md`
- `runs/hf_hello_rte_hard/docs_index.jsonl`
- `runs/hf_hello_rte_hard/chunks.jsonl`

### 3) Quick retrieval test

```bash
python rag_query.py --dataset runs/hf_hello_rte_hard/chunks.jsonl --query "What is the exchange endpoint?"
```

### 4) RAG chat locally

```bash
python rag_chat.py \
  --dataset runs/hf_hello_rte_hard/chunks.jsonl \
  --embedder sentence-transformers/all-MiniLM-L6-v2 \
  --model Qwen/Qwen2.5-3B-Instruct 
```

Type questions; it will retrieve top chunks and answer using the model.

### Model recommendation for 2070 Super

- For embeddings: `sentence-transformers/all-MiniLM-L6-v2` (fast, accurate enough for RAG)
- For chat/inference on 8 GB VRAM: `Qwen/Qwen2.5-3B-Instruct` is a great balance of quality/speed. You can also try `microsoft/phi-3-mini-4k-instruct`.

To pre-download:

```bash
python - <<'PY'
from transformers import AutoTokenizer, AutoModelForCausalLM
from sentence_transformers import SentenceTransformer

SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
tok = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-3B-Instruct')
mdl = AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-3B-Instruct')
print('Downloaded models.')
PY
```

### 5) Build corpus and train a small LoRA (optional)

Create a plain-text corpus from the chunked dataset:

```bash
python build_corpus.py --dataset runs/hf_hello_rte_hard/chunks.jsonl --out runs/hf_hello_rte_hard/corpus.txt
```

Run QLoRA continued pretraining on a 3B model (fits 8 GB VRAM):

```bash
python train_qlora_cpt.py \
  --model Qwen/Qwen2.5-3B-Instruct \
  --corpus runs/hf_hello_rte_hard/corpus.txt \
  --out runs/hf_hello_rte_hard/lora-qlora-cpt \
  --epochs 2 --bsz 1 --grad-accum 16 --max-seq-len 2048
```

Chat with the adapter applied:

```bash
python rag_chat.py \
  --dataset runs/hf_hello_rte_hard/chunks.jsonl \
  --embedder sentence-transformers/all-MiniLM-L6-v2 \
  --model Qwen/Qwen2.5-3B-Instruct \
  --lora runs/hf_hello_rte_hard/lora-qlora-cpt
```


### 6) Hyperliquid MCP server (query market/account data)

Implements selected Info API endpoints as MCP tools, which you can connect to your model client.

Install deps (if not already):

```bash
pip install -r requirements.txt
```

Run the server (stdio):

```bash
python mcp_hyperliquid.py
```

Example MCP tool invocations (pseudo):

```json
{"tool": "get_metaAndAssetCtxs", "args": {"network": "mainnet"}}
{"tool": "get_clearinghouse_state", "args": {"user": "0x...", "network": "mainnet"}}
{"tool": "get_funding_history", "args": {"coin": "ETH", "startTime": 1700000000000}}
```

Environment variables:

- `HYPERLIQUID_MAINNET_INFO` (override mainnet info URL)
- `HYPERLIQUID_TESTNET_INFO` (override testnet info URL)
- `HYPERLIQUID_HTTP_TIMEOUT` (seconds, default 20)

Client config example (Cursor/Anthropic MCP):

```json
{
  "mcpServers": {
    "hyperliquid-info": {
      "command": "python",
      "args": ["/srv/shared/Models/hyperLiquidAgent/test/mcp_hyperliquid.py"],
      "env": {
        "HYPERLIQUID_HTTP_TIMEOUT": "20"
      }
    }
  }
}
```

### 7) Full market picture tool and signals

Call once to fetch Info + WebSocket data, analytics, and signal:

```json
{"tool": "get_full_market_picture", "args": {"coin": "BTC", "network": "mainnet", "depth": 50, "trades": 30}}
```

Response shape (abridged):

```json
{
  "coin": "BTC",
  "marketSnapshot": {"mid": 64250.1, "spreadBps": 0.6, "funding": "0.0000125", "OI": "1882.55", "vol24h": "1426126.29"},
  "analytics": {"imbalance": 0.18, "vwap": 64240.8, "vwapDrift": -0.00015, "tradeImbalance": 0.22},
  "signal": {"label": "buy", "score": 0.23, "confidence": 0.23, "reasons": ["orderbook imbalance 0.18", "vwap drift -0.02%", "funding 0.0000125"]},
  "rawSlices": {"orderbookTopN": {"bids": [[...]], "asks": [[...]]}, "recentTradesM": [...]},
  "meta": {"network": "mainnet", "sources": ["Info", "WS"], "flags": []}
}
```

Also supported:

- `get_orderbook(coin, depth)`
- `get_recent_trades(coin, maxMessages)`
- `get_predicted_fundings()`
- `get_perps_at_open_interest_cap()`
- `get_perp_deploy_auction_status()`
- `get_active_asset_data(user, coin)`
- `get_perp_dex_limits(dex)`

### Notes

- If GitBook structure changes, the scraper falls back to `<body>` extraction.
- Adjust `--max-chars` and `--overlap` to trade off recall vs. speed.
- For fine-tuning, the produced JSONL can be adapted to SFT format by wrapping `text` into prompts/responses.


