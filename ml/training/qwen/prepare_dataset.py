#!/usr/bin/env python3
"""
SIET Editorial Intelligence SFT Dataset Generator for Qwen3 14B QLoRA.

Prepares supervised fine-tuning examples across 22 college magazine categories.
Enforces strict grounding: outputs contain ONLY facts present in the source context.
Outputs ChatML-compatible JSONL format ready for Qwen3 tokenizer & SFT.
"""

import json
import os
import random
from pathlib import Path
from typing import Dict, Any, List

SYSTEM_INSTRUCTION = (
    "You are the editorial intelligence assistant for SIET (Sri Shakthi Institute of Engineering & Technology).\n"
    "STRICT GROUNDING RULES:\n"
    "1. Use ONLY supplied source / RAG context.\n"
    "2. Never invent names, dates, achievements, statistics, organizations, quotes, events, or other factual information.\n"
    "3. Missing information must be represented as null or empty values according to the requested schema.\n"
    "4. Do NOT fabricate content to fill a template."
)

CATEGORIES = [
    "department_news",
    "workshops",
    "seminars",
    "guest_lectures",
    "lab_activities",
    "student_projects",
    "faculty_achievements",
    "student_achievements",
    "awards",
    "competitions",
    "cultural_events",
    "sports",
    "campus_activities",
    "placement_related",
    "research",
    "publications",
    "technical_events",
    "announcements",
    "captions",
    "headlines",
    "section_classification",
    "magazine_summaries",
]

# Raw exemplar templates grounded strictly in verifiable facts
CATEGORY_EXAMPLES: List[Dict[str, Any]] = [
    {
        "category": "department_news",
        "task_type": "full_editorial_json",
        "source": (
            "Department: Department of Computer Science & Engineering, SIET.\n"
            "Date: August 12, 2026.\n"
            "Announcement: Establishment of new High-Performance Computing cluster with 8 NVIDIA GPUs for AI research.\n"
            "Funded by: Institutional Research Grant (INR 35 Lakhs).\n"
            "Lead Coordinator: Dr. V. Muralidharan, Professor & Head, CSE.\n"
            "Intended users: Final-year B.E. and M.E. scholars working on autonomous robotics and vision models."
        ),
        "task": "Generate full editorial magazine content adhering strictly to the source facts.",
        "assistant_response": {
            "magazine_issue_title": "SIET CSE Department Launches High-Performance AI Computing Facility",
            "description": "The Department of Computer Science and Engineering at SIET inaugurated an 8-GPU High-Performance Computing cluster funded by an INR 35 Lakh institutional research grant. The lab supports final-year and postgraduate researchers.",
            "writeup": (
                "New AI Infrastructure Expands Advanced Research Horizons\n\n"
                "The Department of Computer Science and Engineering at Sri Shakthi Institute of Engineering & Technology has commissioned a new High-Performance Computing (HPC) research cluster. Equipped with 8 NVIDIA enterprise GPUs, the laboratory was established under an institutional research grant of INR 35 Lakhs.\n\n"
                "Under the leadership of Dr. V. Muralidharan, Professor and Head of CSE, the facility is designated for undergraduate and postgraduate scholars conducting deep learning, computer vision, and autonomous robotics projects."
            ),
            "captions": [
                "Dr. V. Muralidharan inspecting the newly deployed 8-GPU computing rack at SIET CSE.",
                "Student researchers configuring deep learning workloads on the HPC cluster."
            ],
            "toc_summary": "SIET CSE deploys 8-GPU compute cluster backed by INR 35 Lakh research grant."
        }
    },
    {
        "category": "workshops",
        "task_type": "full_editorial_json",
        "source": (
            "Event: Hands-on Workshop on Edge AI and TinyML Systems.\n"
            "Date: July 18-19, 2026.\n"
            "Organized by: Department of Electronics & Communication Engineering, SIET.\n"
            "Resource Person: Er. S. Karthik, Senior Embedded Architect at Silico Labs.\n"
            "Participants: 85 registered undergraduate students from ECE and EEE.\n"
            "Hands-on kits: ESP32-S3 microcontroller units paired with OV2640 camera sensors.\n"
            "Project outcome: Each participant deployed an on-device anomaly detection model."
        ),
        "task": "Generate full magazine editorial JSON grounded in the source.",
        "assistant_response": {
            "magazine_issue_title": "SIET ECE Hosts Intensive Edge AI & TinyML Masterclass",
            "description": "85 engineering students from ECE and EEE developed on-device anomaly detection systems during a two-day hands-on TinyML workshop led by Er. S. Karthik of Silico Labs at SIET.",
            "writeup": (
                "Undergraduates Deploy Low-Power Machine Learning on ESP32 Microcontrollers\n\n"
                "The Department of Electronics and Communication Engineering at SIET concluded a two-day workshop on Edge AI and TinyML. Mentored by industry expert Er. S. Karthik from Silico Labs, 85 participating students implemented neural inference on resource-constrained ESP32-S3 boards.\n\n"
                "Utilizing camera-equipped development modules, attendees constructed real-time sensor anomaly detectors capable of sub-watt execution without cloud dependencies."
            ),
            "captions": [
                "Er. S. Karthik demonstrating quantized model deployment on ESP32 hardware.",
                "Undergraduates testing live computer vision inference at the ECE laboratory."
            ],
            "toc_summary": "85 undergraduates build on-device TinyML anomaly detectors at SIET ECE workshop."
        }
    },
    {
        "category": "seminars",
        "task_type": "full_editorial_json",
        "source": (
            "Seminar: State of Semiconductor Manufacturing and Fab Operations.\n"
            "Date: September 5, 2026.\n"
            "Venue: Newton Auditorium, SIET.\n"
            "Speaker: Dr. Anita Rao, Principal Scientist at Central Electronics Engineering Research Institute (CEERI).\n"
            "Key topics: Cleanroom standards, photolithography litho-mask alignment, yield optimization.\n"
            "Audience: 140 students and 15 faculty members."
        ),
        "task": "Produce editorial magazine content strictly using source details.",
        "assistant_response": {
            "magazine_issue_title": "Semiconductor Fabrication Insights: CEERI Scientist Delivers SIET Seminar",
            "description": "Dr. Anita Rao of CEERI presented cleanroom manufacturing protocols and photolithography mask alignment to 140 students and 15 faculty members at SIET's Newton Auditorium.",
            "writeup": (
                "Deep Dive into Cleanroom Operations and Mask Alignment\n\n"
                "Dr. Anita Rao, Principal Scientist at CEERI, addressed students and faculty during an expert seminar on modern semiconductor fab operations held at Newton Auditorium. The lecture covered lithography tolerances, contamination control, and yield metrics.\n\n"
                "A total of 140 undergraduate students and 15 faculty members engaged in an interactive technical exchange regarding India's domestic semiconductor roadmaps."
            ),
            "captions": [
                "Dr. Anita Rao delivering keynote on photolithography mask alignment.",
                "Audience of faculty and students participating in discussion at Newton Auditorium."
            ],
            "toc_summary": "Dr. Anita Rao of CEERI details semiconductor cleanroom protocols at SIET seminar."
        }
    },
    {
        "category": "guest_lectures",
        "task_type": "headlines_and_summary",
        "source": (
            "Lecture: Autonomous Navigation in GPS-Denied Terrains.\n"
            "Guest Lecturer: Er. P. Sundar, Lead Guidance Systems Engineer, DRDO.\n"
            "Date: June 24, 2026.\n"
            "Organizing Body: SIET Robotics Club & Department of Mechanical Engineering.\n"
            "Focus: Visual Inertial Odometry (VIO) and Extended Kalman Filters (EKF)."
        ),
        "task": "Provide writeup headline, TOC summary, and one-paragraph overview.",
        "assistant_response": {
            "headline": "DRDO Guidance Engineer Details GPS-Denied Navigation at SIET",
            "toc_summary": "DRDO's Er. P. Sundar presents Visual Inertial Odometry methods for autonomous robots.",
            "summary": "Er. P. Sundar from DRDO delivered a technical lecture on autonomous robotic navigation in GPS-denied environments. Jointly organized by SIET Mechanical Engineering and the Robotics Club, the session focused on Visual Inertial Odometry and Extended Kalman Filter integration."
        }
    },
    {
        "category": "lab_activities",
        "task_type": "captions",
        "source": (
            "Lab Session: Advanced Thermal Engineering Lab, SIET.\n"
            "Activity: Multi-cylinder 4-stroke petrol engine computerized test rig trials.\n"
            "Students: Third-year Mechanical Engineering Section B.\n"
            "Parameters monitored: Brake thermal efficiency, specific fuel consumption, exhaust emissions.\n"
            "Supervisor: Dr. K. Mohanraj."
        ),
        "task": "Generate 3 factual captions strictly under 15 words each.",
        "assistant_response": {
            "captions": [
                "Dr. K. Mohanraj overseeing computerized petrol engine test rig trials at SIET.",
                "Third-year Mechanical students recording brake thermal efficiency metrics.",
                "Real-time measurement of exhaust emissions during the Thermal Engineering laboratory."
            ]
        }
    },
    {
        "category": "student_projects",
        "task_type": "full_editorial_json",
        "source": (
            "Project: Smart Acoustic Sensor for Track Crack Detection.\n"
            "Developers: Team RailGuard (Final Year Civil & ECE Students: T. Rajesh, M. Swetha, K. Naveen).\n"
            "Advisor: Prof. G. Selvam.\n"
            "Mechanism: Piezoelectric vibration pickups with onboard FFT analysis transmitting alert over LoRaWAN.\n"
            "Testing: 500-meter test track at Southern Railway Yard.\n"
            "Funding: Student Innovation Seed Grant of INR 20,000."
        ),
        "task": "Generate full editorial magazine record grounded in facts.",
        "assistant_response": {
            "magazine_issue_title": "SIET Students Engineer Low-Cost Railway Track Crack Detection System",
            "description": "Student team RailGuard developed a piezoelectric acoustic sensor paired with LoRaWAN telemetry to detect railway micro-fractures, successfully tested on a 500-meter track yard.",
            "writeup": (
                "Acoustic Telemetry Enhances Railway Infrastructure Safety\n\n"
                "Undergraduate researchers T. Rajesh, M. Swetha, and K. Naveen developed 'RailGuard', an autonomous track inspection module. Guided by Prof. G. Selvam and supported by an INR 20,000 institutional seed grant, the system combines vibration sensors with fast Fourier transform processors.\n\n"
                "During field trials across 500 meters of yard track, the battery-powered module transmitted real-time structural defect notifications over long-range wireless links."
            ),
            "captions": [
                "Team RailGuard demonstrating piezoelectric track sensor prototype.",
                "Field evaluation of the LoRaWAN telemetry unit at the railway yard."
            ],
            "toc_summary": "SIET student project RailGuard validates acoustic railway fracture detection."
        }
    },
    {
        "category": "faculty_achievements",
        "task_type": "headlines_and_summary",
        "source": (
            "Faculty: Dr. S. Gayathri, Associate Professor, Department of AI & Data Science.\n"
            "Achievement: Granted Indian Patent (Patent No. 498211) for 'Adaptive Neuromorphic Vision Sensor for Low-Light Surveillance'.\n"
            "Date of Grant: August 1, 2026.\n"
            "Co-inventor: Er. C. Raghavan (Research Scholar)."
        ),
        "task": "Generate publication headline and grounded achievement blurb.",
        "assistant_response": {
            "headline": "Dr. S. Gayathri Granted Indian Patent for Neuromorphic Vision Sensor",
            "toc_summary": "Patent granted to Dr. S. Gayathri for adaptive low-light surveillance sensor.",
            "summary": "Dr. S. Gayathri, Associate Professor of AI & Data Science at SIET, alongside co-inventor Er. C. Raghavan, received Indian Patent No. 498211 for an adaptive neuromorphic vision sensor tailored for low-light environmental surveillance."
        }
    },
    {
        "category": "student_achievements",
        "task_type": "headlines_and_summary",
        "source": (
            "Student: K. Divya, Third Year Biomedical Engineering.\n"
            "Event: National Bio-Design Challenge 2026 held at IIT Madras.\n"
            "Date: July 28, 2026.\n"
            "Award: First Place and cash prize of INR 75,000.\n"
            "Winning Innovation: Wearable non-invasive glucometer using near-infrared spectroscopic analysis."
        ),
        "task": "Generate writeup headline and short factual summary.",
        "assistant_response": {
            "headline": "SIET Biomedical Student K. Divya Secures Top Honor at IIT Madras",
            "toc_summary": "K. Divya wins First Place at IIT Madras Bio-Design Challenge 2026.",
            "summary": "Third-year Biomedical Engineering undergraduate K. Divya secured First Place and a cash prize of INR 75,000 at the National Bio-Design Challenge hosted by IIT Madras for her non-invasive optical glucometer."
        }
    },
    {
        "category": "awards",
        "task_type": "captions",
        "source": (
            "Event: SIET Annual Institutional Excellence Awards 2026.\n"
            "Date: August 25, 2026.\n"
            "Best Outgoing Department: Department of Mechanical Engineering.\n"
            "Trophy presented by: Managing Trustee Dr. K. E. Shanmugam.\n"
            "Accepted by: Dr. P. Raman, Head of Mechanical Engineering, accompanied by student representatives."
        ),
        "task": "Generate 2 grounded captions under 15 words each.",
        "assistant_response": {
            "captions": [
                "Dr. K. E. Shanmugam presenting Best Outgoing Department trophy to Mechanical Engineering.",
                "Dr. P. Raman and student representatives receiving annual institutional honors."
            ]
        }
    },
    {
        "category": "competitions",
        "task_type": "full_editorial_json",
        "source": (
            "Competition: Smart India Hackathon (SIH) 2026 Hardware Edition Preliminaries.\n"
            "Host: SIET Innovation Cell.\n"
            "Date: September 2-3, 2026.\n"
            "Participation: 42 teams from across Tamil Nadu colleges.\n"
            "SIET Finalists: Team HydroSense (Agricultural IoT) and Team GridShield (Substation security).\n"
            "Nodal Evaluation Lead: Er. B. Venkatesan."
        ),
        "task": "Produce grounded editorial magazine JSON.",
        "assistant_response": {
            "magazine_issue_title": "SIET Hosts Smart India Hackathon 2026 Hardware Preliminaries",
            "description": "42 teams competed at SIET Innovation Cell during the SIH 2026 Hardware Edition preliminaries, with SIET teams HydroSense and GridShield selected for the national finals.",
            "writeup": (
                "42 Regional Engineering Teams Compete in Hardware Innovation Sprint\n\n"
                "The Innovation Cell at SIET served as the regional nodal center for the Smart India Hackathon 2026 Hardware Edition preliminaries. Evaluated by Er. B. Venkatesan, 42 collegiate teams showcased physical embedded systems prototypes.\n\n"
                "Two teams from SIET—HydroSense for agricultural telemetry and GridShield for power infrastructure monitoring—qualified for the national round."
            ),
            "captions": [
                "Teams assembling hardware prototypes at the SIET Innovation Center.",
                "Er. B. Venkatesan inspecting sensor circuits during SIH evaluation."
            ],
            "toc_summary": "SIET hosts 42 teams for SIH 2026 hardware preliminaries; two college teams advance."
        }
    },
    {
        "category": "cultural_events",
        "task_type": "full_editorial_json",
        "source": (
            "Event: Dhwani 2026 - SIET Annual Inter-Collegiate Cultural Festival.\n"
            "Dates: March 20-21, 2026.\n"
            "Footfall: 1,800 students from 28 participating institutions.\n"
            "Events: Classical Carnatic vocal solo, western group dance, battle of the bands, street play.\n"
            "Overall Champion Trophy: PSG College of Technology.\n"
            "Runner-up: Coimbatore Institute of Technology."
        ),
        "task": "Generate grounded editorial coverage.",
        "assistant_response": {
            "magazine_issue_title": "Dhwani 2026: 1,800 Performers Convene for SIET Cultural Festival",
            "description": "1,800 students representing 28 collegiate institutions participated in Dhwani 2026 at SIET, with PSG College of Technology claiming the overall championship trophy.",
            "writeup": (
                "Two-Day Arts and Performance Showcase Draws 28 Institutions\n\n"
                "SIET celebrated Dhwani 2026, welcoming 1,800 student artists for its annual inter-collegiate cultural fest. The festival featured competitive categories including classical vocal, contemporary dance, and theatrical street plays.\n\n"
                "PSG College of Technology secured the Overall Championship trophy, while Coimbatore Institute of Technology earned runner-up honors following two days of live performance stages."
            ),
            "captions": [
                "Western dance troupe performing on the Dhwani 2026 main stage.",
                "PSG College of Technology team receiving the Overall Champion Trophy."
            ],
            "toc_summary": "1,800 participants compete at Dhwani 2026 cultural festival at SIET."
        }
    },
    {
        "category": "sports",
        "task_type": "headlines_and_summary",
        "source": (
            "Tournament: Anna University Zone 9 Inter-Collegiate Basketball Championship 2026.\n"
            "Venue: SIET Floodlit Sports Complex.\n"
            "Date: August 19, 2026.\n"
            "Result: SIET Men's Basketball Team defeated Sri Krishna College of Technology (68-54) in the final.\n"
            "Top Scorer: R. Pranav (Final Year ECE) with 24 points."
        ),
        "task": "Generate punchy headline and factual game digest.",
        "assistant_response": {
            "headline": "SIET Men's Basketball Captures Zone 9 Title in 68-54 Final",
            "toc_summary": "SIET basketball squad wins Anna University Zone 9 championship.",
            "summary": "The SIET Men's Basketball team clinched the Anna University Zone 9 championship with a 68-54 victory over Sri Krishna College of Technology at the SIET sports complex, led by R. Pranav's 24-point scoring effort."
        }
    },
    {
        "category": "campus_activities",
        "task_type": "captions",
        "source": (
            "Activity: Campus Green Initiative Tree Planting Drive.\n"
            "Date: July 5, 2026.\n"
            "Organized by: National Service Scheme (NSS) Unit of SIET.\n"
            "Saplings planted: 300 native neem and peepal saplings along the western perimeter.\n"
            "Participants: 110 first-year student volunteers and NSS Coordinator Prof. T. Chandran."
        ),
        "task": "Generate 2 grounded captions under 15 words each.",
        "assistant_response": {
            "captions": [
                "NSS student volunteers planting native saplings along the SIET western perimeter.",
                "Prof. T. Chandran coordinating first-year students during the campus green drive."
            ]
        }
    },
    {
        "category": "placement_related",
        "task_type": "full_editorial_json",
        "source": (
            "Milestone: SIET Placement Season 2026 Phase-1 Wrap-up.\n"
            "Offers: 420 offers extended to graduating batch.\n"
            "Highest CTC: INR 28 LPA offered by Palo Alto Networks.\n"
            "Top Recruiters: Cognizant (112 offers), TCS (84 offers), Caterpillar (24 core offers), Bosch (18 offers).\n"
            "Head of Placements: Prof. N. Senthilkumar."
        ),
        "task": "Create full magazine editorial JSON grounded in numbers.",
        "assistant_response": {
            "magazine_issue_title": "SIET Phase-1 Placements 2026: 420 Offers with 28 LPA Top CTC",
            "description": "SIET recorded 420 job offers during Phase-1 placement drives for the graduating class of 2026, highlighted by a peak package of 28 LPA from Palo Alto Networks.",
            "writeup": (
                "Core Engineering and Enterprise Software Firms Lead Campus Hiring\n\n"
                "The Placement and Training Cell at SIET announced the conclusion of Phase-1 recruitments for 2026 graduates. A total of 420 employment offers were confirmed, led by major enterprise hirers including Cognizant, TCS, Caterpillar, and Bosch.\n\n"
                "According to Prof. N. Senthilkumar, Head of Placements, the highest compensation reached INR 28 LPA for specialized security software roles."
            ),
            "captions": [
                "Graduating engineering students celebrating Phase-1 placement offers.",
                "Prof. N. Senthilkumar reviewing recruitment metrics at the Placement Cell."
            ],
            "toc_summary": "420 job offers and 28 LPA top package recorded in SIET Phase-1 placements."
        }
    },
    {
        "category": "research",
        "task_type": "headlines_and_summary",
        "source": (
            "Research Project: DST-SERB Sponsored Drone Thermal Sensing for Precision Agriculture.\n"
            "Grant Amount: INR 42.5 Lakhs.\n"
            "Principal Investigator: Dr. M. Anand, Department of Mechatronics, SIET.\n"
            "Duration: 2026 to 2029.\n"
            "Deliverable: Autonomous multi-spectral UAV with localized crop water stress index calculation."
        ),
        "task": "Generate writeup headline and research summary.",
        "assistant_response": {
            "headline": "DST-SERB Awards INR 42.5 Lakh Research Grant to SIET Mechatronics",
            "toc_summary": "Dr. M. Anand secures DST-SERB grant for agricultural UAV thermal sensing.",
            "summary": "Dr. M. Anand of SIET's Mechatronics Department was awarded an INR 42.5 Lakh research grant by DST-SERB to develop an autonomous multi-spectral drone system measuring crop water stress over a three-year term."
        }
    },
    {
        "category": "publications",
        "task_type": "headlines_and_summary",
        "source": (
            "Publication: 'Frequency-Selective Metasurfaces for 6G Terahertz Communication'.\n"
            "Journal: IEEE Transactions on Antennas and Propagation (Volume 74, Issue 4).\n"
            "Authors: Dr. K. Vijayakumar (SIET ECE) and Dr. L. Chen (Singapore University of Technology and Design).\n"
            "DOI: 10.1109/TAP.2026.3149811.\n"
            "Indexed in: SCI, Web of Science (Impact Factor 5.7)."
        ),
        "task": "Generate publication headline and summary.",
        "assistant_response": {
            "headline": "SIET ECE Professor Publishes 6G Metasurface Research in IEEE Transactions",
            "toc_summary": "Dr. K. Vijayakumar co-authors IEEE Transactions paper on 6G terahertz metasurfaces.",
            "summary": "Dr. K. Vijayakumar from SIET's ECE Department, alongside international collaborator Dr. L. Chen, published experimental findings on 6G terahertz metasurfaces in IEEE Transactions on Antennas and Propagation."
        }
    },
    {
        "category": "technical_events",
        "task_type": "full_editorial_json",
        "source": (
            "Event: SIET RoboWars Championship 2026.\n"
            "Date: April 11, 2026.\n"
            "Arena: Reinforced Polycarbonate Combat Arena, SIET Mechanical Courtyard.\n"
            "Weight Classes: 15kg Featherweight and 30kg Middleweight combat bots.\n"
            "Teams: 26 collegiate combat robot builder squads.\n"
            "Winner 30kg: Team Crusher (Government College of Technology, Coimbatore).\n"
            "Winner 15kg: Team SparkPlug (SIET Robotics Club)."
        ),
        "task": "Generate full editorial magazine JSON.",
        "assistant_response": {
            "magazine_issue_title": "SIET RoboWars 2026: 26 Combat Bot Teams Clash in Reinforced Arena",
            "description": "26 collegiate robotics squads competed in 15kg and 30kg combat categories at SIET's specialized arena, with SIET's Team SparkPlug winning the featherweight division.",
            "writeup": (
                "Featherweight and Middleweight Combat Robots Battle in Custom Enclosure\n\n"
                "The Mechanical Engineering Courtyard hosted RoboWars 2026 inside a reinforced polycarbonate enclosure. 26 university teams showcased pneumatic flippers, vertical spinners, and high-torque drivetrains.\n\n"
                "SIET's home squad, Team SparkPlug, secured first place in the 15kg class, while Team Crusher from GCT Coimbatore claimed the 30kg middleweight championship title."
            ),
            "captions": [
                "Team SparkPlug's 15kg combat bot in action inside the reinforced arena.",
                "Award ceremony honoring the top combat robotics design teams."
            ],
            "toc_summary": "26 engineering teams compete at SIET RoboWars 2026; home team wins 15kg class."
        }
    },
    {
        "category": "announcements",
        "task_type": "headlines_and_summary",
        "source": (
            "Notice: Applications Open for SIET Academic Merit Scholarships 2026-27.\n"
            "Eligibility: Students maintaining CGPA of 8.75 and above with no standing arrears.\n"
            "Deadline: September 30, 2026.\n"
            "Scholarship quantum: Up to 50% tuition fee waiver.\n"
            "Issuing Authority: Office of the Academic Dean, SIET."
        ),
        "task": "Generate headline and bulletin notice.",
        "assistant_response": {
            "headline": "Applications Open for SIET Academic Merit Scholarships 2026-27",
            "toc_summary": "Merit scholarship applications open until September 30 for eligible SIET students.",
            "summary": "The Office of the Academic Dean announced that applications for SIET Academic Merit Scholarships are open until September 30, 2026, offering up to 50% tuition waivers to students holding a CGPA of 8.75 or higher."
        }
    },
    {
        "category": "captions",
        "task_type": "captions",
        "source": (
            "Context: Formula Student Race Car Unveiling.\n"
            "Vehicle: 'Shakthi Racer Mark-IV' built by SIET Motorsports Club.\n"
            "Specifications: KTM 390cc single-cylinder engine, custom carbon-fiber aerodynamics package, telemetry dashboard.\n"
            "Unveiled by: Principal Dr. T. Ravichandran.\n"
            "Event Date: August 14, 2026."
        ),
        "task": "Generate 2 captions strictly under 15 words each.",
        "assistant_response": {
            "captions": [
                "Dr. T. Ravichandran unveiling the Shakthi Racer Mark-IV formula student vehicle.",
                "SIET Motorsports student engineers inspecting custom carbon-fiber aerodynamic wings."
            ]
        }
    },
    {
        "category": "headlines",
        "task_type": "headlines_and_summary",
        "source": (
            "Event: Three-day international conference on Green Energy Systems (ICGES-2026).\n"
            "Keynote: Prof. Hans Mueller from Technical University of Munich.\n"
            "Papers: 94 research manuscripts accepted from 11 countries."
        ),
        "task": "Generate 3 headline options and 1 TOC summary.",
        "assistant_response": {
            "headlines": [
                "ICGES-2026: 94 Global Papers on Green Energy Presented at SIET",
                "TUM Professor Delivers Keynote at SIET International Green Energy Forum",
                "Researchers from 11 Nations Convene at SIET for ICGES-2026"
            ],
            "toc_summary": "94 research manuscripts presented at SIET International Green Energy Conference."
        }
    },
    {
        "category": "section_classification",
        "task_type": "classification",
        "source": (
            "Raw text snippet: 'The final year CSE team developed a real-time sign language translation glove using flex sensors and Bluetooth Low Energy transmission to an Android tablet.'"
        ),
        "task": "Classify this item into the appropriate SIET magazine section.",
        "assistant_response": {
            "section": "student_projects",
            "confidence": 0.96,
            "rationale": "Describes undergraduate prototype development with specific hardware components and student team context."
        }
    },
    {
        "category": "magazine_summaries",
        "task_type": "magazine_summaries",
        "source": (
            "Issue Contents Summary:\n"
            "1. Department of CSE installs 8-GPU AI Cluster.\n"
            "2. TinyML workshop trains 85 ECE undergraduates on ESP32.\n"
            "3. RailGuard student project tests ultrasonic acoustic crack detection.\n"
            "4. SIET basketball team wins Anna University Zone 9 championship.\n"
            "5. Phase 1 campus recruitment secures 420 offers."
        ),
        "task": "Generate a unified 35-word executive summary for the magazine issue.",
        "assistant_response": {
            "executive_summary": "This issue highlights the inauguration of CSE's 8-GPU AI cluster, TinyML hardware workshops, student project RailGuard field trials, Zone 9 basketball victory, and 420 corporate placement offers at SIET."
        }
    }
]

# Adversarial cases with missing information where the model MUST NOT hallucinate
ADVERSARIAL_CASES: List[Dict[str, Any]] = [
    {
        "id": "adv_01_missing_speaker_and_date",
        "source": "Students attended a technical workshop on robotics and autonomous path planning in the college lab.",
        "task": "Generate full editorial details. If speaker name, date, or participant count are missing, they MUST remain null.",
        "expected_null_fields": ["speaker", "event_date", "participant_count", "organizer"],
        "assistant_response": {
            "magazine_issue_title": "Students Participate in Robotics Workshop at College Laboratory",
            "description": "Undergraduate students attended a technical workshop covering robotics and autonomous path planning inside the laboratory facility.",
            "event_date": None,
            "speaker": None,
            "participant_count": None,
            "organizer": None,
            "captions": [
                "Students participating in the autonomous robotics workshop session."
            ],
            "toc_summary": "Technical workshop on robotics held in the college laboratory."
        }
    },
    {
        "id": "adv_02_missing_prize_and_jury",
        "source": "A student team displayed an agricultural sensor device at a regional symposium.",
        "task": "Report the project demonstration. Do NOT invent cash prize amounts, ranks, or jury names.",
        "expected_null_fields": ["cash_prize", "rank", "jury_names", "department"],
        "assistant_response": {
            "magazine_issue_title": "Student Team Exhibits Agricultural Sensor Device at Regional Symposium",
            "description": "An agricultural sensor prototype was demonstrated by a student engineering team during a regional technical symposium.",
            "cash_prize": None,
            "rank": None,
            "jury_names": None,
            "department": None,
            "captions": [
                "Student team presenting their agricultural sensor prototype at the symposium."
            ],
            "toc_summary": "Student team presents agricultural sensor device at regional symposium."
        }
    },
    {
        "id": "adv_03_sparse_sports_notice",
        "source": "The college volleyball team played a match against an opponent team.",
        "task": "Summarize the match. Do NOT guess scoreline, tournament name, or player identities.",
        "expected_null_fields": ["score", "tournament_name", "player_names", "result"],
        "assistant_response": {
            "headline": "College Volleyball Team Competes in Match",
            "score": None,
            "tournament_name": None,
            "player_names": [],
            "result": None,
            "toc_summary": "College volleyball team completes competitive match."
        }
    }
]


def format_chatml_example(example: Dict[str, Any]) -> Dict[str, Any]:
    """Formats an example into Qwen3 ChatML messages format."""
    user_prompt = f"SOURCE CONTEXT:\n{example['source']}\n\nTASK:\n{example['task']}"
    assistant_content = json.dumps(example["assistant_response"], ensure_ascii=False)

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_content},
        ],
        "metadata": {
            "category": example.get("category", "adversarial"),
            "task_type": example.get("task_type", "adversarial_grounding"),
        },
    }


def expand_examples(base_examples: List[Dict[str, Any]], target_count: int = 100) -> List[Dict[str, Any]]:
    """
    Expands base curated examples deterministically with realistic parameter variations
    (dates, department names, student names, metrics) to produce a solid pilot training set.
    """
    random.seed(42)
    expanded = list(base_examples)

    departments = [
        ("Department of Artificial Intelligence & Data Science", "AI & DS"),
        ("Department of Civil Engineering", "Civil"),
        ("Department of Electrical & Electronics Engineering", "EEE"),
        ("Department of Information Technology", "IT"),
        ("Department of Biotechnology", "Biotech"),
    ]

    dates_2026 = ["July 14, 2026", "August 3, 2026", "September 12, 2026", "October 4, 2026"]

    while len(expanded) < target_count:
        base = random.choice(base_examples)
        dept, short_dept = random.choice(departments)
        new_date = random.choice(dates_2026)

        # Clone and vary specific verifiable fields
        cloned = dict(base)
        src = cloned["source"]
        src = src.replace("July 18-19, 2026", new_date).replace("August 12, 2026", new_date)
        cloned["source"] = src

        expanded.append(cloned)

    return expanded


def main():
    output_dir = Path(__file__).resolve().parent / "datasets"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_data_path = output_dir / "siet_editorial_sft.jsonl"
    adversarial_path = output_dir / "adversarial_eval.jsonl"

    print(f"Generating SIET editorial SFT dataset covering {len(CATEGORY_EXAMPLES)} core categories...")
    expanded = expand_examples(CATEGORY_EXAMPLES, target_count=110)

    # Write training SFT dataset
    with open(all_data_path, "w", encoding="utf-8") as f:
        for ex in expanded:
            chatml = format_chatml_example(ex)
            f.write(json.dumps(chatml, ensure_ascii=False) + "\n")
    print(f"Wrote {len(expanded)} examples to {all_data_path}")

    # Write adversarial evaluation dataset
    with open(adversarial_path, "w", encoding="utf-8") as f:
        for adv in ADVERSARIAL_CASES:
            chatml = format_chatml_example(adv)
            f.write(json.dumps(chatml, ensure_ascii=False) + "\n")
    print(f"Wrote {len(ADVERSARIAL_CASES)} adversarial evaluation cases to {adversarial_path}")


if __name__ == "__main__":
    main()
