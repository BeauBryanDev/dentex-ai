# DentexAI

**Dentist-assistant AI: computer vision on dental X-rays plus a retrieval-grounded clinical agent.**

Upload a panoramic or periapical radiograph. Two YOLO11s models run over the same image — one
detects lesions, one identifies every tooth by its FDI number. Their outputs are *fused* into
clinical statements ("caries on tooth 37"), rendered as a box overlay and an odontogram, and
handed to a Claude agent that explains them — grounded in a FAISS index built from four dental
reference documents, cited passage by passage.

> **Not a medical device.** DentexAI is an academic showcase. Every output is a decision-support
> suggestion for a qualified clinician, never a diagnosis.

**Current accuracy caveat.** The lesion model misses genuine pathology on a non-trivial share of
images (0.503 mAP50 on the held-out test split), and the FDI model occasionally mislabels a tooth
number. Neither is a serving bug: both are dataset limits, quantified in
[Model performance](#model-performance) below. The lesion model is **at its dataset's ceiling**: 0.617 mAP50 on validation is the best result
several hyperparameter configurations have produced, so the remaining lever is a better annotated
corpus, not further tuning. Sourcing one is the highest-value improvement available to this
project.

---

## How it works

```
X-ray ──┬──► lesion YOLO11s (4 classes)  ──► boxes ──┐
        │                                             ├──► fusion ──► findings ──┐
        └──► FDI YOLO11s (35 classes)    ──► boxes ──┘   (dedup +      "Cavities  │
                                                          containment)  on T37"   │
                                                                                  ▼
                                               FAISS + PubMedBERT ◄── tool call ── Claude agent
                                               (960 chunks, 4 PDFs)      │             │
                                                                         └── cited ────┘
                                                                             reply
```

**Fusion is the product's core idea.** Two independent networks produce two unrelated box lists;
fusion is what turns them into a sentence a dentist can act on. It runs in two order-dependent
stages, each using a deliberately different metric:

1. **Dedup teeth** — "are these two boxes the same physical tooth?" → symmetric **IoU** at 0.7.
   Class-aware NMS is load-bearing (adjacent teeth genuinely abut on a panoramic, so
   class-agnostic NMS would delete real neighbours), but its consequence is that one physical
   tooth can come back with two FDI numbers. The highest score wins. Restorations are exempt — a
   crown is *supposed* to overlap its tooth.
2. **Assign lesions** — "is this lesion inside that tooth?" → asymmetric **containment**
   (intersection ÷ lesion area) at 0.15. Not IoU: a small caries fully inside a molar scores
   ~0.07 IoU purely from the size gap, so an IoU test silently drops genuine findings.
   Unattributed lesions are still returned with `tooth_fdi = null`, never dropped.

Dedup must run before assignment, or a finding is attributed to an FDI number that is about to be
discarded. FDI numbers claimed by more than one non-overlapping box are reported in
`ambiguous_fdi` rather than guessed at.

---

## Stack

| Layer | Choice |
|---|---|
| Vision | ONNX Runtime + OpenCV over exported YOLO11s weights — **no ultralytics at serve time** |
| Backend | FastAPI (single worker by construction: models and sessions live on `app.state`) |
| Agent | Official `anthropic` SDK, retrieval exposed as a **tool** — no LangChain |
| Retrieval | FAISS `IndexFlatIP` + PubMedBERT (`NeuML/pubmedbert-base-embeddings`), L2-normalised |
| Frontend | React 19 + TypeScript + Vite 7 + Tailwind v4, zustand, recharts, react-odontogram |
| Training | YOLO11s in Google Colab (NVIDIA L4), exported to ONNX |

---

## Quick start

**Requirements:** Python 3.11+, Node 20+, ~4 GB RAM. No GPU needed — everything serves on CPU
through onnxruntime.

```bash
git clone git@github.com:BeauBryanDev/dentex-ai.git && cd dentex-ai

# 1. Python dependencies — install order matters. A plain `pip install torch` pulls ~3 GB of
#    CUDA wheels onto a CPU-only machine.
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 2. Secrets
cat > .env <<'ENV'
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-5
ENV

# The .onnx weights are not distributed with the repo — request them from the maintainer.

# 3. Backend — run from the repo root; config resolves paths relative to it.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8012

# 4. Frontend, in a second shell
cd frontend && npm install && npm run dev     # http://localhost:5173
```

Port **8012** is not arbitrary — 8000–8007 are occupied on the development machine, and
`http://localhost:5173` is the only origin in `cors_allow_origins`. Changing either means
changing both.

Verify the backend came up with every model resident:

```bash
curl -s localhost:8012/health | python -m json.tool
```

Sample radiographs for manual testing live in `images2test/`.

---

## API

Three endpoints. The asymmetry between the first two is the design: `/analyze` *produces*
findings, `/chat` *consumes* them, and `session_id` is the only thing joining the two requests.

### `GET /health`
Returns `status: "ok"` once both ONNX sessions, the FAISS index and the embedding model are
loaded onto `app.state`.

### `POST /analyze` — `multipart/form-data`
`file` (the X-ray) and an optional `session_id` (to upload a new image into a running
conversation).

```jsonc
{
  "session_id": "…",
  "image_width": 2440, "image_height": 1292,
  "teeth":         [{ "fdi": 37, "box": [...], "score": 0.91 }],
  "restorations":  [{ "name": "Crown", "box": [...], "score": 0.87 }],
  "findings":      [{ "label": "Cavities", "tooth_fdi": 37, "box": [...], "score": 0.64 }],
  "ambiguous_fdi": [43],
  "summary": "compact text form — the grounding block handed to the agent"
}
```

### `POST /chat` — `application/json`
`{ "message": "...", "session_id": "..." }`. Carries no image and no findings: if the session has
an analysis attached, the agent is grounded in it automatically. Returns the reply, the
`tool_calls` it made (so the sources behind a clinical claim are visible),
`grounded_in_analysis`, and token counts.

---

## Model performance

Both detectors are YOLO11s fine-tunes trained in Colab on an NVIDIA L4, `imgsz=640`, batch 32,
AdamW with a cosine schedule and early stopping. Both export to a v8-style detection head —
`images[1,3,640,640]` → `output0[1, 4+nc, 8400]`, with **no objectness channel** — which is why a
single decoder in `utils/postprocessing.py` serves both graphs.

### FDI tooth model (`FDI_Teeth_model.onnx`) — 35 classes

32 permanent teeth (T11–T48) plus `Bridge`, `Crown`, `Implant`. Trained on 4,560 images, validated
on 175, tested on 52. Early stopping fired at epoch 49 of 74; 1.08 h wall clock.

| Split | Images | Instances | P | R | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|
| Validation (`best.pt`) | 175 | 5,274 | 0.983 | 0.990 | **0.991** | 0.792 |
| Test (`best.pt`) | 52 | 1,562 | 0.987 | 0.969 | **0.974** | 0.776 |
| Test (ONNX opset 18) | 52 | 1,562 | 0.980 | 0.967 | **0.972** | 0.780 |

The third row is the one that matters operationally: it is the exported artefact the backend
actually serves, re-validated through ONNX Runtime. Parity with the PyTorch checkpoint is within
0.002 mAP50, so the export and the letterbox/NMS/rescale reimplementation are faithful.

Per-class numbering is uniformly strong — every FDI class scores ≥ 0.968 mAP50 on the test split,
most at the 0.995 ceiling, with mAP50-95 between 0.71 and 0.87. The weak classes are the
restorations, and they are weak from support, not from difficulty: `Bridge` has **2** test
instances (0.495 mAP50) and `Crown` has 11 (0.838). Those two figures are estimated from a
handful of boxes and should not be read as stable.

### Lesion model (`lesion_yolov8small.onnx`) — 4 classes

`Cavities`, `Damage`, `Infection`, `Wisdom`. Trained on 8,006 images, validated on 997, tested on
543. Early stopping fired at epoch 31 of 61; 2.57 h wall clock. `flipud=0` is deliberate — X-ray
vertical orientation is clinically meaningful — while `fliplr` stays on.

| Split | Images | Instances | P | R | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|
| Validation | 997 | 2,524 | 0.634 | 0.613 | **0.617** | 0.283 |
| Test | 543 | 1,673 | 0.517 | 0.538 | **0.503** | 0.216 |

Per class, on the test split:

| Class | Images | Instances | P | R | mAP50 | mAP50-95 |
|---|---|---|---|---|---|---|
| Cavities | 265 | 580 | 0.651 | 0.496 | 0.550 | 0.240 |
| Damage | 281 | 896 | 0.628 | 0.595 | 0.604 | 0.222 |
| Infection | 122 | 181 | 0.436 | 0.309 | 0.275 | 0.090 |
| Wisdom | 11 | 16 | 0.352 | 0.750 | 0.584 | 0.310 |

Three things to read out of this table:

- **`Infection` is the weakest class by a wide margin** (0.275 mAP50, recall 0.309). Periapical
  radiolucency is a low-contrast, poorly bounded target, and it has the fewest annotated instances
  of the three real pathology classes. Roughly two out of three infections are missed.
- **Recall is the binding constraint overall** (0.538). The failure mode a clinician sees is a
  missed lesion, not a phantom one — which is exactly the wrong direction for a screening aid and
  the reason the disclaimer above is not boilerplate.
- **`Wisdom` is unstable across splits**: 0.941 mAP50 on validation, 0.584 on test, 0.314 on a
  third held-out split of 1,290 images. With 16 test instances, that spread is sampling noise, not
  a measured property of the model.

The gap between the validation and test splits (0.617 → 0.503 mAP50) indicates mild overfitting to
the validation distribution plus genuine annotation inconsistency in the source dataset.

**0.617 is a dataset ceiling, not an untuned model.** Several hyperparameter configurations were
tried and none beat it; the notebook preserves only the run that won. Further tuning — learning
rate, optimizer, augmentation, patience, a larger YOLO variant — is spent effort. Improving lesion
detection means training on a different, better annotated dataset, and whether any candidate
actually clears 0.617 is an open question. The FDI model, by contrast, is done.

**One discrepancy to resolve:** the FDI notebook exports at **opset 18**, the lesion notebook at
**opset 17**. Both load and validate correctly under the pinned onnxruntime, so nothing is broken,
but the two should be aligned at the next export.

A retrained model is only live once re-exported, and the `data.yaml` class order must stay
identical to the `*_class_names` lists derived in `config.py` — those lists are the index→label
mapping for raw ONNX output.

---

## RAG pipeline

The agent does not have the reference corpus in its prompt. Retrieval is exposed to Claude as a
**tool** (`search_dental_reference`), so the model decides when a claim needs a citation and pays
the token cost only on the turns that do. The corpus itself is built offline by six independently
re-runnable phases under `rag/`; each reads the previous phase's JSON from `rag/out/`, so changing
one stage never means re-running the chain.

```
Docs4RAG/*.pdf
   │
   ├─ phase0_audit / phase0_probes   measurement only, writes nothing
   ├─ phase1_extract  ──► phase1_extracted.json   PDF → text, headings tagged @@H1@@/@@H2@@
   ├─ phase2_clean    ──► phase2_cleaned.json     unwrap lines, strip headers/watermarks
   ├─ phase3_chunk    ──► phase3_chunks.json      960 token-budgeted chunks + metadata
   ├─ phase4_embed_index ──► dentex.faiss + chunk_metadata.json
   ├─ retrieve.py                                 the one retriever, shared CLI + backend
   └─ phase6_validate                             the §11 validation queries — currently 5/5
```

```bash
python rag/phase3_chunk.py       # re-chunk only
python rag/phase6_validate.py    # validate
```

### The corpus

Four documents, ~960 chunks. Filenames are load-bearing: they are referenced literally in
`Dentex_RAG.md` §2 and stored in every chunk's `source_file` metadata.

| Document | Role | `epistemic_status` |
|---|---|---|
| *Textbook of Operative Dentistry*, Garg & Garg, 3rd ed. | Clinical practice, instructional | `educational_textbook` |
| Pitts, Zero, Marsh, Ekstrand, Weintraub, Ramos-Gomez, … Ismail (2017), *Dental caries* (King's College) | Peer-reviewed review | `peer_reviewed_research` |
| FDI policy statements | Professional position | `policy_position` |
| ISO 3950 — *Dentistry: designation system for teeth and areas of the oral cavity* | Normative on numbering | `normative_standard` |

### Why each stage is the way it is

- **Retrieval allocates slots per `epistemic_status`, not a global top-k.** The corpus is
  lopsided — 890 of 960 chunks come from the Garg textbook, 4 from the ISO standard — so a global
  nearest-neighbour search lets the textbook crowd out the normative standard entirely. Slot
  allocation guarantees the standard is reachable for the questions it actually governs.
- **Chunking budgets real tokens, not words.** PubMedBERT has a hard 512-token window, and the
  tokens-per-word ratio reaches 2.15 on dense dental terminology (a 449-word chunk once produced
  777 tokens). Phase 3 builds windows against a 400-token budget using the model's own tokenizer.
  A word-based cap silently truncates embeddings and must never be reintroduced.
- **Font size is the only reliable structure signal in the Garg textbook**, and linearization
  destroys it. Phase 1 therefore tags headings with `@@H1@@`/`@@H2@@` sentinels while the size
  information still exists, and Phase 3 consumes them. Measured bands: 9.5 pt body, 11 pt heading,
  9 pt running header, 12 pt page number, ≤ 8.5 pt captions and table cells. Captions and tables
  are cut **by region before linearization**, never by regex afterwards, or their fragments bleed
  into adjacent prose.
- **The ISO watermark is horizontal**, so rotation-based filtering does not catch it. It is removed
  by exact full-line cross-page frequency matching — exact, never substring, because the watermark
  line `ISO 3950:2009` is a strict prefix of the genuine running header `ISO 3950:2009(E)`.
- **Embeddings stay L2-normalised.** That is what makes FAISS `IndexFlatIP` behave as cosine
  similarity. FAISS holds vectors only; all text and metadata lives in the `chunk_metadata.json`
  sidecar, keyed by integer IDs taken from position in a `chunk_id`-sorted list, so the IDs are
  stable across rebuilds.
- **There is exactly one retriever**, `rag/retrieve.py`, shared by the CLI and the backend. An
  `app/rag/` serving copy was tried and deleted: two copies of the slot-allocation logic is
  precisely the thing that drifts. `Retriever(out_dir=...)` loads from disk for the CLI;
  `Retriever(index=, meta=, model=)` reuses the artefacts `core/lifespan.py` has already loaded,
  since the default constructor would pull PubMedBERT off disk on every request.

Two artefact copies exist on purpose: the CLI defaults to `rag/out/`, the backend reads
`RAG_STORE/` through settings. **Keep them in sync when the index is rebuilt** — copy
`dentex.faiss` and `chunk_metadata.json` across.

### Excluded from the index, by decision

Figure captions, tables, the per-chapter `BIBLIOGRAPHY` blocks and index of the Garg textbook, the
reference section of the caries paper, and ISO front matter. Accepted consequences: ~19 chunks
cite a `Table N.N` whose table is not indexed; `loadbearing` lost a hyphen with no corpus evidence
either way; the FDI publication date (2019) comes from the original filename rather than the
document body; and the front-matter chunk of `Dental_Caries.pdf` is still indexed.

---

## Cost control

DentexAI runs on a personal API key, so token cost is a design constraint rather than an
afterthought. A 3-turn consultation costs **~10K tokens (~$0.05)**, where turn 2 alone once cost
13K. Four measures, all measured rather than guessed:

- **Analysis compaction** — `prompts.compact_analysis()` strips the findings payload injected into
  the prompt from **3,403 → 147 tokens (96%)**. 46% of the original was pixel coordinates, which
  Claude cannot use — it cannot see the image. The full payload still goes to the frontend for the
  overlay.
- **Prompt caching** — both system blocks carry `cache_control`; the analysis is fixed per session,
  so it is a cache read from turn 2 on. Verify with `usage.cache_read_input_tokens`, which
  `log_agent_usage` prints on every call.
- **Lean retrieval** — 4 hits × 600 chars instead of 6 × 1,200 (**84% smaller**). Because a
  `tool_result` is resent on every later turn, `orchestrator.prune_tool_results` stubs all but the
  newest (deleting them would orphan the `tool_use` block and the API would reject the request).
- **Budgets** — `core/budget.py` enforces per-session tokens, turns per session, and a process-wide
  backstop, all checked *before* the call and all failing closed.

---

## Repo layout

```
app/          FastAPI backend — routers → services → utils, schemas for the wire format
  core/       config, lifespan (every expensive object loaded once), budget, session store
  services/   detector.py (ONNX inference), fusion.py (the core idea), analysis_service.py
  agent/      orchestrator, prompts, tool schema
  utils/      letterboxing, NMS, coordinate rescaling, CLASS_MAP.json, tooth geometry
rag/          six-phase pipeline: extract → clean → chunk → embed/index → retrieve → validate
RAG_STORE/    the index the backend serves (dentex.faiss + chunk_metadata.json)
Docs4RAG/     source corpus, 4 PDFs — filenames are load-bearing metadata
models/       Colab training notebooks + the two exported .onnx weights
frontend/     React app — upload, box overlay, odontogram, findings table, chat panel
tests/        eval_rag.py / eval_dx.py — grounding harnesses, not unit tests
```

---

## Evaluation

```bash
PYTHONPATH=. python3 tests/eval_rag.py   # 5 question types, incl. a must-NOT-search case
PYTHONPATH=. python3 tests/eval_dx.py    # 3 phrasings of "diagnose this"
```

These are standalone harnesses, not pytest and not unit tests. They make real API calls and load
both ONNX models plus PubMedBERT, so they cost money and take ~2 minutes. Do not run them per
commit.

They wrap the retriever in a spy and assert two things per turn: that the tool was called when it
should have been (and *not* for small talk), and that **every source named in the reply was
actually in the retrieved set** — a citation naming a document that never came back is fabricated.
That second check is the one no amount of reading the reply will give you.

**Re-run them after any change to `agent/prompts.py`, `agent/tool_schema.py`, retrieval size, or
`agent_effort`.** Agent grounding is the one behaviour here that regresses silently. It has already
happened once: loosening the system prompt to make the agent sound more confident stopped it
retrieving on diagnosis turns entirely, so it answered management questions from memory while
looking exactly as authoritative as before. Nothing failed; nothing logged.

---

## Known limitations

- **Lesion recall** — 0.538 on the test split, and 0.309 for `Infection`. Missed pathology is the
  dominant failure mode, and it is capped by the training data rather than by tuning. See
  [Model performance](#model-performance).
- **Duplicate FDI numbers on non-overlapping boxes** — 14 collisions across the sample images. No
  IoU test can detect this. An arch-ordering dynamic program was built and removed: it assumed ≤ 8
  teeth per quadrant (supernumeraries violate this), inferred order from box centre-x
  (transposition violates this), and rewrote confident labels globally, so one bad box could shift
  a whole quadrant. Reported through `ambiguous_fdi` rather than guessed at.
- **Single-worker backend by construction** — the chat session store is in-process, so sessions do
  not survive a restart and the app does not scale horizontally as written.
- **Corpus gaps** — figure captions, tables and bibliographies are excluded by decision, so ~19
  chunks reference a `Table N.N` that is not in the index.
- **`Dockerfile` is an empty placeholder.**

**Radiographic orientation matters:** quadrants 1 and 4 (the patient's right) render on the
**viewer's left**. Any code deriving side from a box x-coordinate must honour that mirror.

---

## License

See [LICENSE](LICENSE).
