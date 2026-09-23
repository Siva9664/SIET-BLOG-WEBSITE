import pytest
from app.modules.documents.embeddings import embed_text, embed_texts, DEFAULT_EMBEDDING_DIM
from app.modules.documents.retriever import _cosine_similarity


@pytest.mark.asyncio
async def test_embed_text_dimension_and_normalization():
    vec = await embed_text("Autonomous robotics research at SIET AI Lab")
    assert len(vec) == DEFAULT_EMBEDDING_DIM
    # L2 magnitude should be approximately 1.0 (unit normalized)
    mag = sum(v * v for v in vec) ** 0.5
    assert 0.99 <= mag <= 1.01


@pytest.mark.asyncio
async def test_embed_texts_batch():
    texts = [
        "Quantum edge computing and neural networks",
        "Autonomous quadruped robot project",
        "SIET annual technical symposium",
    ]
    vecs = await embed_texts(texts)
    assert len(vecs) == 3
    for v in vecs:
        assert len(v) == DEFAULT_EMBEDDING_DIM


@pytest.mark.asyncio
async def test_semantic_paraphrase_vs_keyword():
    target_passage = (
        "Team QuadRobo (1st Place Winner, ₹75,000 award): Autonomous quadruped legged robot "
        "using real-time spatial vision and low-latency motor microcontrollers."
    )
    keyword_query = "autonomous quadruped legged robot microcontrollers"
    paraphrase_query = "four-legged walking robotic device with low-delay motor controllers"

    target_vec = await embed_text(target_passage)
    keyword_vec = await embed_text(keyword_query)
    paraphrase_vec = await embed_text(paraphrase_query)

    kw_score = _cosine_similarity(keyword_vec, target_vec)
    para_score = _cosine_similarity(paraphrase_vec, target_vec)

    print(f"Keyword score: {kw_score:.4f}, Paraphrase score: {para_score:.4f}")
    assert kw_score >= 0.60
    assert para_score >= 0.60
    # Paraphrase should be comparable to keyword match (within 0.10)
    assert abs(kw_score - para_score) < 0.10
