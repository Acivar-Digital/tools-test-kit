"""Property-based fuzzing tests for RAG/Tokenizer chunking and sanitization utilities.

Targets:
- split_text_into_chunks: Text chunker for Telegram messages (src2/interfaces/telegram/utils.py)
- chunk_text: RAG ingestion chunker (infrastructure/rag/run_rag_pipeline.py)
- sanitize_surrogates: Unicode surrogate/Zalgo sanitizer (src2/interfaces/telegram/utils.py)

Strategy: Hypothesis st.text() generating Zalgo text (combining characters),
massive Unicode blocks (CJK), mixed bidirectional text (Arabic + English),
lone surrogates, and extremely long strings (10k+ characters).

Properties:
1. Max-Token Invariant: No output chunk exceeds the defined max_chars/chunk_size limit.
2. No Crash: No unhandled TypeError, UnicodeEncodeError, or C-level segfault.
3. Valid Unicode: All output chunks are valid str objects encodable as UTF-8
   (ensuring safe JSON serialization for embedding APIs like BGEM3/Qdrant).
"""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from infrastructure.rag.run_rag_pipeline import CHUNK_OVERLAP, CHUNK_SIZE, chunk_text
from src2.interfaces.telegram.utils import sanitize_surrogates, split_text_into_chunks

# Suppress health checks for fuzzing: too_slow (large inputs are expected),
# large_base_example (10k+ char strings are the test goal),
# data_too_large (Hypothesis's own size limit, not our concern).
_FUZZ_SETTINGS = [HealthCheck.too_slow, HealthCheck.large_base_example, HealthCheck.data_too_large]


# ── Adversarial Unicode alphabets ─────────────────────────────────

# U+0300–U+036F: Combining Diacritical Marks (Zalgo text base)
_COMBINING_MARKS = [chr(c) for c in range(0x0300, 0x0370)]

# U+0600–U+06FF: Arabic (for bidirectional text mixing)
_ARABIC_CHARS = [chr(c) for c in range(0x0600, 0x06FF)]

# U+4E00–U+9FFF: CJK Unified Ideographs (massive unicode blocks)
_CJK_CHARS = [chr(c) for c in range(0x4E00, 0xA000)]

# U+D800–U+DFFF: Lone surrogates (can cause UnicodeEncodeError on UTF-8 encode)
_LONE_SURROGATES = [chr(c) for c in range(0xD800, 0xE000)]

# U+1F600–U+1F64F: Emoticons (emoji)
_EMOJI_CHARS = [chr(c) for c in range(0x1F600, 0x1F650)]

# ASCII letters (A-Z, a-z)
_ASCII_LETTERS = [chr(c) for c in range(0x41, 0x5B)] + [chr(c) for c in range(0x61, 0x7B)]

# Common separators (for chunk boundary splitting)
_SEPARATORS = [" ", "\n", "\r", "\t", "。", "、", "，", "．"]

# Full adversarial alphabet combining all categories
_ADVERSARIAL_ALPHABET = (
    _ASCII_LETTERS
    + _COMBINING_MARKS
    + _ARABIC_CHARS
    + _CJK_CHARS
    + _LONE_SURROGATES
    + _EMOJI_CHARS
    + _SEPARATORS
)

# Defined limits for each chunker
TELEGRAM_MAX_CHARS = 4000
RAG_CHUNK_SIZE = CHUNK_SIZE
RAG_CHUNK_OVERLAP = CHUNK_OVERLAP

_TEST_SOURCE = "fuzz_test_source"


# ── Helper: build text from a character list ──────────────────────

def _chars_to_text(chars: list[str]) -> str:
    """Join a list of single-character strings into a single string."""
    return "".join(chars)


# ── Hypothesis strategies ─────────────────────────────────────────

@st.composite
def _adversarial_text(draw, min_size=1, max_size=2000):
    """Generate text with adversarial Unicode: Zalgo, CJK, Arabic bidi, surrogates, emoji."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    chars = draw(st.lists(st.sampled_from(_ADVERSARIAL_ALPHABET), min_size=size, max_size=size))
    return _chars_to_text(chars)


@st.composite
def _zalgo_text(draw):
    """Generate Zalgo text: ASCII base chars with heavy combining mark stacks."""
    num_bases = draw(st.integers(min_value=1, max_value=500))
    parts = []
    for _ in range(num_bases):
        base = draw(st.sampled_from(_ASCII_LETTERS))
        num_marks = draw(st.integers(min_value=1, max_value=15))
        marks = draw(
            st.lists(st.sampled_from(_COMBINING_MARKS), min_size=num_marks, max_size=num_marks)
        )
        parts.append(base + "".join(marks))
    return "".join(parts)


@st.composite
def _mixed_bidi_text(draw, min_size=1, max_size=2000):
    """Generate mixed bidirectional text (Arabic + English)."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    chars = draw(
        st.lists(
            st.sampled_from(_ASCII_LETTERS + _ARABIC_CHARS + _SEPARATORS),
            min_size=size, max_size=size,
        )
    )
    return _chars_to_text(chars)


@st.composite
def _surrogate_text(draw, min_size=1, max_size=2000):
    """Generate text containing lone surrogates mixed with normal text."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    chars = draw(
        st.lists(
            st.sampled_from(_ASCII_LETTERS + _LONE_SURROGATES + _SEPARATORS),
            min_size=size, max_size=size,
        )
    )
    return _chars_to_text(chars)


@st.composite
def _extremely_long_text(draw, min_size=10000, max_size=50000):
    """Generate extremely long strings (10,000+ chars).

    Uses chunked generation with repetition to bypass Hypothesis's
    BUFFER_SIZE limit (8192) on single strategy draws. Each individual
    draw stays within the 8192 limit; the final string exceeds 10k.
    """
    base_len = draw(st.integers(min_value=5000, max_value=8000))
    base = draw(st.text(min_size=base_len, max_size=base_len))
    repeats = draw(st.integers(min_value=2, max_value=10))
    return base * repeats


# Combined strategy covering all adversarial text types.
# Each sub-strategy respects Hypothesis's BUFFER_SIZE (8192) limit.
_any_adversarial_text = st.one_of(
    _adversarial_text(min_size=1, max_size=2000),
    _zalgo_text(),
    _mixed_bidi_text(),
    _surrogate_text(),
    _extremely_long_text(),
)


# ── Tests: sanitize_surrogates ────────────────────────────────────

@given(text=_any_adversarial_text)
@settings(max_examples=200, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_sanitize_surrogates_no_crash(text):
    """sanitize_surrogates must not crash on adversarial Unicode including lone surrogates."""
    result = sanitize_surrogates(text)
    assert isinstance(result, str)


@given(text=_surrogate_text())
@settings(max_examples=100, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_sanitize_surrogates_replaces_lone_surrogates(text):
    """sanitize_surrogates must replace lone surrogates with valid Unicode (U+FFFD)."""
    result = sanitize_surrogates(text)
    # Output must be valid UTF-8 encodable — no UnicodeEncodeError
    result.encode("utf-8")
    # No surrogate code points should remain in the output
    for ch in result:
        assert not (0xD800 <= ord(ch) <= 0xDFFF), (
            f"Lone surrogate {ch!r} survived sanitize_surrogates"
        )


@given(text=_adversarial_text(min_size=1, max_size=2000))
@settings(max_examples=200, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_sanitize_surrogates_valid_utf8(text):
    """sanitize_surrogates output must be valid UTF-8 encodable."""
    result = sanitize_surrogates(text)
    result.encode("utf-8")  # Must not raise UnicodeEncodeError


# ── Tests: split_text_into_chunks ──────────────────────────────────

@given(text=_any_adversarial_text)
@settings(max_examples=200, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_split_text_into_chunks_no_crash(text):
    """split_text_into_chunks must not crash (TypeError, UnicodeEncodeError, segfault) on adversarial Unicode."""
    chunks = split_text_into_chunks(text, max_chars=TELEGRAM_MAX_CHARS)
    assert isinstance(chunks, list)
    for chunk in chunks:
        assert isinstance(chunk, str)


@given(text=_any_adversarial_text)
@settings(max_examples=200, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_split_text_into_chunks_max_token_invariant(text):
    """Max-Token Invariant: no output chunk from split_text_into_chunks exceeds max_chars."""
    chunks = split_text_into_chunks(text, max_chars=TELEGRAM_MAX_CHARS)
    for chunk in chunks:
        assert len(chunk) <= TELEGRAM_MAX_CHARS, (
            f"Chunk of {len(chunk)} chars exceeds max_chars={TELEGRAM_MAX_CHARS}. "
            f"Chunk start: {chunk[:100]!r}"
        )


@given(text=_any_adversarial_text)
@settings(max_examples=200, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_split_text_into_chunks_valid_unicode(text):
    """All chunks from split_text_into_chunks must be valid UTF-8 encodable.

    This ensures chunks can be safely serialized to JSON for embedding APIs (BGEM3/Qdrant).
    Lone surrogates in chunks would cause UnicodeEncodeError during JSON serialization.
    """
    chunks = split_text_into_chunks(text, max_chars=TELEGRAM_MAX_CHARS)
    for chunk in chunks:
        chunk.encode("utf-8")  # Must not raise UnicodeEncodeError


@given(text=_extremely_long_text())
@settings(max_examples=50, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_split_text_into_chunks_long_strings(text):
    """split_text_into_chunks handles 10k+ char strings without crash and respects max_chars."""
    assert len(text) >= 10000
    chunks = split_text_into_chunks(text, max_chars=TELEGRAM_MAX_CHARS)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert len(chunk) <= TELEGRAM_MAX_CHARS


@given(text=_zalgo_text())
@settings(max_examples=100, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_split_text_into_chunks_zalgo(text):
    """split_text_into_chunks handles Zalgo (heavy combining character) text."""
    chunks = split_text_into_chunks(text, max_chars=TELEGRAM_MAX_CHARS)
    for chunk in chunks:
        assert len(chunk) <= TELEGRAM_MAX_CHARS
        chunk.encode("utf-8")


@given(text=_mixed_bidi_text())
@settings(max_examples=100, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_split_text_into_chunks_bidi(text):
    """split_text_into_chunks handles mixed bidirectional text (Arabic+English)."""
    chunks = split_text_into_chunks(text, max_chars=TELEGRAM_MAX_CHARS)
    for chunk in chunks:
        assert len(chunk) <= TELEGRAM_MAX_CHARS


@given(text=_surrogate_text())
@settings(max_examples=100, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_split_text_into_chunks_surrogate_resistance(text):
    """split_text_into_chunks must handle text with lone surrogates without crash."""
    chunks = split_text_into_chunks(text, max_chars=TELEGRAM_MAX_CHARS)
    for chunk in chunks:
        assert len(chunk) <= TELEGRAM_MAX_CHARS


# ── Tests: chunk_text (RAG ingestion) ─────────────────────────────

@given(text=_any_adversarial_text)
@settings(max_examples=200, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_chunk_text_no_crash(text):
    """chunk_text must not crash on adversarial Unicode."""
    chunks = chunk_text(
        text, _TEST_SOURCE, chunk_size=RAG_CHUNK_SIZE, overlap=RAG_CHUNK_OVERLAP
    )
    assert isinstance(chunks, list)
    for c in chunks:
        assert isinstance(c, dict)
        assert "text" in c
        assert isinstance(c["text"], str)
        assert "source" in c
        assert isinstance(c["source"], str)
        assert "chunk_index" in c
        assert isinstance(c["chunk_index"], int)
        assert "id" in c
        assert isinstance(c["id"], int)


@given(text=_any_adversarial_text)
@settings(max_examples=200, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_chunk_text_max_token_invariant(text):
    """Max-Token Invariant: no chunk from chunk_text exceeds chunk_size characters."""
    chunks = chunk_text(
        text, _TEST_SOURCE, chunk_size=RAG_CHUNK_SIZE, overlap=RAG_CHUNK_OVERLAP
    )
    for c in chunks:
        assert len(c["text"]) <= RAG_CHUNK_SIZE, (
            f"Chunk text of {len(c['text'])} chars exceeds chunk_size={RAG_CHUNK_SIZE}"
        )


@given(text=_any_adversarial_text)
@settings(max_examples=200, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_chunk_text_valid_unicode(text):
    """All chunk text from chunk_text must be valid UTF-8 encodable.

    Chunks with lone surrogates would cause UnicodeEncodeError during JSON
    serialization in the embedding ingestion pipeline (embed function).
    """
    chunks = chunk_text(
        text, _TEST_SOURCE, chunk_size=RAG_CHUNK_SIZE, overlap=RAG_CHUNK_OVERLAP
    )
    for c in chunks:
        c["text"].encode("utf-8")  # Must not raise UnicodeEncodeError


@given(text=_extremely_long_text())
@settings(max_examples=50, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_chunk_text_long_strings(text):
    """chunk_text handles 10k+ char strings without crash and respects chunk_size."""
    assert len(text) >= 10000
    chunks = chunk_text(
        text, _TEST_SOURCE, chunk_size=RAG_CHUNK_SIZE, overlap=RAG_CHUNK_OVERLAP
    )
    assert len(chunks) >= 1
    for c in chunks:
        assert len(c["text"]) <= RAG_CHUNK_SIZE


@given(text=_surrogate_text())
@settings(max_examples=100, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_chunk_text_surrogate_resistance(text):
    """chunk_text must handle text with lone surrogates without crash."""
    chunks = chunk_text(
        text, _TEST_SOURCE, chunk_size=RAG_CHUNK_SIZE, overlap=RAG_CHUNK_OVERLAP
    )
    for c in chunks:
        assert len(c["text"]) <= RAG_CHUNK_SIZE


# ── Cross-property: sanitize then chunk ────────────────────────────

@given(text=_any_adversarial_text)
@settings(max_examples=100, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_sanitize_then_split(text):
    """Pipeline: sanitize_surrogates → split_text_into_chunks must not crash and respect max_chars."""
    sanitized = sanitize_surrogates(text)
    chunks = split_text_into_chunks(sanitized, max_chars=TELEGRAM_MAX_CHARS)
    for chunk in chunks:
        assert len(chunk) <= TELEGRAM_MAX_CHARS
        chunk.encode("utf-8")


@given(text=_any_adversarial_text)
@settings(max_examples=100, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_sanitize_then_chunk_text(text):
    """Pipeline: sanitize_surrogates → chunk_text must not crash and respect chunk_size."""
    sanitized = sanitize_surrogates(text)
    chunks = chunk_text(
        sanitized, _TEST_SOURCE, chunk_size=RAG_CHUNK_SIZE, overlap=RAG_CHUNK_OVERLAP
    )
    for c in chunks:
        assert len(c["text"]) <= RAG_CHUNK_SIZE
        c["text"].encode("utf-8")


# ── Edge cases ────────────────────────────────────────────────────

@given(
    max_chars=st.integers(min_value=1, max_value=100),
    text=_adversarial_text(min_size=1, max_size=500),
)
@settings(max_examples=100, deadline=None, suppress_health_check=_FUZZ_SETTINGS)
def test_split_text_into_chunks_variable_max_chars(max_chars, text):
    """split_text_into_chunks must respect max_chars invariant for various limits."""
    chunks = split_text_into_chunks(text, max_chars=max_chars)
    for chunk in chunks:
        assert len(chunk) <= max_chars, (
            f"Chunk of {len(chunk)} chars exceeds max_chars={max_chars}"
        )
        chunk.encode("utf-8")
