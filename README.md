# DentexAI

**Dentist-assistant AI: computer vision on dental X-rays + a retrieval-grounded clinical agent.**

Upload a panoramic or periapical radiograph. Two YOLOv8 models run over the same image — one
detects lesions, one identifies every tooth by its FDI number. Their outputs are *fused* into
clinical statements ("caries on tooth 37"), rendered as a box overlay and an odontogram, and
handed to a Claude agent that explains them — grounded in a FAISS index built from four dental
reference documents, cited passage by passage.
The project still have some issues regarding the Teeth lesion model,  the lession model sometimes failes to recognized some damages and the fdi model sometimes fails to recognize some fdi numbers mostly because of the model's regular performance. it actually comes from dataset training,  so the dataset is not perfect. 

I m thinking about traning a lesion model with a new dataset, there are good optiones over the web, but I m not sure if it will be better than the current one.

> **Not a medical device.** DentexAI is an academic showcase. Every output is a decision-support
> suggestion for a qualified clinician, never a diagnosis.

---

## How it works

```
X-ray ──┬──► lesion YOLOv8 (4 classes)  ──► boxes ──┐
        │                                            ├──► fusion ──► findings ──┐
        └──► FDI YOLOv8 (35 classes)    ──► boxes ──┘   (dedup +      "Cavities  │
                                                         containment)  on T37"   │
                                                                                 ▼
                                              FAISS + PubMedBERT ◄── tool call ── Claude agent
                                              (960 chunks, 4 PDFs)      │             │
                                                                        └── cited ────┘
                                                                            reply
```

**Fusion is the product's core idea.** Two independent CNN networks produce two unrelated box
lists; fusion is what turns them into a sentence a dentist can act on. It runs in two
order-dependent stages, each using a deliberately different metric:

1. **Dedup teeth** — "are these two boxes the same physical tooth?" → symmetric **IoU** at 0.7.
   Class-aware NMS is load-bearing (adjacent teeth genuinely abut on a panoramic, so
   class-agnostic NMS would delete real neighbours), but its consequence is that one physical
   tooth can come back with two FDI numbers. Highest score wins. Restorations are exempt — a
   crown is *supposed* to overlap its tooth.
2. **Assign lesions** — "is this lesion inside that tooth?" → asymmetric **containment**
   (intersection ÷ lesion area) at 0.15. Not IoU: a small caries fully inside a molar scores
   ~0.07 IoU purely from the size gap, so an IoU test silently drops genuine findings.
   Unattributed lesions are still returned with `tooth_fdi = null`, never dropped.

FDI numbers claimed by more than one non-overlapping box are reported in `ambiguous_fdi`
rather than guessed at.

---

## Stack

| Layer | Choice |
|---|---|
| Vision | ONNX Runtime + OpenCV over exported YOLOv8 weights — **no ultralytics at serve time** |
| Backend | FastAPI (single worker by construction: models and sessions live on `app.state`) |
| Agent | Official `anthropic` SDK, retrieval exposed as a **tool** — no LangChain |
| Retrieval | FAISS `IndexFlatIP` + PubMedBERT (`NeuML/pubmedbert-base-embeddings`), L2-normalised |
| Frontend | React 19 + TypeScript + Vite 7 + Tailwind v4, zustand, recharts, react-odontogram |
| Training | YOLOv8 in Google Colab, exported to ONNX opset 18 |

---

## Quick start

**Requirements:** Python 3.11+, Node 20+, ~4 GB RAM. No GPU needed — everything serves on CPU thanks to onnxruntime.

```bash
git clone  git@github.com:BeauBryanDev/dentex-ai.git  && cd dentex-ai

# 1. Python deps — install order matters. A plain `pip install torch` pulls ~3 GB of CUDA
#    wheels onto a CPU-only machine.
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 2. Secrets
cat > .env <<'ENV'
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-5
ENV

# Request models to repo maintainter

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
`file` (the X-ray) and optional `session_id` (to upload a new image into a running
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
`{ "message": "...", "session_id": "..." }`. Carries no image and no findings: if the session
has an analysis attached, the agent is grounded in it automatically. Returns the reply, the
`tool_calls` it made (so a clinical claim's sources are visible), `grounded_in_analysis`, and
token counts.

---

## Cost control

DentexAI runs on a personal API key, so token cost is a design constraint rather than an
afterthought. A 3-turn consultation costs **~10K tokens (~$0.05)**, where turn 2 alone once
cost 13K. Four measures, all measured rather than guessed:

- **Analysis compaction** — `prompts.compact_analysis()` strips the findings payload injected
  into the prompt from **3403 → 147 tokens (96%)**. 46% of the original was pixel coordinates,
  which Claude cannot use — it cannot see the image. The full payload still goes to the
  frontend for the overlay.
- **Prompt caching** — both system blocks carry `cache_control`; the analysis is fixed per
  session, so it's a cache read from turn 2 on. Verify with `usage.cache_read_input_tokens`.
- **Lean retrieval** — 4 hits × 600 chars instead of 6 × 1200 (**84% smaller**). Because a
  `tool_result` is resent on every later turn, `orchestrator.prune_tool_results` stubs all but
  the newest (deleting them would orphan the `tool_use` block).
- **Budgets** — `core/budget.py` enforces per-session tokens, turns per session, and a
  process-wide backstop, all checked *before* the call and all failing closed.

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

## RAG pipeline

Six independently re-runnable phases; each reads the previous phase's JSON from `rag/out/`,
so changing one stage never means re-running the chain.

```bash
python rag/phase3_chunk.py       # re-chunk only
python rag/phase6_validate.py    # the validation queries — currently 5/5
```

Design decisions worth knowing before touching it:

- **Retrieval allocates slots per `epistemic_status`**, not a global top-k. The corpus is
  lopsided — 890 of 960 chunks come from one textbook, 4 from the ISO standard — so a global
  search lets the textbook crowd out the normative standard entirely.
- **Chunking budgets real tokens, not words.** PubMedBERT has a hard 512-token window, and
  tokens/word reaches 2.15 on dense dental terminology; a 449-word chunk once produced 777
  tokens. Windows are built against a 400-token budget using the model's own tokenizer.
- **Font size is the only reliable structure signal** in the main textbook, and linearization
  destroys it — Phase 1 tags headings with sentinels so it survives into Phase 3.
- **Embeddings stay L2-normalised**; that is what makes `IndexFlatIP` behave as cosine
  similarity. FAISS holds vectors only — all text and metadata lives in the JSON sidecar,
  keyed by integer IDs that are stable across rebuilds.

The  Four PDF Documents carry on the RAG chuking pipeline are these files:

- Textbook of OPERATIVE DENTISTRY.pdf by Nisha Garg et Garg.
- FDI Policiy Statements
- iso 3950 Dentistry - Designation System for teeth and oral cavity 
- Pitts, N. B., Zero, D. T., Marsh, P. D., Ekstrand, K., Weintraub, J. A., Ramos-Gomez, F., ... Ismail, A. (2017).
Dental caries Kingś College 


---

## Evaluation

```bash
PYTHONPATH=. python3 tests/eval_rag.py   # 5 question types, incl. a must-NOT-search case
PYTHONPATH=. python3 tests/eval_dx.py    # 3 phrasings of "diagnose this"
```

These are standalone harnesses, not pytest, and not unit tests yet — they make real API calls and
load both ONNX models plus PubMedBERT, so they cost money and take ~2 minutes. Don't run them
per commit.

They wrap the retriever in a spy and assert two things per turn: that the tool was called when
it should have been (and *not* for small talk), and that **every source named in the reply was
actually in the retrieved set** — a citation naming a document that never came back is
fabricated. That second check is the one no amount of reading the reply will give you.

**Re-run them after any change to `agent/prompts.py`, `agent/tool_schema.py`, retrieval size,
or `agent_effort`.** Agent grounding is the one behaviour here that regresses silently: it has
already happened once, when loosening the system prompt to make the agent sound more confident
stopped it retrieving on diagnosis turns entirely. It answered from memory while looking
exactly as authoritative as before. Nothing failed; nothing logged.

---

## Known limitations

- **Duplicate FDI numbers on non-overlapping boxes** — 14 collisions across the sample images.
  No IoU test can detect this. An arch-ordering DP was built and removed: it assumed ≤8 teeth
  per quadrant (supernumeraries violate this), inferred order from box centre-x (transposition
  violates this), and rewrote confident labels globally. Reported via `ambiguous_fdi` rather
  than guessed at.
- **Single-worker backend by construction** — the chat session store is in-process, so sessions
  do not survive a restart and the app does not scale horizontally as written.
- **Corpus gaps** — figure captions, tables, and bibliographies are excluded by decision, so
  ~19 chunks reference a `Table N.N` that is not in the index.
- `Dockerfile` is an empty placeholder.

**Radiographic orientation matters:** quadrants 1 and 4 (the patient's right) render on the
**viewer's left**. Any code deriving side from a box x-coordinate must honour that mirror.

---

## License

See [LICENSE](LICENSE).
