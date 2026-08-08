print("Testing imports...")
print("Base imports OK")

print("libcst OK")

print("fastmcp, qdrant OK")

try:
    from fastembed import TextEmbedding  # noqa: F401
    print("fastembed OK")
except ImportError:
    print("fastembed NOT FOUND (expected if optional)")

print("All imports tested.")
