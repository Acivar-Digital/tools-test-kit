import asyncio

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# =====================================================================
# 1. PROVIDER SETUP
# =====================================================================
# Local Mesh Provider (Gemma / Gemini)
google_studio_provider = OpenAIProvider(
    base_url="http://10.32.34.243:18000/v1/openai",
    api_key="YOUR-API-KEY-HERE"
)

# Local LiteRouter Provider (Owl / DeepSeek)
openrouter_provider = OpenAIProvider(
    base_url="http://localhost:7766/v1",
    api_key="YOUR-API-KEY-HERE"
)

# =====================================================================
# 2. DEFINING AVAILABLE MODELS (Model A & Model B)
# =====================================================================
model_a = OpenAIChatModel("gemma-4-31b-it", provider=google_studio_provider)
model_b = OpenAIChatModel("openrouter/openrouter/owl-alpha", provider=openrouter_provider)

# =====================================================================
# 3. DYNAMIC CONTROL SHEET (Your configuration registry)
# =====================================================================
control_sheet = {
    "base_model": model_a,  # Injecting Model A object
    "rag_model": model_b    # Injecting Model B object
}

# =====================================================================
# 4. AGENTS INITIALIZATION (Instantiated without models)
# =====================================================================
# Leaving the model blank allows runtime determination
base_agent = Agent(instructions="You are the core baseline coordinator. Respond in under 15 words.")
rag_agent = Agent(instructions="You extract factual chunks. Respond in under 15 words.")

# =====================================================================
# 5. EXECUTION PIPELINE
# =====================================================================
async def main():
    print("🚀 Running Base Agent using gemma-4-31b-it...")
    # Execute the Base Agent using the 'base_model' configuration choice
    base_result = await base_agent.run(
        "Hello! Confirm you are online.",
        model=control_sheet["base_model"] # << Swapped right here at execution time
    )
    print("Base Agent Response:", base_result.output)

    print("\n🚀 Running RAG Agent using openrouter/owl-alpha...")
    # Execute the RAG Agent using the 'rag_model' configuration choice
    rag_result = await rag_agent.run(
        "Hello! Confirm you are online.",
        model=control_sheet["rag_model"] # << Swapped right here at execution time
    )
    print("RAG Agent Response:", rag_result.output)

if __name__ == "__main__":
    asyncio.run(main())
