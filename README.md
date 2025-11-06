Very, very, early and rushed version of a Hyperliquid-knowledgable model by using a combination of RAG and custom MCP tools with the Hyperliquid API. There's a lot of things that I plan on doing here, such as.

- Swapping the miniature Qwen model to GPT OSS-20b or another larger model with a better base-all-around knowledge. 
- Properly configuring the MCP toolkit to be called at the correct times, not just calling a tool based on the prompt.
- Getting more training data, such as Discord chats, tweets, and trading guides. dddddddsdadd

Not quality work at all, but mainly using this for a school project that will eventually be integrated into my product. 


1.) Activate .venv (source .venv/bin/activate) \n
2.) Download requirements.txt (can run -r) \n
3.) Run the RAG_chat \n

~ python rag_chat.py \
  --dataset /hyperLiquidAgent/test/runs/current/chunks.cleaned.jsonl \
  --embedder sentence-transformers/all-MiniLM-L6-v2 \
  --model Qwen/Qwen2.5-1.5B-Instruct 

  4.) Run the server.py (frontend interface + MCP tools)
  5.) A frontend interface will be open at http://0.0.0.0:7860/ to interact with! 

  ~~

  Once again, very-very early prototype, and eventually this will be implemented into a perpetual DEX frontend that will actively give users an edge in trading, answer questions with valuable and meaningful answers, and give genuine insight into the market. 

  A few prompts I want to be able to consistently ask about X coin, and the desired result.

  User: What is the best way to buy $400,000 worth of Ethereum on the spot market? I want you to analyze the past 3 days, and give me the most optimal time to buy Ethereum, and the best execution strategy to best enter the position. 
  Model: After looking over the past few days of Ethereum data, the best time to execute the trade would be x time UTC. The best method of execution would likely be a TWAP order, as you'll get the best average price without driving the market up. 

  User: Ethereum is preforming really strongly right now. What are some good betas to Ethereum that are likely to see a rise in value correlated with the price of Ethereum moving up? 
  Model: The strongest performing ETH betas are currently $AVAX, $ARB, and $BNB. These betas haven't seen adjacent price action to Ethereum, and it's probable that as Ethereum continues to increase these coins will as well. 

  User: This user has been taking a lot of interesting trades, could you analyze this wallet and tell me all of the key insight and patterns you can find with this wallet? 0x.......
  Model: This user was identified as Amber Capital according to MLM's telegram. They are known for running delta-neutral funds, so although it may look like they're making a lot of money, it's all neutral positions farming funding.

  ~~
