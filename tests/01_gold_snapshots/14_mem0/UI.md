# Mem0 Latency Baseline Report

## The Bottleneck Identified
Based on our isolated test run, we have empirically identified exactly why the `/ask` pipeline stalls:

- **`search()` (Vector Retrieval):** ~26 ms 
- **`add_memory()` (LLM Extraction):** ~5,644 ms (**~5.6 seconds**)

## Why is `add_memory` so slow?
The `mem0` library's `add()` function does not just insert text into a database. When called, it:
1. Reaches out to the LLM (`POST http://10.32.34.243:8045/v1/chat/completions`) to intelligently extract facts, entities, and relationships from the provided text.
2. Calls the embedding model (`POST http://localhost:8002/v1/embeddings`) multiple times for the newly extracted facts.
3. Loads/runs the local `spaCy` NLP models.
4. Performs multiple index creations and document inserts into Qdrant (`user_memory` and `user_memory_entities` collections).

This blocking ~5.6s synchronous operation halts the entire Telegram response cycle.

## Recommendations for Optimization
1. **Background Tasks (Celery/Async):** Do not block the user's `/ask` reply on `add_memory`. Fire the reply to Telegram first using just `search()` for context, and queue the `add_memory` ingestion in the background via Celery or `asyncio.create_task`.
2. **Batching:** Instead of adding memory on every single message turn, collect the conversation and batch ingest it at the end of the session.
