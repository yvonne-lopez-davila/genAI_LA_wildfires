# LLMProxy Python SDK

Python client for the LLMProxy backend, with examples for text generation, media generation, retrieval, uploads, and model discovery.

## Install

From `py/`:

```bash
pip install .
```

## Configure

Create a `.env` file in the directory where you run Python:

```env
LLMPROXY_API_KEY=your-api-key
LLMPROXY_ENDPOINT=https://a061igc186.execute-api.us-east-1.amazonaws.com/prod
```

Important: this SDK loads `.env` from the current working directory (`Path.cwd()`), not from the package directory.

## Quickstart

```python
from llmproxy import LLMProxy

client = LLMProxy()

response = client.generate(
    model="4o-mini",
    system="Answer briefly and clearly.",
    query="Who are the Jumbos?",
    websearch=False,
    session_id="GenericSession",
    temperature=0.0,
    lastk=0,
    rag_usage=False,
)

print(response)
```

## Core Methods

### `generate(...)`

Primary LLM call. Supports text-only and media-assisted generation.

Common arguments:
- `model`: model name (for example, `4o-mini`, `gemini-2.5-flash`)
- `system`: system instruction
- `query`: user prompt
- `websearch`: whether to enable provider web search for this call (default: `False`).
Currently only `gemini-2.5-flash` and `gemini-2.5-flash-lite` support this
- `output_schema`: optional Pydantic model class for structured outputs.
Some models (e.g., Meta Llama) do not accept `output_schema`.
- `session_id`: conversation/session scope (default: `GenericSession`)
- `temperature`, `lastk`, `rag_usage`, `rag_threshold`, `rag_k`

Media arguments:
- `media=[{"id": "...", "type": "..."}]` for pre-uploaded media refs
- Supported media MIME prefixes: `image/*`, `audio/*`

### `upload_media(file_path, session_id, content_type)`

Uploads one image/audio asset and returns a reusable media reference for `generate(...)`.

### `upload_text(text, session_id, description=None, strategy="smart")`

Uploads raw text into a session so it can be retrieved later.

### `upload_file(file_path, session_id, mime_type=None, description=None, strategy="smart")`

Uploads a file (for example PDF) into a session.

### `retrieve(query, session_id, rag_threshold, rag_k)`

Retrieves relevant chunks from data previously uploaded to that `session_id`.

### `model_info()`

Returns model metadata available through the backend.

## Session and RAG Primer

- Use one `session_id` as a shared namespace for uploaded data and retrieval.
- `upload_text` / `upload_file` add data to a session.
- `retrieve` returns relevant context from that session.
- `generate(..., rag_usage=True)` asks the backend to apply RAG context for that generation call.
- You can also manually append retrieved context to your prompt (see `examples/retrieve_and_generate.py`).


## Example Scripts

Run from `py/examples` (with a valid `.env` in that directory):

```bash
python generate.py
python generate_w_websearch.py
python generate_w_media.py
python structured_outputs.py
python upload_text.py
python upload_file.py
python retrieve.py
python retrieve_and_generate.py
python model_info.py
python multi-turn_assistant.py
python webpage_extract.py
```

Suggested learning path:
1. `generate.py`
2. `upload_text.py` + `retrieve.py`
3. `retrieve_and_generate.py`
4. `generate_w_media.py`

## Return Shape and Errors

All methods return dictionaries.
- Success responses are parsed JSON from the backend.
- Failures include an `"error"` key and usually a `"status_code"` key.
