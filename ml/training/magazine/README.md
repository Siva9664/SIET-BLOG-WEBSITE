# SIET AI College Magazine Training Dataset Builder

A scalable, offline dataset builder for preparing supervised fine-tuning (SFT) data for **Qwen3-14B SIET Editorial Intelligence** from raw college magazines, annual reports, and templates (PDF & DOCX).

---

## 1. Architectural Boundary & Design Principles

```
                                  RAW INPUTS
                      ┌─────────────────────────────────┐
                      │  College Magazines (PDF / DOCX) │
                      │  Annual Reports / Lab Circulars │
                      └────────────────┬────────────────┘
                                       │
                         [DocumentIngestion + Provenance]
                                       │
                                       ▼
                       PAGE TEXT, BOUNDARIES, PHOTOS
                                       │
                       [StorySegmenter + PhotoAssociator]
                                       │
                                       ▼
                   EVENT-PHOTO GROUNDED STORY UNITS
                                       │
                                       ▼
             ┌──────────────────────────────────────────────────┐
             │       Qwen3-14B Supervised Learning Scope        │
             ├──────────────────────────────────────────────────┤
             │  • Section / Category Classification             │
             │  • Publication Headline Generation               │
             │  • Grounded Summary / TOC Digests                │
             │  • Grounded Magazine Writeups & Rewriting        │
             │  • Photo Captioning (<= 15 words)                │
             │  • Keyword / Topic Tag Extraction                │
             │  • Content Length Bracket Classification         │
             │  • High-Level Layout Intent & Template Selection │
             └─────────────────────────┬────────────────────────┘
                                       │
                                       ▼ (Deterministic Contract)
             ┌──────────────────────────────────────────────────┐
             │  Deterministic Rendering Engine (React / PDF)    │
             ├──────────────────────────────────────────────────┤
             │  • Physical layout geometry                      │
             │  • Exact pixel/CSS styling                       │
             │  • Typography & margin placement                 │
             │  • Lab Admin specific template themes            │
             └──────────────────────────────────────────────────┘
```

### What Qwen3-14B Learns
1. **Editorial Intelligence**: Inspirational, professional, and grounded tone tailored for engineering faculty, students, and recruiters.
2. **Strict Grounding**: Zero hallucination. Missing dates, speakers, funding, or ranks remain `null` or empty.
3. **Event-to-Photo Association**: Photos placed at the end of each event are bound strictly to that event. Ambiguous placements are marked `uncertain`.
4. **High-Level Layout Intent**: Selecting intents (`hero_image`, `image_grid`, `two_column_article`, `photo_feature`, `achievement_feature`, `event_page`) without generating low-level CSS or coordinates.

### What Qwen3-14B Must NOT Learn
- Raw PDF coordinates or canvas transformations.
- Raw SVG, CSS, or arbitrary geometry.
- Biometric facial recognition.
- Inventing ungrounded facts to fill empty layout slots.

---

## 2. Dataset Directory Structure

The builder conforms to the following standardized layout under `ml/datasets/magazine/`:

```
ml/datasets/magazine/
├── raw/
│   ├── magazines/           # Multi-page college magazines (PDF / DOCX)
│   ├── reports/             # Annual department reports & event briefs
│   └── templates/           # Layout reference examples & Lab Admin schemas
├── processed/
│   ├── events/              # Segmented campus & symposium event JSONs
│   ├── victories/           # Hackathon, sports & competition victory JSONs
│   ├── achievements/        # Faculty grants, patents & institutional honours
│   ├── projects/            # Capstone & student innovation exhibits
│   ├── faculty/             # FDPs, publications & faculty activities
│   └── other/               # Editorials & campus general stories
├── photos/                  # Extracted embedded images named {doc_id}_p{page}_img{idx}.png
├── examples/
│   ├── editorial.jsonl      # Editorial SFT examples (headlines, TOC, writeups, tags)
│   ├── template.jsonl       # High-level template recommendation examples
│   ├── layout.jsonl         # Layout intent planning examples
│   ├── photo.jsonl          # Photo association and grounded captioning examples
│   └── admin_feedback.jsonl # Approved human editor corrections
└── final/
    ├── train.jsonl          # Clean training split (guaranteed document isolation)
    ├── validation.jsonl     # Validation split (zero source document leakage)
    └── adversarial.jsonl    # Missing-information hallucination stress test suite
```

---

## 3. Event & Photo Grouping Invariant

In SIET magazines, event photos are normally attached or grouped at the end of each individual event, victory, achievement, or story.

The builder enforces strict rules:
- **Same Page / Explicit End**: Photos appearing on the same page as a single story are bound to that story with `HIGH` confidence.
- **Caption Grounding**: Photos with embedded caption text matching story participants or headlines are mapped accordingly.
- **Ambiguity Isolation**: When multiple stories share a page and photos lack explicit captions, the association is flagged `is_uncertain: True` and `photo_confidence: "uncertain"`. The builder **never guesses** or invents cross-event links.
- **Provenance Preservation**: Every photo retains `photo_id`, `doc_id`, `page_number`, `order_on_page`, and SHA-256 hash.

---

## 4. Supported Fine-Tuning Tasks

All generated datasets adhere to the **ChatML** JSONL schema:
`{"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}], "metadata": {...}}`

| Task Name | Input Context | Target Assistant Output |
| :--- | :--- | :--- |
| `section_classification` | Source story notes | JSON `{"category": "<one_of_10_types>"}` |
| `headline_generation` | Unpolished event notes | Grounded, publication-ready headline (<= 15 words) |
| `summary_generation` | Full article body | Grounded TOC digest (<= 25 words) |
| `grounded_rewriting` | Raw notes & facts | Structured article JSON (`headline`, `body`, `date`, `people`, `organization`, `achievement_result`) |
| `caption_generation` | Story context + photo reference | Strictly grounded photo caption (<= 15 words) |
| `keyword_extraction` | Story context | Grounded topic tags directly verifiable from text |
| `content_length_classification` | Story context | Budget tier (`short`, `medium`, `feature`) |
| `template_recommendation` | Story metadata & photo count | Template ID, page type, layout intent (no pixel coordinates) |
| `layout_intent` | Story metadata & photo count | High-level layout intent (`hero_image`, `image_grid`, `two_column_article`, etc.) |
| `story_to_photos` | Story context + available photos | List of associated photos with grounding rationale |
| `adversarial_grounding` | Intentionally incomplete notes | Null/empty fields for missing information |

---

## 5. Admin Corrections Integration

Human editor feedback enters the training corpus through `admin_feedback`:

```json
{
  "feedback_id": "fb_cse_2026_01",
  "doc_id": "cse_newsletter_vol4",
  "story_id": "cse_newsletter_vol4_p2_s1",
  "ai_output": { ... },
  "admin_correction": { ... },
  "final_approved_output": { ... },
  "correction_type": "grounding_fix",
  "reason": "Removed hallucinated chief guest name not present in source note",
  "template_version": "v1.2",
  "model_version": "qwen3-14b-base",
  "approved": true,
  "is_training_eligible": true
}
```

> [!IMPORTANT]
> **Not every correction enters the dataset**. Entries are only transformed into training examples if:
> 1. `approved == true`
> 2. `is_training_eligible == true`
> 3. The output strictly passes the automated grounding auditor.

---

## 6. Strict Grounding Policy

The grounding auditor (`GroundingAuditor`) strictly verifies:
- **No invented dates or years**: Every 4-digit year in model responses must appear in the source context.
- **No invented statistics or numbers**: Participant counts, currency amounts, or percentages must match source numbers.
- **No invented people or organizations**: Names with titles (Dr., Prof., Er.) must exist verbatim in source text.
- **No invented rankings**: Claims like "First Prize" or "Gold Medal" are rejected if not in the source.
- **Missing values**: Unknown attributes must remain `null` or empty list.

---

## 7. Deterministic Deduplication & Leakage Prevention

1. **Exact Deduplication**:
   - SHA-256 hash of normalized messages JSON filters identical examples.
   - SHA-256 hash of raw source text filters duplicate articles across newsletter drafts.
2. **Perceptual Photo Deduplication**:
   - Exact SHA-256 and difference hash (dHash) detect identical and resized/cropped photos across issues.
3. **Zero Document-Level Leakage**:
   - Datasets are partitioned **by source document (`doc_id`)**, not by random example shuffling.
   - All pages and stories from `magazine_issue_2026_01.pdf` remain exclusively in `train.jsonl` OR `validation.jsonl`, never both.

---

## 8. CLI Usage

The builder is invoked as a Python module:

```bash
# Standard dataset build from raw magazine repository
./.ml-venv/bin/python -m ml.training.magazine.build_dataset \
  --input ml/datasets/magazine/raw \
  --output ml/datasets/magazine \
  --validate \
  --stats

# Dry-run inspection (processes documents and audits quality without writing final files)
./.ml-venv/bin/python -m ml.training.magazine.build_dataset \
  --input ml/datasets/magazine/raw \
  --output ml/datasets/magazine \
  --dry-run \
  --stats

# Custom validation ratio and random seed
./.ml-venv/bin/python -m ml.training.magazine.build_dataset \
  --input ml/datasets/magazine/raw \
  --output ml/datasets/magazine \
  --val-ratio 0.20 \
  --seed 42
```

### CLI Flags
- `--input <path>`: Path to raw files directory or single document (supports PDF, DOCX, TXT, MD).
- `--output <path>`: Destination dataset directory.
- `--validate`: Runs strict quality gates and grounding verification (aborts on fatal errors).
- `--stats`: Computes and displays markdown and JSON dataset summaries.
- `--dry-run`: Runs end-to-end pipeline without mutating disk files.

---

## 9. Running Tests

The test suite contains 28 comprehensive unit tests using self-contained synthetic fixtures (zero external network requests or model downloads):

```bash
./.ml-venv/bin/python -m unittest discover -s ml/training/magazine/tests -p "test_*.py" -v
```
