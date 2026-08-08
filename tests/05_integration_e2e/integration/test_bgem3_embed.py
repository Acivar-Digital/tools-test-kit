import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

BGEM3_URL = os.getenv("BGEM3_URL", "http://localhost:8002/v1/embeddings")
BGEM3_TOKEN = os.getenv("BGEM3_TOKEN", "")

def test_embed():
    print(f"Connecting to: {BGEM3_URL}")
    try:
        is_openai = "v1/embeddings" in BGEM3_URL
        payload = {"input": "test query"} if is_openai else ["test query"]
        headers = {"Authorization": f"Bearer {BGEM3_TOKEN}"} if BGEM3_TOKEN else {}
        response = requests.post(
            BGEM3_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        print(f"Response Type: {type(data)}")
        if isinstance(data, dict):
            print(f"Keys: {list(data.keys())}")
            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                emb = data["data"][0]["embedding"]
                print(f"Embeddings length: {len(data['data'])}")
                print(f"First embedding length: {len(emb)}")
            elif "embeddings" in data:
                print(f"Embeddings length: {len(data['embeddings'])}")
                print(f"First embedding length: {len(data['embeddings'][0])}")
        elif isinstance(data, list):
            print(f"List length: {len(data)}")
            print(f"First element length: {len(data[0])}")
        else:
            print(f"Raw data: {data}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_embed()
