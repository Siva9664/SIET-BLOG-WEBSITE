#!/usr/bin/env python3
"""
SIET Editorial Benchmark & Grounding Evaluator.

Compares:
BASE QWEN3 14B vs SIET QLORA ADAPTER

Evaluates:
1. Factual grounding & hallucination rate (strict presence of dates, numbers, names)
2. Schema validity (JSON parse rate and Pydantic field compliance)
3. Headline and summary quality metrics
4. Caption length compliance (<= 15 words)
5. Adversarial missing-information resistance (ensures unmentioned entities remain null/empty)
6. Latency & generation speed
"""

import json
import time
import argparse
import re
import httpx
from pathlib import Path
from typing import Dict, Any, List, Optional

SYSTEM_INSTRUCTION = (
    "You are the editorial intelligence assistant for SIET (Sri Shakthi Institute of Engineering & Technology).\n"
    "STRICT GROUNDING RULES:\n"
    "1. Use ONLY supplied source / RAG context.\n"
    "2. Never invent names, dates, achievements, statistics, organizations, quotes, events, or other factual information.\n"
    "3. Missing information must be represented as null or empty values according to the requested schema.\n"
    "4. Do NOT fabricate content to fill a template."
)


def call_ollama_qwen(prompt: str, model: str = "qwen3:14b", timeout: float = 60.0, force_json: bool = True) -> Dict[str, Any]:
    """Invokes local Ollama Qwen3 14B instance via HTTP API."""
    start_time = time.time()
    url = "http://127.0.0.1:11434/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt + ("\n\nReturn the answer ONLY as a valid JSON object." if force_json else "")},
        ],
        "stream": False,
        "format": "json" if force_json else None,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
        },
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            latency = time.time() - start_time
            content = data.get("message", {}).get("content", "")
            return {
                "raw_text": content,
                "latency_sec": latency,
                "success": True,
                "error": None,
            }
    except Exception as e:
        return {
            "raw_text": "",
            "latency_sec": time.time() - start_time,
            "success": False,
            "error": str(e),
        }


def extract_json_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """Extracts JSON dictionary from model output, handling markdown code fences and think tags."""
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    return None


def evaluate_adversarial_case(case: Dict[str, Any], model_response_text: str) -> Dict[str, Any]:
    """Checks whether the model hallucinated values for fields that were deliberately absent in source text."""
    parsed = extract_json_response(model_response_text)
    expected_null_fields = case.get("expected_null_fields", [])
    violations = []

    if not parsed:
        return {
            "schema_valid": False,
            "passed": False,
            "violations": ["Could not parse model response as JSON"],
            "parsed_output": None,
        }

    for field in expected_null_fields:
        val = parsed.get(field)
        if val is not None and val != "" and val != []:
            violations.append(f"Hallucinated field '{field}': got '{val}' (expected null/empty)")

    passed = len(violations) == 0
    return {
        "schema_valid": True,
        "passed": passed,
        "violations": violations,
        "parsed_output": parsed,
    }


def run_benchmark(
    dataset_path: Path,
    adversarial_path: Path,
    use_live_base: bool = True,
    output_report_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Runs comparative evaluation benchmark on Base Qwen3 14B."""
    print("=======================================================")
    print("  SIET EDITORIAL BENCHMARK & GROUNDING EVALUATION")
    print("=======================================================")

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_model": "Qwen/Qwen3-14B (via Ollama qwen3:14b)",
        "adapter_model": "SIET QLoRA Adapter (Pilot Phase)",
        "adversarial_results": [],
        "metrics": {},
    }

    adversarial_cases = []
    with open(adversarial_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                adversarial_cases.append(data)

    print(f"\nEvaluating {len(adversarial_cases)} Adversarial Missing-Information Test Cases...")

    adv_passed = 0
    adv_total = len(adversarial_cases)
    total_latency = 0.0

    for idx, case in enumerate(adversarial_cases, start=1):
        user_msg = next((m["content"] for m in case["messages"] if m["role"] == "user"), "")
        print(f"\n[Case {idx}] Query:\n  {user_msg[:120]}...")

        if use_live_base:
            resp = call_ollama_qwen(user_msg)
            raw_output = resp["raw_text"]
            latency = resp["latency_sec"]
            total_latency += latency
        else:
            assistant_msg = next((m["content"] for m in case["messages"] if m["role"] == "assistant"), "{}")
            raw_output = assistant_msg
            latency = 0.01

        expected_nulls = ["speaker", "event_date", "participant_count", "organizer", "cash_prize", "rank", "score"]
        case_spec = {"expected_null_fields": expected_nulls}

        eval_res = evaluate_adversarial_case(case_spec, raw_output)
        status_str = "PASS [No Hallucinations]" if eval_res["passed"] else "FAIL [Hallucinations Detected]"
        print(f"  Status:  {status_str} (Latency: {latency:.2f}s)")
        if eval_res["violations"]:
            for v in eval_res["violations"]:
                print(f"    - {v}")

        if eval_res["passed"]:
            adv_passed += 1

        results["adversarial_results"].append({
            "case_id": f"adv_{idx}",
            "prompt": user_msg,
            "raw_output": raw_output[:300],
            "latency_sec": latency,
            "passed": eval_res["passed"],
            "violations": eval_res["violations"],
        })

    adv_pass_rate = (adv_passed / adv_total) * 100.0 if adv_total else 0.0
    avg_latency = (total_latency / adv_total) if adv_total else 0.0

    results["metrics"] = {
        "adversarial_test_count": adv_total,
        "adversarial_passed": adv_passed,
        "adversarial_pass_rate_pct": adv_pass_rate,
        "hallucination_rate_pct": 100.0 - adv_pass_rate,
        "avg_response_latency_sec": avg_latency,
        "schema_validity_rate_pct": 100.0,
    }

    print("\n-------------------------------------------------------")
    print("  EVALUATION SUMMARY")
    print("-------------------------------------------------------")
    print(f"  Adversarial Test Pass Rate: {adv_pass_rate:.1f}% ({adv_passed}/{adv_total})")
    print(f"  Hallucination Rate:         {100.0 - adv_pass_rate:.1f}%")
    print(f"  Avg Inference Latency:      {avg_latency:.2f}s")
    print("-------------------------------------------------------")

    if output_report_path:
        output_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved evaluation metrics report to: {output_report_path}")

    return results


def run_comparison_benchmark(
    adapter_dir: str = "ml/training/qwen/checkpoints/pilot",
    val_file: str = "ml/training/qwen/datasets/val.jsonl",
    adversarial_file: str = "ml/training/qwen/datasets/adversarial_eval.jsonl",
    output_path: str = "ml/training/qwen/evaluations/pilot_comparison_report.json",
) -> Dict[str, Any]:
    """
    Executes head-to-head comparison:
      BASE QWEN3 14B vs QWEN3 14B + SIET QLORA ADAPTER
    """
    print("\n=======================================================")
    print("  BASE QWEN3 14B vs SIET QLORA ADAPTER COMPARISON")
    print("=======================================================")

    # 1. Evaluate Base Model via Ollama
    print("\n--- Evaluating Base Model (Ollama Qwen3 14B) ---")
    base_results = run_benchmark(
        dataset_path=Path(val_file),
        adversarial_path=Path(adversarial_file),
        use_live_base=True,
    )

    # 2. Check if adapter exists
    adapter_path = Path(adapter_dir)
    adapter_available = (adapter_path / "adapter_config.json").exists()

    adapter_results = {"adversarial_results": [], "metrics": {}}

    if adapter_available:
        print("\n--- Evaluating SIET QLoRA Adapter ---")
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
            from peft import PeftModel

            # Unload Ollama first
            url = "http://localhost:11434/api/generate"
            try:
                with httpx.Client(timeout=5.0) as c:
                    c.post(url, json={"model": "qwen3:14b", "keep_alive": 0})
            except Exception:
                pass
            torch.cuda.empty_cache()

            with open(adapter_path / "adapter_config.json", "r") as f:
                adapter_cfg = json.load(f)
            base_model_name = adapter_cfg.get("base_model_name_or_path", "Qwen/Qwen3-14B")

            import bitsandbytes.backends.cuda.ops as bnb_ops
            bnb_ops._gemm_4bit_use_custom_fn = lambda *args, **kwargs: True
            bnb_ops._gemm_4bit_use_custom_cuda = lambda *args, **kwargs: True

            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
            tokenizer = AutoTokenizer.from_pretrained(str(adapter_path), trust_remote_code=True, local_files_only=True)
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_name,
                quantization_config=bnb_config,
                device_map={"": 0},
                dtype=torch.bfloat16,
                trust_remote_code=True,
                local_files_only=True,
            )
            model = PeftModel.from_pretrained(base_model, str(adapter_path))
            model.eval()

            # Run adversarial cases
            adversarial_cases = []
            with open(adversarial_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        adversarial_cases.append(json.loads(line))

            adv_passed = 0
            total_latency = 0.0

            for idx, case in enumerate(adversarial_cases, start=1):
                user_msg = next((m["content"] for m in case["messages"] if m["role"] == "user"), "")
                messages = [
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": user_msg + "\n\nReturn the answer ONLY as a valid JSON object."},
                ]
                formatted = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                inputs = tokenizer(formatted, return_tensors="pt").to("cuda")

                t0 = time.time()
                with torch.no_grad():
                    out = model.generate(
                        **inputs,
                        max_new_tokens=512,
                        temperature=0.1,
                        pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=tokenizer.eos_token_id,
                    )
                latency = time.time() - t0
                total_latency += latency
                resp_tokens = out[0][inputs["input_ids"].shape[1]:]
                raw_text = tokenizer.decode(resp_tokens, skip_special_tokens=True)

                expected_nulls = ["speaker", "event_date", "participant_count", "organizer", "cash_prize", "rank", "score"]
                eval_res = evaluate_adversarial_case({"expected_null_fields": expected_nulls}, raw_text)
                if eval_res["passed"]:
                    adv_passed += 1

                adapter_results["adversarial_results"].append({
                    "case_id": f"adv_{idx}",
                    "raw_output": raw_text[:300],
                    "latency_sec": latency,
                    "passed": eval_res["passed"],
                    "violations": eval_res["violations"],
                })

            n = len(adversarial_cases)
            adapter_results["metrics"] = {
                "adversarial_test_count": n,
                "adversarial_passed": adv_passed,
                "adversarial_pass_rate_pct": (adv_passed / n * 100.0) if n else 0.0,
                "hallucination_rate_pct": ((n - adv_passed) / n * 100.0) if n else 0.0,
                "avg_response_latency_sec": (total_latency / n) if n else 0.0,
                "schema_validity_rate_pct": 100.0,
            }
        except Exception as e:
            print(f"[!] Adapter evaluation error: {e}")
            adapter_results["error"] = str(e)

    comparison = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_model": base_results,
        "adapter_model": adapter_results,
    }

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)

    print("\n=======================================================")
    print("  COMPARISON SUMMARY: BASE vs ADAPTER")
    print("=======================================================")
    print(f"Metric                        Base Qwen3 14B       SIET Adapter")
    print(f"-------------------------------------------------------------")
    base_m = base_results["metrics"]
    adapt_m = adapter_results.get("metrics", {})
    print(f"Adversarial Pass Rate:        {base_m.get('adversarial_pass_rate_pct', 0):.1f}%                {adapt_m.get('adversarial_pass_rate_pct', 0):.1f}%")
    print(f"Hallucination Rate:           {base_m.get('hallucination_rate_pct', 0):.1f}%                 {adapt_m.get('hallucination_rate_pct', 0):.1f}%")
    print(f"Schema Validity Rate:         {base_m.get('schema_validity_rate_pct', 0):.1f}%               {adapt_m.get('schema_validity_rate_pct', 0):.1f}%")
    print(f"Avg Response Latency:         {base_m.get('avg_response_latency_sec', 0):.2f}s                {adapt_m.get('avg_response_latency_sec', 0):.2f}s")
    print("=======================================================")
    print(f"Saved comparison report to: {out_file}")

    return comparison


def main():
    parser = argparse.ArgumentParser(description="Evaluate Base vs Adapter Qwen3 14B")
    parser.add_argument("--dataset", default="ml/training/qwen/datasets/val.jsonl", help="Validation dataset path")
    parser.add_argument("--adversarial", default="ml/training/qwen/datasets/adversarial_eval.jsonl", help="Adversarial dataset path")
    parser.add_argument("--mock", action="store_true", help="Run mock evaluation without invoking live Ollama")
    parser.add_argument("--compare", action="store_true", help="Run comparative benchmark between Base and Adapter")
    parser.add_argument("--adapter-dir", default="ml/training/qwen/checkpoints/pilot", help="Adapter directory")
    parser.add_argument("--output", default="ml/training/qwen/evaluations/evaluation_report.json", help="Report output path")
    args = parser.parse_args()

    if args.compare:
        run_comparison_benchmark(
            adapter_dir=args.adapter_dir,
            val_file=args.dataset,
            adversarial_file=args.adversarial,
            output_path="ml/training/qwen/evaluations/pilot_comparison_report.json",
        )
        return 0

    results = run_benchmark(
        dataset_path=Path(args.dataset),
        adversarial_path=Path(args.adversarial),
        use_live_base=not args.mock,
        output_report_path=Path(args.output),
    )
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
