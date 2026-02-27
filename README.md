# 🏛️ Contract Review Agent — Phase 1

Local AI-powered contract review. Runs 100% on your machine. No cloud APIs.

## Stack
- **LLM:** Llama 3.2:3b via Ollama
- **Document Parsing:** PyMuPDF + python-docx
- **Clause Segmentation:** Rule-based + LLM-assisted
- **Output:** Markdown + JSON review reports

---

## Setup (5 minutes)

### 1. Install Ollama
```bash
# macOS
brew install ollama

# Or download from https://ollama.ai
```

### 2. Pull the model
```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text   # For Phase 2 RAG (install now)
```

### 3. Install Python dependencies
```bash
# Python 3.11+ required
pip install -r requirements.txt
```

### 4. (Optional) Install Tesseract for scanned PDFs
```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt install tesseract-ocr
```

---

## Usage

### Check everything is working
```bash
python main.py check
```

### Run demo (no contract needed)
```bash
python main.py demo
```
This creates a sample NDA with intentional issues and runs a full review.

### Review your own contract
```bash
# Basic review (outputs markdown)
python main.py review path/to/contract.pdf

# Review with JSON output too
python main.py review path/to/contract.pdf --format both

# Save report to specific folder
python main.py review path/to/contract.pdf --output reports/
```

---

## Output

Reports are saved to `data/processed/`. The markdown report includes:
- Overall risk level (HIGH / MEDIUM / LOW)
- Contract metadata (parties, dates, governing law)
- Risk summary table
- Per-clause analysis with issues and redline suggestions
- Executive summary with recommendation

---

## Project Structure

```
contract_agent/
├── main.py                     ← CLI entry point
├── .env                        ← Configuration (edit this)
├── requirements.txt
│
├── core/
│   ├── config.py               ← Settings loader
│   ├── llm.py                  ← Ollama interface
│   └── review_pipeline.py      ← Main review orchestration
│
├── ingestion/
│   ├── parser.py               ← PDF/DOCX/TXT parsing
│   └── segmenter.py            ← Clause segmentation
│
├── prompts/
│   └── review_prompts.py       ← All LLM prompts
│
├── utils/
│   └── report_exporter.py      ← Markdown/JSON export
│
└── data/
    ├── uploads/                ← Put contracts here
    ├── processed/              ← Review reports saved here
    └── knowledge_base/
        └── playbook.yaml       ← Your company's legal positions
```

---

## Configuration

Edit `.env` to change models and settings:

```env
PRIMARY_MODEL=llama3.2:3b      # Swap to qwen2.5:14b for better results
FAST_MODEL=llama3.2:3b
MAX_CHUNK_TOKENS=512
```

---

## Customize Your Playbook

Edit `data/knowledge_base/playbook.yaml` to set your company's positions on each clause type. This file is used in Phase 2 (RAG) to give the agent company-specific context.

---

## Phase Roadmap

| Phase | Status | What it adds |
|-------|--------|--------------|
| **Phase 1** | ✅ This | Document parsing, clause segmentation, LLM review |
| **Phase 2** | Next | ChromaDB RAG, knowledge base, playbook retrieval |
| **Phase 3** | Later | Contract drafting pipeline |
| **Phase 4** | Later | CLM database, Text-to-SQL queries |
| **Phase 5** | Later | Chainlit UI, LoRA fine-tuning |

---

## Upgrading the Model

When ready to test with a stronger model:
```bash
ollama pull qwen2.5:14b
```
Then in `.env`:
```env
PRIMARY_MODEL=qwen2.5:14b
```
Zero other changes needed.
