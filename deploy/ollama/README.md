# Schematic's Ollama on the server

Runs on your server at `~/schematic-ollama/`. The server runs one
application at a time, so Schematic gets the whole machine. There is no GPU on the server;
everything runs on CPU.

- Container `schematic-ollama`, image `ollama/ollama:latest`, volume `schematic_ollama_data`
- Listens on `127.0.0.1:11435` only (not public). Reach it through an SSH tunnel.
- No CPU/memory caps (whole machine); one model loaded at a time; unloads after 30 idle minutes.
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
