import pytest
from sqlalchemy import select
from app.core.database import async_session_maker
from app.modules.magazine.models import MagazineTemplate, TemplateEmbedding
from app.modules.magazine.template_retriever import (
    retrieve_template_examples,
    seed_template_embeddings,
)


@pytest.mark.asyncio
async def test_seed_and_retrieve_template_embeddings():
    async with async_session_maker() as db:
        tmpl = (await db.execute(select(MagazineTemplate).where(MagazineTemplate.is_active == True))).scalars().first()
        assert tmpl is not None, "Active template must exist"

        # 1. Seed embeddings
        count = await seed_template_embeddings(db, tmpl.id)
        assert count >= 6

        # 2. Verify retrieval on robotics query
        q_robotics = "autonomous walking quadruped machine with low latency motor actuators"
        res_robotics = await retrieve_template_examples(db, tmpl.id, q_robotics, top_k=1)
        assert len(res_robotics) == 1
        assert res_robotics[0]["example_key"] == "robotics_hardware"
        assert res_robotics[0]["similarity_score"] >= 0.60

        # 3. Verify retrieval on hackathon award query
        q_award = "undergraduate student team wins first prize and cash award at national hackathon competition"
        res_award = await retrieve_template_examples(db, tmpl.id, q_award, top_k=1)
        assert len(res_award) == 1
        assert res_award[0]["example_key"] == "hackathon_national_victory"
        assert res_award[0]["similarity_score"] >= 0.60

        # 4. Verify that retrieval returns distinct, context-relevant exemplars
        assert res_robotics[0]["example_key"] != res_award[0]["example_key"]
