"""Retrieval Benchmark: Paraphrase Recall@5 and MRR Evaluation.

Evaluates baseline vs hybrid BGE-base-en-v1.5 + BM25 + Reranker on 40 labelled paraphrase queries.
"""

import pytest
from app.modules.documents.embeddings import embed_text
from app.modules.documents.retriever import _cosine_similarity, _compute_keyword_score

PARAPHRASE_BENCHMARK_SET = [
    ("four-legged walking robotic device with low-delay motor controllers", "Autonomous quadruped legged robot using real-time spatial vision and low-latency motor microcontrollers."),
    ("undergraduate student team wins top prize at national hackathon", "Team QuadRobo (1st Place Winner, ₹75,000 award) at national championship."),
    ("edge encryption protocol for IoT sensor networks", "Faculty and student researchers demonstrated edge encryption and secure mesh protocols."),
    ("indoor navigation without GPS signal", "Achieved 99.4% waypoint navigation accuracy in indoor GPS-denied environments."),
    ("visual inertial odometry quadcopter drone", "Robotics Lab demonstrated a quadcopter prototype with visual-inertial odometry."),
    ("microcontroller motor actuators for legged robots", "low-latency motor microcontrollers for quadruped robots."),
    ("national robotics prize winners and cash purse", "1st Place Winner, ₹75,000 award at national robotics championship."),
    ("smart mesh network security for embedded devices", "intrusion detection systems and secure mesh protocols for smart infrastructure."),
    ("obstacle avoidance quadcopter aerial vehicle", "quadcopter prototype with visual-inertial odometry and real-time obstacle avoidance."),
    ("indoor positioning accuracy without satellite signals", "99.4% waypoint navigation accuracy in indoor GPS-denied environments."),
    ("spatial vision system for walking robot", "Autonomous quadruped legged robot using real-time spatial vision."),
    ("smart telemetry units for environmental monitoring", "Sensors and smart telemetry units designed by students."),
    ("reinforcement learning for quadcopter swarm formation", "Reinforcement learning for quadcopter formation flying."),
    ("multi-agent drone formation control research", "Autonomous AI Drone Navigation and Multi-Agent Swarm Intelligence."),
    ("edge intrusion detection for smart cities", "edge encryption, intrusion detection systems, and secure mesh protocols."),
    ("annual student innovation showcase and tech symposium", "Robotics & AI Lab Annual Symposium."),
    ("real-time visual odometry for autonomous flight", "visual-inertial odometry and real-time obstacle avoidance."),
    ("undergraduate award winners in robotics lab", "Lead researcher Ananya Rao received the Best Innovation Award."),
    ("first place cash reward for quadruped prototype", "₹75,000 award for 1st Place Winner in autonomous quadruped robot."),
    ("embedded sensor node communications protocol", "secure mesh protocols for smart infrastructure."),
    ("indoor navigation precision metrics", "achieved a 99.4% waypoint navigation accuracy."),
    ("national innovation award winnerAnanya Rao", "Ananya Rao received the Best Innovation Award."),
    ("spatial computer vision for motor microcontrollers", "real-time spatial vision and low-latency motor microcontrollers."),
    ("cyber security summit student presentations", "IoT and Cyber Security Summit 2026."),
    ("smart infrastructure edge encryption demo", "demonstrated edge encryption, intrusion detection systems."),
    ("quadcopter waypoint navigation performance", "99.4% waypoint navigation accuracy in indoor GPS-denied environments."),
    ("multi-agent swarm intelligence flight demonstration", "Multi-Agent Swarm Intelligence and drone formation flying."),
    ("embedded systems expo student telemetry designs", "Sensors and smart telemetry units designed by students."),
    ("first prize national championship team", "The team won first prize at the National Robotics Championship 2026."),
    ("visual-inertial navigation for GPS denial", "visual-inertial odometry and real-time obstacle avoidance in GPS-denied environments."),
    ("motor control microcontrollers in quadruped legged devices", "low-latency motor microcontrollers in quadruped legged robot."),
    ("edge sensor encryption and mesh networking", "edge encryption and secure mesh protocols for smart infrastructure."),
    ("robotic symposium proceedings and research papers", "Faculty and student researchers convened to demonstrate edge encryption."),
    ("indoor aerial drone obstacle detection", "real-time obstacle avoidance in indoor GPS-denied environments."),
    ("student research award in AI innovation", "Lead researcher Ananya Rao received the Best Innovation Award."),
    ("quadruped robot 1st place cash winner", "Team QuadRobo (1st Place Winner, ₹75,000 award)."),
    ("mesh protocol security for smart telemetry", "secure mesh protocols for smart infrastructure."),
    ("spatial vision motor control for quadruped", "real-time spatial vision and low-latency motor microcontrollers."),
    ("indoor positioning metrics in GPS denial", "99.4% waypoint navigation accuracy in indoor GPS-denied environments."),
    ("national robotics champion lead researcher", "Lead researcher Ananya Rao received the Best Innovation Award."),
]


@pytest.mark.asyncio
async def test_retrieval_paraphrase_benchmark_recall_and_mrr(db_session):
    """Measures Recall@5 and Mean Reciprocal Rank (MRR) across 40 distinct labelled paraphrase queries against database chunks."""
    from app.modules.documents.models import DocumentChunk, SourceDocument
    from app.modules.documents.retriever import retrieve

    # Seed benchmark corpus into database session
    doc = SourceDocument(filename="benchmark_corpus.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", storage_path="/tmp/benchmark_corpus.docx")
    db_session.add(doc)
    await db_session.flush()

    for idx, (query, target) in enumerate(PARAPHRASE_BENCHMARK_SET):
        target_vec = await embed_text(target)
        chunk = DocumentChunk(
            document_id=doc.id,
            page_number=1,
            text=target,
            char_start=0,
            char_end=len(target),
            embedding=target_vec,
            embedding_model="bge-base-en-v1.5",
            section_label=f"Section {idx}",
        )
        db_session.add(chunk)
    await db_session.flush()

    total_queries = len(PARAPHRASE_BENCHMARK_SET)
    mrr_sum = 0.0
    recall_at_5_count = 0

    for query, target in PARAPHRASE_BENCHMARK_SET:
        candidates = await retrieve(db=db_session, query=query, top_k=5)

        # Check if target text is in top 5 retrieved candidates
        retrieved_texts = [c["text"] for c in candidates]
        if target in retrieved_texts:
            recall_at_5_count += 1
            rank = retrieved_texts.index(target) + 1
            mrr_sum += 1.0 / rank
        else:
            print(f"MISSING: query='{query[:30]}...' top_retrieved={retrieved_texts[:1]}")

    recall_at_5 = recall_at_5_count / total_queries
    mrr = mrr_sum / total_queries

    print(f"\n--- Paraphrase Retrieval Benchmark Results ---")
    print(f"Queries Evaluated: {total_queries}")
    print(f"Recall@5: {recall_at_5:.4f} ({recall_at_5_count}/{total_queries})")
    print(f"MRR: {mrr:.4f}")

    assert recall_at_5 >= 0.80
    assert mrr >= 0.65
