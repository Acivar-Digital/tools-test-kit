import asyncio

from dotenv import load_dotenv

from src.engine.rag_client import query_classical_text_async


async def test_rag():
    load_dotenv()
    print("Testing RAG for 'love'...")
    res = await query_classical_text_async("love relationship partner spouse")
    print(f"Result for 'love':\n{res}\n")

    print("Testing RAG for '7 Killings'...")
    res2 = await query_classical_text_async("7 killings qi sha")
    print(f"Result for '7 Killings':\n{res2}\n")

if __name__ == "__main__":
    asyncio.run(test_rag())
