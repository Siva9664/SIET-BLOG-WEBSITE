"""
SIET Engineering Magazine - Style Guide & Few-Shot Prompting Configuration

Defines house style guidelines and high-quality exemplar past articles for few-shot LLM prompting.
"""
from typing import List, Dict, Any

SIET_MAGAZINE_STYLE_GUIDE = """
- Tone: Professional, inspirational, but warm — written specifically for engineering students, faculty, and industry partners.
- Key Entities: Always mention key people by full name and title if provided (e.g., "Dr. S. Sharma, Head of AI & Machine Learning").
- Forbidden Clichés: Avoid generic AI phrases like "In today's fast-paced world", "In conclusion", "It goes without saying", "Testament to", or "Embark on a journey".
- Headlines: Short, specific, and punchy (e.g., "Autonomous Swarm Robotics Takes Top Honors at SIET TechFest 2026", not "A Great Event").
- Concrete Details: Include exact metrics and statistics whenever mentioned in raw notes (e.g., attendance counts, prize purses, project counts, sensor specs).
- Photo Captions: Must be strictly under 12 words, factual, and concise — zero flowery adjectives.
- Voice: Use active, engaging voice throughout.
- Punctuation: Avoid excessive exclamation marks — maximum one per article, if any.
"""

FEW_SHOT_EXAMPLES: List[Dict[str, Any]] = [
    {
        "category": "hackathon",
        "raw_notes": """SIET HackNation 2026
Date: March 14, 2026
Location: Main Auditorium & IoT Lab
Keynote: Dr. K. Arunkumar (VP of AI, Apex Systems)
250 students, 62 teams, 24-hour continuous coding challenge
Themes: Smart Grid Energy, Autonomous Agri-Drones, Medical Diagnostics
Winners: Team NeuralCrop (1st place, ₹50,000 prize) for low-cost edge AI crop disease detector. Runner up: Team VoltGrid for micro-grid load balancer.
Jury praised code modularity and real-world deployment readiness.""",
        "output_title": "SIET HackNation 2026: 24 Hours of Edge-AI Innovation",
        "output_description": "Sri Shakthi Institute of Engineering & Technology hosted 250 student developers across 62 teams for HackNation 2026. Participants engineered working prototypes in IoT smart grids, agri-drones, and medical diagnostics under a 24-hour deadline. Team NeuralCrop secured the top spot with their edge-AI crop disease diagnosis system.",
        "output_writeup": """SIET HackNation 2026: 24 Hours of Edge-AI Innovation

62 Teams Push the Boundaries of Embedded Intelligence

The Main Auditorium and IoT Laboratories at SIET transformed into a high-intensity innovation hub for HackNation 2026, bringing together 250 undergraduate developers for a 24-hour continuous engineering sprint. Inaugurated by Dr. K. Arunkumar, Vice President of AI at Apex Systems, the hackathon challenged teams to build deployable prototypes addressing critical needs in smart grid energy, autonomous agriculture, and digital healthcare.

Edge AI Takes Center Stage in Agriculture

Team NeuralCrop earned first place and the ₹50,000 cash prize for their real-time leaf disease classifier running on low-cost edge hardware. Utilizing a custom quantised convolutional network, their handheld device identifies crop infections within 200 milliseconds without internet connectivity.

"The technical depth shown by these students in hardware-constrained AI optimization is exceptional," noted Dr. Arunkumar during the final project evaluation. Runner-up honors went to Team VoltGrid for their adaptive micro-grid load balancer capable of preventing localized transformer overloads.

Scaling Prototypes for Production

The jury commended all 62 teams for clean software architecture and emphasis on field readiness. SIET's Incubation Cell announced seed assistance for the top three projects to support patent filing and field trials.""",
        "captions": [
            "Dr. K. Arunkumar inaugurating SIET HackNation 2026 at Main Auditorium.",
            "Team NeuralCrop demonstrating their edge AI crop diagnostic unit.",
            "Participants collaborating during the 24-hour continuous coding challenge."
        ],
        "toc_summary": "62 student teams build edge-AI and smart-grid prototypes at HackNation 2026."
    },
    {
        "category": "symposium",
        "raw_notes": """Annual Research Symposium & Innovation Expo 2026
Date: February 20, 2026
Organized by: Dept of ECE & CSE, SIET
Guest of Honor: Er. R. Meenakshi (Senior Principal Engineer, ISRO Satellite Centre)
18 research papers presented, 35 hardware project models displayed
Highlights: Quadruped legged robot demo by final year Robotics batch, solar-powered EV conversion kit, wireless EEG-controlled wheelchair
Over 450 visitors including local industry delegates.""",
        "output_title": "SIET Research Symposium 2026: Next-Gen Robotics & Autonomous Mobility",
        "output_description": "The Departments of ECE and CSE at SIET convened their Annual Research Symposium and Innovation Expo, presenting 18 peer-reviewed paper presentations and 35 live hardware demonstrations. Attracting over 450 industry delegates and visitors, the expo featured quadruped robotics, solar EV conversion kits, and brain-computer interfaces.",
        "output_writeup": """SIET Research Symposium 2026: Next-Gen Robotics & Autonomous Mobility

Industry Leaders Review 35 Live Hardware Demonstrations at SIET Expo

Sri Shakthi Institute of Engineering & Technology held its Annual Research Symposium and Innovation Expo, bringing together 450 visitors, researchers, and industrial leaders. Chief Guest Er. R. Meenakshi, Senior Principal Engineer at the ISRO Satellite Centre, opened the paper sessions featuring 18 peer-reviewed student presentations spanning embedded systems, satellite telemetry, and power electronics.

Quadruped Robotics and Assistive Technology Steal the Spotlight

A major highlight of the live exposition was the quadruped legged robot created by the final-year Robotics batch. Operating on custom inverse kinematics software, the robot navigated uneven terrain obstacles autonomously. 

Simultaneously, the Assistive Devices Lab demonstrated a wireless EEG-controlled wheelchair designed to assist individuals with severe mobility impairments. Er. Meenakshi commended the students for bridging theoretical control systems with tangible hardware solutions tailored for societal impact.""",
        "captions": [
            "Er. R. Meenakshi inspecting the student quadruped robot demonstration.",
            "Final year ECE students presenting paper on satellite telemetry.",
            "Live demonstration of solar-powered EV conversion kit at Innovation Expo."
        ],
        "toc_summary": "18 research papers and 35 hardware models showcased at Annual Symposium 2026."
    },
    {
        "category": "workshop",
        "raw_notes": """Hands-on Workshop on Generative AI & RAG Architectures
Date: January 10, 2026
Resource Person: Prof. N. Venkatesh (Dept of Data Science, SIET)
Target Audience: 120 3rd Year CSE & IT Students
Topics covered: Vector databases, ChromaDB, LangChain, Llama-3 local fine-tuning
Outcome: Every student built a domain-specific Q&A bot over college syllabus data""",
        "output_title": "Hands-on Masterclass: Generative AI & RAG Architectures at SIET",
        "output_description": "SIET's Department of Data Science conducted an intensive technical workshop on Retrieval-Augmented Generation (RAG) and local LLM deployment for 120 computer science undergraduates. Led by Prof. N. Venkatesh, students learned vector database indexing with ChromaDB and built custom academic Q&A bots.",
        "output_writeup": """Hands-on Masterclass: Generative AI & RAG Architectures at SIET

120 Computer Science Students Deploy Custom RAG Assistants Using Local LLMs

The Department of Data Science at SIET organized an intensive hands-on workshop dedicated to Retrieval-Augmented Generation (RAG) and open-weight language model fine-tuning. Conducted by Prof. N. Venkatesh, the session provided 120 third-year CSE and IT undergraduates with practical exposure to industrial AI architectures.

Building Private Q&A Bots with ChromaDB and LangChain

Rather than relying purely on cloud APIs, students configured local vector stores using ChromaDB to index SIET course syllabi and research papers. Prof. Venkatesh guided participants through chunking strategies, embedding generation, and prompt optimization.

By the afternoon session, every participant successfully deployed a private Q&A bot capable of accurately answering complex engineering queries with zero external data leaks. "Mastering RAG pipelines equips our students with immediately relevant software engineering skills," stated Prof. Venkatesh.""",
        "captions": [
            "Prof. N. Venkatesh explaining vector embeddings during the AI masterclass.",
            "Undergraduate students implementing ChromaDB indexing pipelines in lab."
        ],
        "toc_summary": "120 CSE students build custom RAG Q&A bots during intensive AI workshop."
    }
]


def get_best_matching_few_shot(raw_notes: str = "", event_name: str = "") -> Dict[str, Any]:
    """
    Selects the most relevant few-shot example based on keyword heuristics
    (hackathon, symposium/expo, workshop/lecture). Defaults to the first example.
    """
    combined_text = f"{event_name} {raw_notes}".lower()
    
    if any(k in combined_text for k in ["hack", "code", "contest", "sprint", "ideathon"]):
        for ex in FEW_SHOT_EXAMPLES:
            if ex["category"] == "hackathon":
                return ex

    if any(k in combined_text for k in ["expo", "symposium", "conference", "paper", "project display"]):
        for ex in FEW_SHOT_EXAMPLES:
            if ex["category"] == "symposium":
                return ex

    if any(k in combined_text for k in ["workshop", "seminar", "masterclass", "lecture", "training"]):
        for ex in FEW_SHOT_EXAMPLES:
            if ex["category"] == "workshop":
                return ex

    return FEW_SHOT_EXAMPLES[0]
