# SLM Research — local model for narration → JSON structuring

> Task profile: the SLM is a **text-in / JSON-out** engine. Docling + DocLayout-YOLO
> + TableFormer already produce clean per-page text/tables, so the SLM mostly
> parses UPI/NEFT **narration strings** into a strict transaction/identifier JSON,
> plus light classification. It runs **only on the messy ~5-10%** the regex parser
> can't handle (regex-first design in `02_LLD.md §2.3`).
>
> #1 criterion: **structured-output / function-calling reliability**. Then
> instruction-following, narration parsing, and batch throughput. Long context is
> unnecessary (page-chunked input).
>
> **Status: optional, default-off toggle.** v1 parses transactions with a
> deterministic rules/regex engine and needs no LLM. The SLM is an additive
> "better parse" toggle (`structurer_slm.enabled`, LLD §2.3) that only touches
> rows the deterministic parser flagged as low-confidence. So this document is a
> *pre-researched, ready-to-enable* pick — not a v1 dependency. Don't over-invest
> here until the toggle work (Phase 5) starts.

## This machine ("here")
`RTX 4060 Laptop — 8GB VRAM · 25GB RAM · 16-core AMD · Windows 11`. → the
**"modest / 8GB GPU"** tier. Recommendations below also cover a 24GB box for when
this moves to a server.

## The decisive lever: constrained decoding
With a JSON-Schema/GBNF **grammar** (llama.cpp `--json-schema`, Ollama `format`,
or vLLM XGrammar/Outlines `guided_json`), even a 1.5–4B model emits **100%
schema-valid JSON**. So model choice is about *field accuracy* and
*instruction-following*, **not** JSON syntax reliability. Always enforce a schema;
never rely on prompt-only "return JSON".

## Ranked shortlist (HF repo IDs verified live)
| # | Model (HF repo) | Params | License | Why it fits |
|---|-----------------|--------|---------|-------------|
| 1 | **`Qwen/Qwen3-4B-Instruct-2507`** | 4.0B | Apache-2.0 | Best size/quality/tool-calling ratio; native tool-calling, BFCL-v3 ≈ **61.9**; strong table/JSON parsing. Official + `unsloth` GGUFs. **Primary pick.** |
| 2 | `Qwen/Qwen3-8B` | 8.2B | Apache-2.0 | More reasoning/classification headroom; fits a 24GB GPU; the accuracy pick with a real GPU. |
| 3 | `Qwen/Qwen3-1.7B` | 1.7B | Apache-2.0 | Tiny, fast, tool-calling capable; great CPU/8GB batch worker under grammar constraints. |
| 4 | `Qwen/Qwen2.5-7B-Instruct` | 7.6B | Apache-2.0 | Explicitly tuned for structured/tabular JSON; huge quant ecosystem; safe fallback. |
| 5 | `microsoft/Phi-4-mini-instruct` | 3.8B | MIT | Strong instruction-following, native tool-calling, clean license. Can hallucinate fn names → pair with grammar. |
| 6 | `meta-llama/Llama-3.1-8B-Instruct` | 8B | Llama-3.1 Community | First-class tool-calling; ubiquitous support; non-Qwen diversity. |
| 7 | `Salesforce/Llama-xLAM-2-8b-fc-r` | 8B | CC-BY-**NC** | Purpose-built for function-calling, SOTA-in-class on BFCL-v3. **Non-commercial** — fine for a personal tool, not a product. |
| 8 | `meta-llama/Llama-3.2-3B-Instruct` | 3B | Llama-3.2 Community | Lightweight, good CPU speed; weaker native tool-calling → grammar-constrain. |

Also-rans: `HuggingFaceTB/SmolLM2-1.7B-Instruct` (Apache-2.0 but ~27% BFCL — too
weak for reliable field extraction; only as an ultra-light draft model);
`ibm-granite/granite-3.3-8b-instruct` (Apache-2.0, clean-license 8B with
function-calling); `mistralai/Ministral-8B-Instruct-2410` (good tool-calling but
Mistral Research License = non-commercial).

**VLM option (skip Docling, end-to-end):** `Qwen/Qwen2.5-VL-7B-Instruct`
(Apache-2.0) — DocVQA 95.7, OCRBench 864; its card demos invoice/table→JSON. Use
**only** for tricky scanned/handwritten UPI exports; for clean digital statements
the Docling→text→Qwen3 path is faster and cheaper. `-3B` variant for lighter boxes.

## Structured-output / function-calling notes
- **Native tool-calling:** Qwen3 (all sizes), Qwen2.5-7B, Phi-4-mini, Llama-3.1-8B,
  Granite-3.3, xLAM all expose native tool-call templates; Qwen3 & xLAM strongest.
- **Enforce a schema always:** one transaction/identifier JSON Schema fed as the
  grammar. The model only fills fields; brackets/quotes are guaranteed by the
  decoder → a 1.7–4B model + grammar beats a 13B model without one for this task.

## Quantization per hardware tier
| Tier | Model | Quant | Bits | Footprint | Rough tok/s |
|------|-------|-------|------|-----------|-------------|
| CPU / 16-32GB, no GPU | Qwen3-1.7B or 4B-2507 | GGUF (llama.cpp) | Q4_K_M / UD-Q4_K_XL | 1.7B≈1.3GB · 4B≈2.5GB | ~10-30 (4B) · ~40-70 (1.7B) |
| **8GB GPU (this box)** | **Qwen3-4B-2507** | **GGUF Q5_K_M/Q6_K** or AWQ | 5-6 | ~2.9-3.3GB (room for KV + batch) | ~40-80 |
| 24GB GPU (4090/3090) | Qwen3-8B / Qwen2.5-7B | AWQ 4-bit (vLLM) | 4-6 | ~6-9GB weights | 1500-4000+ aggregate (batched) |
| 48GB GPU | Qwen3-8B / Qwen2.5-VL-7B | AWQ or FP8/BF16 | 4-16 | near-full precision + big batch | very high; VLM viable |

Sweet spot for this box: **GGUF Q5_K_M** (unsloth's UD-Q4_K_XL gives ~Q5 accuracy
at Q4 size). Verified quant repos: `unsloth/Qwen3-4B-Instruct-2507-GGUF`
(Q4_K_M 2.5GB … Q8_0 4.28GB). On a real GPU with throughput needs, prefer **AWQ
4-bit under vLLM**.

## Serving stack
| Stack | Best for | Structured output | Windows | Verdict |
|-------|----------|-------------------|---------|---------|
| **llama.cpp / Ollama** | CPU + small GPU, easy deploy | GBNF + `--json-schema` (excellent) | Native binaries | **Best for this box.** Ollama for convenience; raw llama.cpp for grammar + batch control. |
| vLLM | 24GB+ GPU, high batch | XGrammar/Outlines `guided_json` | Linux-first (WSL2/Docker) | Best for the GPU/server tier. |
| TGI | Server deploys | Guided/JSON grammar | Docker | Fine; vLLM usually simpler + faster here. |
| LM Studio | Desktop GUI / experiments | JSON schema via llama.cpp | First-class GUI | Great for prototyping/model comparison. |

Plan: prototype in **LM Studio** on this laptop; deploy the local tier on
**Ollama/llama.cpp** behind the `NarrationStructurer` interface; swap to **vLLM**
if/when this moves to a 24GB box — no app-code change.

## Final recommendation
| Tier | Primary | Fallback | Serving |
|------|---------|----------|---------|
| **This box (8GB)** | `Qwen/Qwen3-4B-Instruct-2507` GGUF **Q5_K_M** + GBNF grammar | `Qwen/Qwen3-1.7B` (throughput) | Ollama / llama.cpp |
| 24GB GPU | `Qwen/Qwen3-8B` AWQ-4bit + `guided_json` | `Qwen/Qwen2.5-7B-Instruct` | vLLM |
| 48GB / end-to-end | `Qwen/Qwen3-8B` (text) | `Qwen/Qwen2.5-VL-7B-Instruct` (skip Docling) | vLLM |

**Fine-tune?** Not initially. Locked JSON Schema + grammar + a few-shot prompt of
Indian-statement quirks (SBI/HDFC/ICICI narration, UPI VPA formats, DR/CR
conventions) should suffice with Qwen3-4B. Revisit a **LoRA** (500-2000 labeled
page→JSON pairs via unsloth) only if you see *systematic* field errors
(debit/credit column swaps, misparsed UPI refs) across banks. The custom
category/labeling step is the best fine-tune candidate if the taxonomy is bespoke.

## Benchmarks to cite
- **BFCL-v3** (Berkeley Function-Calling Leaderboard) — primary tool-calling metric.
  Qwen3-4B-2507 ≈ 61.9; xLAM-2-8b SOTA-in-class; SmolLM2-1.7B ≈ 27% (why sub-2B is
  risky); Ministral-8B internal FC 31.6.
- **IFEval** — instruction-following (Qwen3 / Phi-4-mini strong for size).
- **JSON-mode reliability** — ~100% syntactic validity *with* constrained decoding;
  measure **field accuracy** on your own held-out Indian-statement set instead.
- VLM (if end-to-end): Qwen2.5-VL-7B — DocVQA 95.7 · OCRBench 864 · ChartQA 87.3.

## License watch
Commercially clean: Qwen3 / Qwen2.5 (Apache-2.0), Phi-4-mini (MIT), Granite
(Apache-2.0). Custom-permissive: Gemma, Llama. **Non-commercial (personal-use
only):** xLAM-2 (CC-BY-NC), Ministral (MRL).

**Bottom line:** `Qwen/Qwen3-4B-Instruct-2507` (GGUF Q5_K_M via Ollama/llama.cpp)
with JSON-Schema-constrained decoding is the strongest, license-clean, fully-local
pick for this 8GB box; `Qwen/Qwen3-8B` (AWQ, vLLM) when it graduates to a 24GB
server. Skip fine-tuning until field-level errors demand it.

---
*Verification note: repo IDs were confirmed via direct Hugging Face model-card
fetches (the authoritative source for repo IDs/specs); BFCL/IFEval figures are as
reported on model cards and the Berkeley leaderboard and should be re-checked
against your own eval set before locking a model.*
