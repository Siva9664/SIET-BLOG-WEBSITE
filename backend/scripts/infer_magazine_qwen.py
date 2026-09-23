"""CLI Script: Inference on Fine-Tuned Qwen Magazine Model (Phase 9).

Run with:
    PYTHONPATH=. .venv/bin/python scripts/infer_magazine_qwen.py --adapter-dir models/siet-qwen-magazine-v1.0.0 --prompt "AI Lab robotics hackathon"
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from app.modules.datasets.qwen_inference import QwenMagazineInference


def main():
    parser = argparse.ArgumentParser(description="Run inference with Fine-Tuned Qwen Magazine model")
    parser.add_argument(
        "--adapter-dir",
        type=str,
        default="models/siet-qwen-magazine-v1.0.0",
        help="Path to fine-tuned adapter directory",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="SIET Autonomous Quadruped Robot Navigates Real-Time Unstructured Campus Terrains.",
        help="Input text for the model",
    )
    parser.add_argument(
        "--task",
        type=str,
        default="headline",
        choices=["headline", "caption", "classification", "template", "structured", "photo"],
        help="Task type to execute",
    )
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature")

    args = parser.parse_args()
    adapter_path = Path(args.adapter_dir)

    task_instructions = {
        "headline": "Generate a compelling, journalistic magazine headline (maximum 15 words) for the content below.",
        "caption": "Generate a concise, factual photograph caption (maximum 15 words) for a college magazine layout.",
        "classification": "Classify the following college content into the appropriate magazine section category. Allowed categories: introduction, project_showcase, student_achievement, faculty_achievement, events, research, photo_gallery.",
        "template": "Given the magazine content and candidate layout templates, select the most appropriate template.",
        "structured": "Convert the raw document into structured magazine content matching the official editorial schema.",
        "photo": "Select and rank the most relevant candidate photographs for the article content.",
    }

    instruction = task_instructions.get(args.task, task_instructions["headline"])

    print("================================================================")
    print("SIET Qwen Magazine Model Inference")
    print("================================================================")
    print(f"Adapter Directory : {adapter_path.resolve()}")
    print(f"Task              : {args.task}")
    print(f"Instruction       : {instruction}")
    print(f"Input Prompt      :\n{args.prompt}\n")

    engine = QwenMagazineInference(adapter_path)
    output = engine.generate(instruction, args.prompt, temperature=args.temperature)

    print("Generated Output:")
    print("----------------------------------------------------------------")
    print(output)
    print("----------------------------------------------------------------")


if __name__ == "__main__":
    main()
