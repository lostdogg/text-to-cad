# Text-to-CAD AI System

AI-powered text-to-3D-CAD generation with multi-agent architecture, manufacturing optimization, and real-time collaboration.

## Features

- **Natural Language → 3D CAD**: Describe any part in plain English; rule-based NLP (+ optional GPT-4) converts it to geometry
- **CSG Boolean Operations**: Union, intersection, subtraction across primitives (box, cylinder, sphere, cone, torus)
- **Manifold Resolution**: Automatic mesh repair (holes, normals, degenerate faces)
- **Multi-Agent Architecture**: NLPAgent → CSGAgent → ValidationAgent in parallel via asyncio
- **Distributed Manufacturing Optimization**:
  - 3-axis CNC: toolpath generation, fixturing, accessibility checks
  - 3D Printing (FDM/SLA/SLS): orientation, supports, layer analysis
  - Laser Cutting: profile extraction, nesting, kerf compensation
- **Real-time Collaboration**: WebSocket sessions with spatial cursors and chat
- **Manufacturing-Ready Validation**: Wall thickness, overhang angles, aspect ratios per process
- **Measurement Tools**: Click-to-measure in 3D viewport (caliper-compatible output in mm)
- **Export**: STL, OBJ, STEP, CNC G-code, 3D print G-code, Laser G-code
- **QC Reports & Procurement**: JSON reports, McMaster-Carr / DigiKey part numbers
- **Cloud & Local**: Docker for cloud, or run directly on Windows/Linux

## Coordinate System

```
   Z+ (Up)
   │
   │   Y+ (Back)
   │  ╱
   │ ╱
   └────── X+ (Right)
```

## Quick Start

### Option A — Docker (recommended)

```bash
docker-compose up --build
```

- Backend API: http://localhost:8000
- Frontend:    http://localhost:5173
- API Docs:    http://localhost:8000/docs

### Option B — Local (Windows / Linux)

**Backend:**
```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Optional — OpenAI GPT-4 NLP

Add to `.env`:
```
OPENAI_API_KEY=sk-...
```

Without it the system uses the built-in rule-based NLP parser.

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
pytest backend/tests/ -v
```

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
cp .env.example .env
# edit .env — set OPENAI_API_KEY, MODE=cloud, etc.
```

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

## License

MIT
