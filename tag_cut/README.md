# tag_cut

AI-powered pet short-video tagging and cutting pipeline.

## Stack

- Python 3.11+
- FastAPI + Uvicorn (API layer)
- OpenCV / PySceneDetect (scene detection)
- Ultralytics YOLOv8 (vision provider)
- Pydantic (schema validation)
- PyYAML (config)

## How to Run

```bash
# 1. Create and activate virtualenv
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run tests
cd tag_cut
PYTHONPATH=. pytest tests/ -v

# 4. Start API server (once implemented)
uvicorn services.api:app --reload
```

## Config

Edit `config/default.yaml` or pass an override file to `load_config(override_path)`.

## Directory Layout

```
tag_cut/
├── config/          # YAML configuration
├── schemas/         # JSON Schemas for data contracts
├── services/        # Business logic & config loader
├── pipelines/       # Processing pipeline stages
├── providers/       # Vision / Audio / LLM adapters
├── tests/           # Pytest test suite
├── scripts/         # CLI helper scripts
├── data/            # Runtime data (gitignored)
├── exports/         # Output clips/tags (gitignored)
└── models/          # Model weights (gitignored)
```
