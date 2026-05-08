# Text-to-CAD AI System

AI-powered text-to-3D-CAD generation with multi-agent architecture, manufacturing optimization, and real-time collaboration.

## Features

Feature availability is formalized via code-level flags and generated into `./CAPABILITIES.md`.

See: [Capability Matrix](./CAPABILITIES.md)

## Coordinate System

```
   Z+ (Up)
   │
   │   Y+ (Back)
   │  ╱
   │ ╱
   └────── X+ (Right)
```

## Before You Begin

### Opening a terminal

All commands below are typed into a **terminal** (command-line window):

| OS | How to open |
|----|------------|
| **Windows** | Press `Win + R`, type `powershell`, press Enter — **or** search "PowerShell" in the Start menu |
| **macOS** | Press `Cmd + Space`, type `Terminal`, press Enter |
| **Linux** | Press `Ctrl + Alt + T`, or search "Terminal" in your app launcher |

### Prerequisites

You need the following tools installed before you start. Click each link for the official installer:

| Tool | Minimum version | Install guide |
|------|----------------|---------------|
| **Git** | any | https://git-scm.com/downloads |
| **Python** | 3.11+ | https://www.python.org/downloads/ |
| **Node.js** | 20+ | https://nodejs.org/ (download the LTS version) |
| **Docker Desktop** | any recent | https://www.docker.com/products/docker-desktop/ *(Option A only)* |

After installing, verify each tool by running these commands in your terminal — each should print a version number and not an error:

```bash
git --version
python --version      # or: python3 --version  on macOS/Linux
node --version
docker --version      # only needed for Option A
```

> **Windows note:** If `python` is not found, try `py --version`. During Python installation, check the box **"Add Python to PATH"**.

## Quick Start

### Step 1 — Download the project

Open a terminal, navigate to a folder where you want to store the project, then run:

```bash
git clone https://github.com/lostdogg/text-to-cad.git
cd text-to-cad
```

> **New to Git?** `git clone` downloads a copy of the project to your computer. `cd text-to-cad` moves into that folder — all following commands must be run from inside it.

### Step 2 — Choose an install method

### Option A — Docker (recommended for beginners)

Docker bundles everything into containers so you don't need to install Python or Node.js separately. Make sure **Docker Desktop is open and running** before continuing.

```bash
# 1. Copy the example environment file
cp .env.example .env          # Linux / macOS
Copy-Item .env.example .env   # Windows PowerShell

# 2. (Optional) Open .env and add API keys — skip this if you just want to try the app
nano .env          # Linux / macOS
notepad .env       # Windows
#    See the "Environment Variables" section below for details.
#    You do NOT need any API key to use the app — it works without one.

# 3. Build and start all services (first run may take a few minutes)
docker-compose up --build
```

Once you see `Application startup complete` in the terminal output:

- 🌐 **Open the app:** http://localhost:5173
- 📖 API Docs: http://localhost:8000/docs

To stop the app, press `Ctrl + C` in the terminal.

**Configure-only mode (exit semantics)**

Validate container configuration without starting the server:

```bash
# Exit 0: configuration valid
# Exit non-zero: configuration invalid/missing required values
docker compose --profile configure run --rm backend-configure
```

### Option B — Local (no Docker)

Use this if you prefer not to install Docker, or if Docker is unavailable on your machine.

**1. Set up environment variables**

You do **not** need an API key to run the app. This step is optional.

```bash
# Linux / macOS
cp .env.example .env
nano .env          # or: vim .env  /  code .env

# Windows (PowerShell)
Copy-Item .env.example .env
notepad .env
```

**2. Backend**

Open a terminal in the `text-to-cad` folder and run:

```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

> **macOS/Linux:** If `pip` is not found, try `pip3`. If `python` is not found, try `python3`.

Wait until you see `Application startup complete` before continuing.

**3. Frontend** (open a *second* terminal window, also in the `text-to-cad` folder)

```bash
cd frontend
npm install
npm run dev
```

Once you see `Local: http://localhost:5173` in the output:

- 🌐 **Open the app:** http://localhost:5173
- 📖 API Docs: http://localhost:8000/docs

To stop, press `Ctrl + C` in each terminal window.

### Environment Variables

`.env.example` ships with sensible defaults. Copy it to `.env` and uncomment / fill in the values you need:

```bash
# Linux / macOS
cp .env.example .env
nano .env

# Windows (PowerShell)
Copy-Item .env.example .env
notepad .env
```

| Variable | Default | Description |
|---|---|---|
| `MODE` | `local` | Set to `cloud` when deploying to a server |
| `HOST` | `0.0.0.0` | Interface the backend binds to |
| `PORT` | `8000` | Backend port |
| `OPENAI_API_KEY` | _(empty)_ | Optional — enables GPT-4 / GPT-4o |
| `ANTHROPIC_API_KEY` | _(empty)_ | Optional — enables Claude models |
| `GOOGLE_API_KEY` | _(empty)_ | Optional — enables Gemini models |
| `OLLAMA_BASE_URL` | _(empty)_ | Optional — enables local Ollama models |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | Comma-separated or JSON list of allowed origins |
| `MAX_WORKERS` | `4` | Async worker threads for the backend |
| `EXPORT_DIR` | `exports` | Directory where generated files are saved |

### Optional — AI NLP Providers

The system works out of the box with the built-in rule-based NLP parser. To enable a cloud AI model, uncomment and set the relevant key in `.env`:

```bash
# OpenAI (GPT-4, GPT-4o, …)
# Get your key → https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-...

# Anthropic (Claude)
# Get your key → https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=sk-ant-...

# Google AI / Gemini
# Get your key → https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=AIza...

# Ollama (local models — no key needed; install from https://ollama.com)
# Change the URL only if Ollama runs on a different host / port
OLLAMA_BASE_URL=http://localhost:11434/v1
```

> **Tip:** You can also paste your API key directly in the UI at runtime without editing `.env` or restarting the server.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/generate` | Generate CAD from text |
| GET  | `/api/generate/models` | List all models |
| WS   | `/api/collaborate/ws/{session_id}` | Real-time collaboration |
| POST | `/api/export/stl/{model_id}` | Export STL |
| POST | `/api/export/obj/{model_id}` | Export OBJ |
| POST | `/api/export/step/{model_id}` | Export STEP |
| POST | `/api/export/gcode/cnc/{model_id}` | CNC G-code |
| POST | `/api/export/gcode/3dprint/{model_id}` | 3D print G-code |
| POST | `/api/export/gcode/laser/{model_id}` | Laser G-code |
| GET  | `/api/export/report/{model_id}` | QC report |
| GET  | `/api/export/procurement/{model_id}` | Procurement specs |
| GET  | `/api/system/capabilities` | Generated capability matrix + metadata |
| GET  | `/api/health` | Health check |

## Example Prompts

```
Create a 50mm × 30mm × 10mm aluminum mounting bracket with four 5mm holes in the corners
Subtract a 5mm cylinder from the center of a 20mm cube
Make a torus with 30mm major radius and 5mm minor radius
Design a 100mm × 50mm × 3mm acrylic panel for laser cutting
```

## Running Tests

```bash
cd /path/to/repo
pip install -r requirements.txt
python -m pytest backend/tests/ -q
```

## Capability Matrix

The capability matrix is generated from code-level feature flags:

```bash
python scripts/generate_capability_matrix.py
```

Generated output: `./CAPABILITIES.md`

## Architecture

```
backend/
├── app/
│   ├── agents/          # Multi-agent system
│   │   ├── coordinator.py    # Orchestrator
│   │   ├── nlp_agent.py      # Text → GeometrySpec
│   │   ├── csg_agent.py      # GeometrySpec → Mesh
│   │   └── validation_agent.py
│   ├── cad/             # Core CAD operations
│   │   ├── csg_operations.py # Boolean ops + primitives
│   │   ├── manifold.py       # Mesh repair
│   │   └── exporter.py       # STL/OBJ/STEP/G-code
│   ├── manufacturing/   # Process optimizers
│   │   ├── cnc.py, printing_3d.py, laser_cutting.py
│   ├── models/          # Pydantic schemas
│   └── api/             # FastAPI routers
frontend/
└── src/
    ├── components/      # React components
    ├── store/           # Zustand state
    ├── api/             # API + WebSocket client
    └── types/           # TypeScript interfaces
```

## Publishing / Deployment

### 1. Prepare environment variables

Copy `.env.example` to `.env` and fill in your values before any build or push step:

```bash
# Linux / macOS
cp .env.example .env
nano .env          # set OPENAI_API_KEY, MODE=cloud, etc.

# Windows (PowerShell)
Copy-Item .env.example .env
notepad .env
```

See the [Environment Variables](#environment-variables) table above for a description of every setting.

### 2. Build and tag the Docker image

```bash
# Replace <registry> and <tag> as appropriate (e.g. docker.io/youruser/text-to-cad:1.0.0)
docker build -t <registry>/text-to-cad:<tag> .
```

### 3. Push the image to a container registry

**Docker Hub**
```bash
docker login
docker push <dockerhub-username>/text-to-cad:<tag>
```

**GitHub Container Registry (GHCR)**
```bash
echo $CR_PAT | docker login ghcr.io -u <github-username> --password-stdin
docker tag text-to-cad:<tag> ghcr.io/<github-username>/text-to-cad:<tag>
docker push ghcr.io/<github-username>/text-to-cad:<tag>
```

### 4. Build the frontend for production

```bash
cd frontend
npm install
npm run build          # outputs to frontend/dist/
```

Serve `frontend/dist/` with any static host (Nginx, Vercel, Netlify, S3 + CloudFront, etc.) or embed it in your backend Docker image.

### 5. Deploy with Docker Compose (self-hosted)

```bash
# On the target server, pull the latest images and start the stack
docker-compose pull
docker-compose up -d --build
```

Set `VITE_API_URL` and `VITE_WS_URL` in `docker-compose.yml` (or via environment) to your public backend URL before deploying.

### 6. Deploy to a cloud platform

**AWS Elastic Container Service (ECS) / Fargate**
1. Push the image to Amazon ECR: `aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com`
2. Create an ECS task definition pointing to the image.
3. Create a Fargate service; expose port 8000 via an Application Load Balancer.

**Google Cloud Run**
```bash
gcloud auth configure-docker
docker tag text-to-cad:<tag> gcr.io/<project>/text-to-cad:<tag>
docker push gcr.io/<project>/text-to-cad:<tag>
gcloud run deploy text-to-cad \
  --image gcr.io/<project>/text-to-cad:<tag> \
  --platform managed --region <region> \
  --port 8000 --allow-unauthenticated
```

**Azure Container Apps / ACI**
```bash
az acr login --name <registry>
docker tag text-to-cad:<tag> <registry>.azurecr.io/text-to-cad:<tag>
docker push <registry>.azurecr.io/text-to-cad:<tag>
az containerapp create --name text-to-cad --resource-group <rg> \
  --image <registry>.azurecr.io/text-to-cad:<tag> \
  --target-port 8000 --ingress external
```

### 7. Verify the deployment

```bash
curl https://<your-domain>/api/health
# Expected: {"status":"healthy"}
```

### 8. Semantic versioning & tagging (recommended)

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
docker build -t <registry>/text-to-cad:1.0.0 -t <registry>/text-to-cad:latest .
docker push <registry>/text-to-cad:1.0.0
docker push <registry>/text-to-cad:latest
```

## Troubleshooting

### "Port already in use" / `address already in use`
Something else is using port 8000 or 5173. Either stop that other program, or change the port:
- Backend: add `--port 8001` to the `uvicorn` command and update `PORT=8001` in `.env`.
- Frontend: `npm run dev -- --port 5174`.

### `python` / `pip` not found (Windows)
- Make sure you checked **"Add Python to PATH"** during installation. If you didn't, re-run the Python installer and enable that option.
- Try `py` instead of `python`, and `py -m pip` instead of `pip`.

### `python` / `pip` not found (macOS / Linux)
- Try `python3` and `pip3` instead.

### `npm` not found
Node.js is not installed or not on your PATH. Download and install it from https://nodejs.org/ (use the LTS version) and restart your terminal.

### `docker: command not found` / Docker not running
- Install Docker Desktop from https://www.docker.com/products/docker-desktop/
- Make sure the Docker Desktop application is **open and running** (look for the whale icon in your system tray / menu bar) before running `docker-compose`.

### `git: command not found`
Install Git from https://git-scm.com/downloads and restart your terminal.

### The app opens but AI generation doesn't work / returns a basic shape
No AI key is configured. The app uses a built-in rule-based parser by default. To enable smarter AI responses, add an API key to `.env` (see [Optional — AI NLP Providers](#optional--ai-nlp-providers) above) or paste it directly in the UI.

### Changes to `.env` are not picked up
Restart the server after editing `.env`:
- Docker: `docker-compose down && docker-compose up --build`
- Local: stop `uvicorn` with `Ctrl + C` and run it again.

## License

MIT (see `./LICENSE`)
