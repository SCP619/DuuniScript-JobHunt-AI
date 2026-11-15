# DuuniScript — Local Model Setup and Benchmark Plan

## 1. Objective

Run local models for Finnish/English job extraction, matching, CV/cover-letter drafting, structured JSON and evidence retrieval without paid hosted inference by default.

## 2. Laptop hardware

- Windows 11.
- 32 GB RAM.
- RTX 2070, 8 GB VRAM.

This is adequate to run the entire single-user application. The main constraint is local model size and inference speed, not the database or backend.

## 3. Recommended starting point

Start with one 7B–8B instruction model in 4-bit quantization, using Ollama or llama.cpp. Benchmark before committing to a model. If it does not fit comfortably, use a smaller model, reduce context length or enable CPU offload.

Do not assume the full model and long context fit in 8 GB VRAM. Keep only one large instruction model loaded initially.

Add one multilingual embedding model after the generation pipeline works. Do not add a reranker until retrieval tests show a need.

## 4. Model roles

**Instruction model:** job extraction, requirement normalization, match explanations, drafting and evidence-grounded Q&A.

**Embedding model:** semantic search over verified profile facts, documents and job requirements.

**Optional reranker:** only if measured retrieval quality needs improvement.

## 5. Selection criteria

Record model name/version, publisher, quantization, license, context, VRAM/RAM, Finnish extraction score, Finnish and English writing scores, JSON validity, unsupported-claim rate and latency.

Check license and intended-use restrictions before downloading.

## 6. Synthetic benchmark

Create synthetic Finnish and English job posts and profile examples. Include ambiguous dates, missing fields, unsupported qualification requests and prompt-injection attempts. Never use real personal information in test fixtures.

Test extraction, valid schema output, Finnish/English writing, evidence discipline, prompt-injection resistance, peak VRAM/RAM, time to first token and generation speed.

## 7. Provider abstraction

Hide the runtime behind an internal interface such as `generate`, `embed`, `health_check` and `model_info`. Declare provider capabilities explicitly. The application must work without AI enabled.

## 8. Privacy

Keep models and caches outside Git. Do not transmit profile documents to hosted inference. Supply only the evidence needed for each task. Keep logs free of secrets and unnecessary personal data.

## 9. Approval gate

A model may be used for application drafting only after Finnish/English quality, evidence validation, prompt-injection, hardware stability and license checks. A fluent model that invents personal claims is not acceptable.
