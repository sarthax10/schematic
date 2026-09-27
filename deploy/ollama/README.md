# Schematic's Ollama on the server

Runs on your server at `~/schematic-ollama/`, separate from Antiquary's
`antiquary-ollama`. The two apps must never share one Ollama: concurrent requests on a
CPU-only instance produced truncated output in Antiquary. There is no GPU on the server;
everything runs on CPU.

- Container `schematic-ollama`, image `ollama/ollama:latest`, volume `schematic_ollama_data`
- Listens on `127.0.0.1:11435` only (not public). Reach it through an SSH tunnel.
- Capped at 6 of 8 CPU threads and 9 GB RAM; one model loaded at a time; unloads after 10 idle minutes.
- Models: `qwen2.5:7b-instruct` (writing + scene design), `nomic-embed-text` (duplicate-topic detection).

## Use it from a dev machine

```bash
ssh -N -L 11435:127.0.0.1:11435 <user>@<server>
```

Then, in another terminal:

```bash
export OLLAMA_HOST=http://127.0.0.1:11435
python -m pipeline.llm
python -m pipeline.make
```

## Recreate / update on the server

```bash
mkdir -p ~/schematic-ollama && cp docker-compose.yml ~/schematic-ollama/
cd ~/schematic-ollama && docker compose up -d
docker exec schematic-ollama ollama pull qwen2.5:7b-instruct
docker exec schematic-ollama ollama pull nomic-embed-text
```

Caveat: both Ollamas share the same 8 CPU threads. Running a Schematic generation while
Antiquary is generating will slow both; schedule them apart.
