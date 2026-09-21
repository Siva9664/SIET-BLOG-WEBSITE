"""SigLIP Multimodal Image Intelligence Benchmark & Evaluation Suite.
Evaluates local SigLIP model performance, VRAM footprint, inference latency,
and image-text matching accuracy on a 10-category synthetic college event benchmark.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import torch
from PIL import Image

# Ensure dataset module can be imported
sys.path.insert(0, str(Path(__file__).parent))
from dataset import load_benchmark_dataset, BenchmarkItem


def audit_environment() -> Dict[str, Any]:
    """Records precise environment, hardware, and library versions."""
    import PIL
    import torchvision
    import transformers

    has_cuda = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if has_cuda else "CPU"
    total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3) if has_cuda else 0.0

    return {
        "python_version": sys.version.split()[0],
        "pytorch_version": torch.__version__,
        "cuda_available": has_cuda,
        "cuda_version": torch.version.cuda if has_cuda else None,
        "device_name": device_name,
        "total_vram_gb": round(total_vram_gb, 2),
        "torchvision_version": torchvision.__version__,
        "transformers_version": transformers.__version__,
        "pillow_version": PIL.__version__,
    }


def get_vram_usage_mb() -> Dict[str, float]:
    """Returns allocated and reserved CUDA VRAM in Megabytes."""
    if not torch.cuda.is_available():
        return {"allocated_mb": 0.0, "reserved_mb": 0.0}
    return {
        "allocated_mb": round(torch.cuda.memory_allocated(0) / (1024**2), 2),
        "reserved_mb": round(torch.cuda.memory_reserved(0) / (1024**2), 2),
    }


def extract_features(model, inputs, is_image: bool = True) -> torch.Tensor:
    """Extracts raw feature tensor whether output is a Tensor or BaseModelOutputWithPooling."""
    out = model.get_image_features(**inputs) if is_image else model.get_text_features(**inputs)
    if hasattr(out, "pooler_output") and out.pooler_output is not None:
        return out.pooler_output
    if hasattr(out, "last_hidden_state") and out.last_hidden_state is not None:
        return out.last_hidden_state[:, 0]
    return out


def run_benchmark(model_name: str = "google/siglip-base-patch16-224") -> Dict[str, Any]:
    print("=" * 75)
    print(f"SIGLIP MULTIMODAL BENCHMARK: {model_name}")
    print("=" * 75)

    env_info = audit_environment()
    print("\n[1] Environment Audit:")
    for k, v in env_info.items():
        print(f"  {k}: {v}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if device.type == "cuda" else torch.float32

    # Initial VRAM
    vram_before = get_vram_usage_mb()
    print(f"\n[2] Initial GPU VRAM: {vram_before['allocated_mb']} MB allocated, {vram_before['reserved_mb']} MB reserved")

    # Load Model & Processor
    print(f"\n[3] Loading Model & Processor '{model_name}' on {device} ({dtype})...")
    load_start = time.perf_counter()

    from transformers import AutoModel, AutoProcessor
    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name, torch_dtype=dtype).to(device)
    model.eval()

    load_duration = time.perf_counter() - load_start
    vram_after_load = get_vram_usage_mb()
    model_vram_footprint_mb = vram_after_load["allocated_mb"] - vram_before["allocated_mb"]
    print(f"  Model loaded in {load_duration:.2f}s")
    print(f"  Model VRAM footprint: ~{model_vram_footprint_mb:.1f} MB (Total allocated: {vram_after_load['allocated_mb']} MB)")

    # Parameter count
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Total parameters: {total_params / 1e6:.1f}M ({total_params:,})")

    # Task 4: Basic Inference Test
    print("\n[4] Running Basic Image-Text Semantic Similarity Test...")
    dataset_dir = Path(__file__).parent / "benchmark_images"
    dataset_items = load_benchmark_dataset(dataset_dir)

    # Basic test on technical workshop
    workshop_item = next(it for it in dataset_items if it.category_id == "technical_workshop")
    test_img = Image.open(workshop_item.image_filename).convert("RGB")

    candidate_prompts = [
        "students attending a technical workshop",
        "students receiving an award",
        "laboratory equipment demonstration",
        "cultural event",
        "faculty meeting",
    ]

    with torch.no_grad():
        prep_start = time.perf_counter()
        img_inputs = processor(images=[test_img], return_tensors="pt").to(device)
        txt_inputs = processor(text=candidate_prompts, padding="max_length", return_tensors="pt").to(device)
        prep_time = time.perf_counter() - prep_start

        # Encode image & text
        img_feats = extract_features(model, img_inputs, is_image=True)
        txt_feats = extract_features(model, txt_inputs, is_image=False)

        # Normalize
        img_feats = img_feats / img_feats.norm(dim=-1, keepdim=True)
        txt_feats = txt_feats / txt_feats.norm(dim=-1, keepdim=True)

        # Dot product cosine similarities
        sims = (img_feats @ txt_feats.T).squeeze(0).cpu().tolist()

    ranked_basic = sorted(zip(candidate_prompts, sims), key=lambda x: x[1], reverse=True)
    print(f"  Image: {workshop_item.category_name}")
    for rank, (prompt_text, score) in enumerate(ranked_basic, 1):
        marker = "✓ [TARGET]" if "workshop" in prompt_text else " "
        print(f"    Rank {rank} (score: {score:.4f}): {prompt_text} {marker}")

    # Task 5: 10-Category College Magazine Benchmark
    print("\n[5] Running 10-Category College Magazine Benchmark...")
    category_results: List[Dict[str, Any]] = []
    top1_correct = 0
    top3_correct = 0
    margins: List[float] = []

    for item in dataset_items:
        img = Image.open(item.image_filename).convert("RGB")
        with torch.no_grad():
            img_in = processor(images=[img], return_tensors="pt").to(device)
            txt_in = processor(text=item.candidate_texts, padding="max_length", return_tensors="pt").to(device)

            i_emb = extract_features(model, img_in, is_image=True)
            t_emb = extract_features(model, txt_in, is_image=False)

            i_emb = i_emb / i_emb.norm(dim=-1, keepdim=True)
            t_emb = t_emb / t_emb.norm(dim=-1, keepdim=True)

            scores = (i_emb @ t_emb.T).squeeze(0).cpu().tolist()

        # Score mapping
        scored_candidates = list(zip(item.candidate_texts, scores))
        # Ground truth is candidate_texts[0]
        gt_score = scores[0]
        distractor_scores = scores[1:]
        top_distractor_score = max(distractor_scores) if distractor_scores else 0.0
        margin = gt_score - top_distractor_score
        margins.append(margin)

        ranked = sorted(scored_candidates, key=lambda x: x[1], reverse=True)
        top1_text = ranked[0][0]
        top3_texts = [r[0] for r in ranked[:3]]

        is_top1 = (top1_text == item.ground_truth_text)
        is_top3 = (item.ground_truth_text in top3_texts)

        if is_top1:
            top1_correct += 1
        if is_top3:
            top3_correct += 1

        print(f"  • Category: {item.category_name:<30} | Top-1: {'PASS' if is_top1 else 'FAIL'} | Score: {gt_score:.4f} | Margin: {margin:+.4f}")

        category_results.append({
            "category_id": item.category_id,
            "category_name": item.category_name,
            "ground_truth_text": item.ground_truth_text,
            "ground_truth_score": round(gt_score, 4),
            "top_distractor_score": round(top_distractor_score, 4),
            "similarity_margin": round(margin, 4),
            "top1_match": is_top1,
            "top3_match": is_top3,
            "ranked_predictions": [{"text": t, "score": round(s, 4)} for t, s in ranked],
        })

    top1_accuracy = (top1_correct / len(dataset_items)) * 100.0
    top3_accuracy = (top3_correct / len(dataset_items)) * 100.0
    avg_margin = sum(margins) / len(margins) if margins else 0.0

    print("-" * 75)
    print(f"BENCHMARK SUMMARY (10 Event Categories):")
    print(f"  Top-1 Accuracy: {top1_accuracy:.1f}% ({top1_correct}/{len(dataset_items)})")
    print(f"  Top-3 Accuracy: {top3_accuracy:.1f}% ({top3_correct}/{len(dataset_items)})")
    print(f"  Average Similarity Margin: {avg_margin:+.4f}")
    print("-" * 75)

    # Task 8: Performance and Latency Scaling
    print("\n[6] Measuring Processing & Inference Latency...")
    # Single image latency (average over 10 runs)
    single_image_latencies = []
    sample_img = Image.open(dataset_items[0].image_filename).convert("RGB")

    with torch.no_grad():
        for _ in range(10):
            t0 = time.perf_counter()
            inp = processor(images=[sample_img], return_tensors="pt").to(device)
            _ = extract_features(model, inp, is_image=True)
            torch.cuda.synchronize() if device.type == "cuda" else None
            single_image_latencies.append(time.perf_counter() - t0)

    avg_single_latency_ms = (sum(single_image_latencies) / len(single_image_latencies)) * 1000.0

    # Batch of 10 images
    batch_10_images = [Image.open(it.image_filename).convert("RGB") for it in dataset_items]
    t0 = time.perf_counter()
    with torch.no_grad():
        batch_inputs = processor(images=batch_10_images, return_tensors="pt").to(device)
        batch_feats = extract_features(model, batch_inputs, is_image=True)
        torch.cuda.synchronize() if device.type == "cuda" else None
    batch_10_latency_ms = (time.perf_counter() - t0) * 1000.0
    per_image_batch10_ms = batch_10_latency_ms / 10.0

    # Peak VRAM during batch
    vram_peak = get_vram_usage_mb()

    # Extrapolations for 50 and 100
    est_batch_50_ms = per_image_batch10_ms * 50.0 * 0.9  # slight vectorization throughput gain
    est_batch_100_ms = per_image_batch10_ms * 100.0 * 0.85
    est_vram_100_mb = vram_peak["allocated_mb"] + (per_image_batch10_ms * 1.5)

    print(f"  Single image latency (1 image): {avg_single_latency_ms:.2f} ms")
    print(f"  Batch latency (10 images): {batch_10_latency_ms:.2f} ms ({per_image_batch10_ms:.2f} ms/image)")
    print(f"  [ESTIMATE] Batch latency (50 images): ~{est_batch_50_ms / 1000.0:.2f} s")
    print(f"  [ESTIMATE] Batch latency (100 images): ~{est_batch_100_ms / 1000.0:.2f} s")
    print(f"  Peak VRAM observed: {vram_peak['allocated_mb']} MB allocated, {vram_peak['reserved_mb']} MB reserved")

    final_report_data = {
        "model_name": model_name,
        "parameters_million": round(total_params / 1e6, 2),
        "environment": env_info,
        "vram_metrics": {
            "initial_allocated_mb": vram_before["allocated_mb"],
            "model_resident_mb": round(model_vram_footprint_mb, 2),
            "peak_allocated_mb": vram_peak["allocated_mb"],
            "peak_reserved_mb": vram_peak["reserved_mb"],
            "free_vram_on_card_gb": round(env_info["total_vram_gb"] - (vram_peak["allocated_mb"] / 1024), 2),
        },
        "timings": {
            "model_load_seconds": round(load_duration, 2),
            "single_image_latency_ms": round(avg_single_latency_ms, 2),
            "batch_10_latency_ms": round(batch_10_latency_ms, 2),
            "estimated_batch_50_seconds": round(est_batch_50_ms / 1000.0, 2),
            "estimated_batch_100_seconds": round(est_batch_100_ms / 1000.0, 2),
        },
        "accuracy": {
            "benchmark_sample_size": len(dataset_items),
            "top1_accuracy_percent": round(top1_accuracy, 2),
            "top3_accuracy_percent": round(top3_accuracy, 2),
            "average_similarity_margin": round(avg_margin, 4),
        },
        "category_breakdown": category_results,
    }

    # Save to disk
    out_file = Path(__file__).parent / "benchmark_results.json"
    with open(out_file, "w") as f:
        json.dump(final_report_data, f, indent=2)

    print(f"\n[7] Complete benchmark metrics saved to: {out_file}")
    return final_report_data


if __name__ == "__main__":
    model_to_test = "google/siglip-base-patch16-224"
    if len(sys.argv) > 1:
        model_to_test = sys.argv[1]
    run_benchmark(model_to_test)
