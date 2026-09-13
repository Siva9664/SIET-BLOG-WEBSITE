"""Benchmark dataset generator for SigLIP multimodal image evaluation.
Uses Pillow to create synthetic, public-safe benchmark images across 10 college event categories.
Zero confidential college data is used.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFont


@dataclass
class BenchmarkItem:
    category_id: str
    category_name: str
    image_filename: str
    ground_truth_text: str
    candidate_texts: List[str]
    distractor_texts: List[str]


# 10 College Magazine Event Categories
CATEGORIES: List[Dict[str, str]] = [
    {
        "id": "technical_workshop",
        "name": "Technical Workshop",
        "ground_truth": "engineering students participating in a hands-on technical workshop with electronic hardware",
        "distractors": [
            "students receiving an award trophy on stage",
            "annual sports track athletic meet",
            "classical cultural dance performance",
            "faculty administrative senate meeting",
        ],
    },
    {
        "id": "laboratory_activity",
        "name": "Laboratory Activity",
        "ground_truth": "students conducting scientific experiments with chemical laboratory glassware and reagents",
        "distractors": [
            "guest lecture delivered in large seminar hall",
            "outdoor campus gathering on open college quad lawn",
            "sports football tournament on campus ground",
            "cultural music performance in college auditorium",
        ],
    },
    {
        "id": "project_demonstration",
        "name": "Student Project Demonstration",
        "ground_truth": "students demonstrating an engineering project prototype with poster presentation boards",
        "distractors": [
            "faculty academic meeting in boardroom",
            "outdoor sports athletics running event",
            "group photo of graduates in academic regalia",
            "cultural dance drama in auditorium",
        ],
    },
    {
        "id": "award_ceremony",
        "name": "Award Ceremony",
        "ground_truth": "students receiving gold medals and achievement award certificates on stage podium",
        "distractors": [
            "students soldering circuit boards in technical workshop",
            "laboratory chemistry experiment with test tubes",
            "students relaxing outdoors on campus green lawn",
            "faculty curriculum review committee meeting",
        ],
    },
    {
        "id": "faculty_event",
        "name": "Faculty Event",
        "ground_truth": "college faculty members and department heads meeting in formal conference room",
        "distractors": [
            "college rock music concert with colorful stage lights",
            "student track and field running competition",
            "hands-on soldering and microcontroller workshop",
            "chemistry laboratory titration experiment",
        ],
    },
    {
        "id": "cultural_event",
        "name": "Cultural Event",
        "ground_truth": "students performing colorful traditional dance and music on auditorium stage",
        "distractors": [
            "students working on oscilloscope in electronics lab",
            "executive faculty senate committee meeting",
            "hardware prototype demonstration for judges",
            "students running 100m sprint race on sports track",
        ],
    },
    {
        "id": "sports_event",
        "name": "Sports Event",
        "ground_truth": "student athletes competing in outdoor track and field running race on sports field",
        "distractors": [
            "keynote speaker addressing audience at academic lecture",
            "students conducting precision microscopy in laboratory",
            "award felicitation ceremony with mementos and trophies",
            "formal faculty staff meeting around conference table",
        ],
    },
    {
        "id": "group_photograph",
        "name": "Group Photograph",
        "ground_truth": "formal group photograph of event participants and faculty mentors posed together",
        "distractors": [
            "single student working alone with soldering iron",
            "chemical flask experiment in fume hood",
            "sprinters racing across sports athletic finish line",
            "empty auditorium stage before guest lecture",
        ],
    },
    {
        "id": "guest_lecture",
        "name": "Guest Lecture",
        "ground_truth": "distinguished keynote speaker delivering an expert guest lecture from auditorium podium",
        "distractors": [
            "students playing competitive basketball match on sports court",
            "traditional cultural folk dance performance",
            "chemistry laboratory titration with pipettes and beakers",
            "hands-on electronics PCB assembly workshop",
        ],
    },
    {
        "id": "campus_activity",
        "name": "Campus Activity",
        "ground_truth": "students gathered outdoors enjoying campus green lawns and college academic walkways",
        "distractors": [
            "formal faculty meeting in closed boardroom",
            "hardware demonstration with FPGA odometry board",
            "gold medal award presentation ceremony",
            "guest lecture speaker at auditorium podium",
        ],
    },
]


def generate_synthetic_image(category_id: str, output_path: Path, width: int = 448, height: int = 448) -> Path:
    """
    Renders a clean, structured synthetic benchmark image with distinct visual primitives,
    color palettes, icons, and text labels corresponding to each category.
    """
    img = Image.new("RGB", (width, height), color=(240, 240, 245))
    draw = ImageDraw.Draw(img)

    # Color themes and compositional primitives per category
    palettes = {
        "technical_workshop": {"bg": (25, 35, 60), "fg": (0, 210, 255), "accent": (255, 180, 0)},
        "laboratory_activity": {"bg": (20, 50, 40), "fg": (50, 255, 180), "accent": (255, 100, 100)},
        "project_demonstration": {"bg": (45, 30, 60), "fg": (200, 120, 255), "accent": (255, 230, 80)},
        "award_ceremony": {"bg": (60, 20, 30), "fg": (255, 215, 0), "accent": (255, 255, 255)},
        "faculty_event": {"bg": (35, 45, 55), "fg": (180, 200, 220), "accent": (100, 160, 230)},
        "cultural_event": {"bg": (70, 20, 60), "fg": (255, 120, 200), "accent": (255, 220, 0)},
        "sports_event": {"bg": (30, 70, 30), "fg": (150, 255, 100), "accent": (255, 255, 255)},
        "group_photograph": {"bg": (40, 40, 50), "fg": (220, 220, 230), "accent": (120, 180, 255)},
        "guest_lecture": {"bg": (30, 35, 50), "fg": (255, 240, 180), "accent": (0, 180, 255)},
        "campus_activity": {"bg": (40, 65, 45), "fg": (180, 255, 160), "accent": (255, 200, 100)},
    }

    style = palettes.get(category_id, {"bg": (30, 30, 30), "fg": (200, 200, 200), "accent": (255, 255, 255)})

    # 1. Background gradient / fill
    draw.rectangle([0, 0, width, height], fill=style["bg"])

    # 2. Category-specific geometric visual signatures
    if category_id == "technical_workshop":
        # Circuit board traces & chip
        draw.rectangle([120, 120, 328, 328], outline=style["fg"], width=4, fill=(15, 20, 40))
        draw.rectangle([170, 170, 278, 278], fill=style["accent"])
        for i in range(140, 310, 25):
            draw.line([i, 60, i, 120], fill=style["fg"], width=3)
            draw.line([i, 328, i, 388], fill=style["fg"], width=3)
            draw.line([60, i, 120, i], fill=style["fg"], width=3)
            draw.line([328, i, 388, i], fill=style["fg"], width=3)
    elif category_id == "laboratory_activity":
        # Flask / chemical beaker silhouette
        draw.polygon([(224, 80), (200, 180), (120, 360), (328, 360), (248, 180)], outline=style["fg"], width=4, fill=(10, 30, 25))
        draw.polygon([(140, 350), (308, 350), (268, 260), (180, 260)], fill=style["accent"])
        for bub in [(210, 230, 12), (235, 210, 8), (200, 190, 10)]:
            draw.ellipse([bub[0]-bub[2], bub[1]-bub[2], bub[0]+bub[2], bub[1]+bub[2]], outline=style["fg"], width=2)
    elif category_id == "project_demonstration":
        # Presentation stand / poster board and robotic arm prototype
        draw.rectangle([80, 80, 368, 280], outline=style["fg"], width=4, fill=(30, 20, 45))
        draw.rectangle([110, 110, 220, 250], fill=(50, 35, 75))
        draw.rectangle([240, 110, 340, 190], fill=style["accent"])
        draw.line([224, 280, 224, 400], fill=style["fg"], width=6)
        draw.line([140, 400, 308, 400], fill=style["fg"], width=6)
    elif category_id == "award_ceremony":
        # Stage podium, trophy cup, and medal
        draw.rectangle([60, 280, 388, 400], fill=(80, 25, 35), outline=style["fg"], width=3)
        # Trophy cup
        draw.polygon([(170, 120), (278, 120), (258, 220), (190, 220)], fill=style["fg"], outline=(255, 255, 255), width=2)
        draw.rectangle([214, 220, 234, 260], fill=style["fg"])
        draw.rectangle([184, 260, 264, 280], fill=style["fg"])
        draw.arc([140, 130, 200, 200], start=90, end=270, fill=style["fg"], width=4)
        draw.arc([248, 130, 308, 200], start=270, end=90, fill=style["fg"], width=4)
    elif category_id == "faculty_event":
        # Boardroom meeting table with seated figure silhouettes
        draw.ellipse([80, 200, 368, 360], fill=(25, 30, 40), outline=style["fg"], width=3)
        for x in [120, 180, 240, 300]:
            draw.ellipse([x-15, 140, x+15, 170], fill=style["accent"])
            draw.arc([x-25, 170, x+25, 210], start=0, end=180, fill=style["accent"], width=4)
    elif category_id == "cultural_event":
        # Spotlight beams and musical notation
        draw.polygon([(0, 0), (140, 448), (280, 448)], fill=(120, 30, 100, 100))
        draw.polygon([(448, 0), (308, 448), (168, 448)], fill=(120, 100, 30, 100))
        draw.ellipse([180, 260, 268, 348], fill=style["fg"])
        draw.line([258, 260, 258, 140], fill=style["fg"], width=6)
        draw.ellipse([240, 120, 290, 160], fill=style["accent"])
    elif category_id == "sports_event":
        # Running track lanes and stadium hurdle
        for y in range(120, 440, 45):
            draw.line([0, y, 448, y], fill=style["fg"], width=3)
        draw.rectangle([180, 220, 268, 240], fill=style["accent"])
        draw.line([190, 240, 190, 320], fill=style["accent"], width=4)
        draw.line([258, 240, 258, 320], fill=style["accent"], width=4)
    elif category_id == "group_photograph":
        # Multi-person lineup (heads and shoulders row)
        for row_y, offset in [(150, 0), (220, 25)]:
            for x in range(60 + offset, 400, 55):
                draw.ellipse([x-14, row_y, x+14, row_y+28], fill=style["accent"])
                draw.arc([x-22, row_y+28, x+22, row_y+65], start=0, end=180, fill=style["fg"], width=3)
    elif category_id == "guest_lecture":
        # Auditorium podium with microphone and seated audience
        draw.rectangle([180, 180, 268, 340], fill=(20, 25, 35), outline=style["fg"], width=3)
        draw.line([214, 180, 224, 140], fill=style["accent"], width=3)
        draw.ellipse([220, 134, 230, 144], fill=style["accent"])
        for y in range(360, 440, 25):
            draw.line([40, y, 408, y], fill=style["fg"], width=2)
    elif category_id == "campus_activity":
        # Outdoor academic lawn with trees and campus pathway
        draw.arc([40, 160, 220, 340], start=0, end=360, fill=style["fg"], width=6)
        draw.polygon([(130, 300), (110, 448), (150, 448)], fill=(120, 80, 40))
        draw.polygon([(0, 448), (200, 320), (248, 320), (448, 448)], fill=(150, 140, 120))

    # 3. Text label overlay (Category title watermark)
    draw.rectangle([10, 10, width - 10, 50], fill=(0, 0, 0, 180))
    draw.text((20, 20), f"[BENCHMARK] {category_id.upper()}", fill=style["accent"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="JPEG", quality=95)
    return output_path


def load_benchmark_dataset(dataset_dir: Path) -> List[BenchmarkItem]:
    """Generates synthetic dataset on disk if not already present and returns items."""
    dataset_dir.mkdir(parents=True, exist_ok=True)
    items: List[BenchmarkItem] = []

    for cat in CATEGORIES:
        cid = cat["id"]
        img_path = dataset_dir / f"{cid}.jpg"
        if not img_path.exists():
            generate_synthetic_image(cid, img_path)

        candidates = [cat["ground_truth"]] + cat["distractors"]
        items.append(
            BenchmarkItem(
                category_id=cid,
                category_name=cat["name"],
                image_filename=str(img_path),
                ground_truth_text=cat["ground_truth"],
                candidate_texts=candidates,
                distractor_texts=cat["distractors"],
            )
        )

    return items
