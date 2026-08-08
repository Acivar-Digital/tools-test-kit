"""Test Qdrant direct search with local path storage.

NOTE: These are smoke tests against a local on-disk Qdrant instance.
"""

import os

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models

DB_PATH = os.path.join("_prd", "memories", "qdrant")
COLLECTION = "user_memory"


@pytest.fixture(scope="module")
def client():
    """Return a QdrantClient connected to the local on-disk store."""
    c = QdrantClient(path=DB_PATH)
    collections = [col.name for col in c.get_collections().collections]
    if COLLECTION not in collections:
        c.create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(
                size=1024, distance=models.Distance.COSINE
            ),
        )
    return c


def test_collection_exists(client):
    """The user_memory collection should exist after fixture setup."""
    collections = [col.name for col in client.get_collections().collections]
    assert COLLECTION in collections


def test_search_with_dummy_vector(client):
    """Searching with a zero-vector should not raise (even if empty results)."""
    hits = client.query_points(
        collection_name=COLLECTION,
        query=[0.0] * 1024,
        limit=1,
    )
    assert hits is not None
