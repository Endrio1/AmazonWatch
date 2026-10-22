# AmazonWatch 🛰️🔥

Sistema de monitoramento em tempo quase real que correlaciona **nuvens de fumaça** e os **incêndios de onde elas se originaram** na **Amazônia Legal**, utilizando dados do **BDQueimadas/INPE** e **NOAA GOES-19**.

Endrio Agassi Bernardes De Almeida
---

## 🧭 Metodologia e Fontes de Dados

| Camada | Fonte | Produto / Formato | Frequência |
|---|---|---|---|
| **Focos de Incêndio** | INPE / BDQueimadas | CSV de 10 minutos (`lat, lon, satelite, data`) | 10 min |
| **Plumas de Fumaça** | NOAA GOES-19 | S3 público: `ABI-L2-ADPF` (Aerosol Detection Product) | 10 min |
| **Imagem de Fundo** | INPE / CPTEC (DSAT) | Mosaico True Color + IR 10.35 µm reprojetado para WGS-84 | 10 min |
| **Limite Territorial** | IBGE (2022) | Geometria simplificada da Amazônia Legal | Estático |

### Algoritmo de Detecção e Associação Pluma ➔ Foco

1. **Extração de Plumas (NOAA ADP):**
   - Recorta os dados geoestacionários na extensão da Amazônia Legal.
   - Aplica a máscara `Smoke == 1` com filtro de qualidade (bits 2–3 do `DQF`).
   - Aplica fechamento morfológico para unir fragmentos contíguos e elimina ruídos menores que 10 pixels.
   - Poligoniza o raster (`rasterio.features.shapes`) e reprojeta os polígonos para coordenadas geográficas WGS-84 (`EPSG:4326`).
   - Calcula a área geodésica em km² de cada pluma.

2. **Associação e Identificação da Origem:**
   - Para cada pluma em um instante $t$, busca focos detectados na janela temporal $[t - 6\text{h}, t + 10\text{min}]$ dentro ou a até 25 km da borda da pluma (`ST_DWithin` geográfico no PostGIS).
   - Agrupa os focos espacialmente com `ST_ClusterDBSCAN` para consolidar detecções repetidas do mesmo incêndio.
   - Calcula um score por decaimento exponencial de distância e tempo:
     $$\text{Score} = \exp\left(-\frac{d}{D_0}\right) \cdot \exp\left(-\frac{\Delta t}{T_0}\right)$$
   - O grupo de maior densidade e score combinado é classificado como a **origem provável**, criando uma linha vetorial que liga o incêndio ao centro de massa da fumaça.

---

## 🏗️ Arquitetura do Sistema

```
AmazonWatch/
├── docker-compose.yml          # Orquestração (PostGIS, API, Worker, Frontend)
├── .env.example                # Variáveis de ambiente
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/                # Migrações PostGIS (SRID 4326)
│   ├── app/
│   │   ├── main.py             # Aplicação FastAPI
│   │   ├── config.py           # Configurações Pydantic
│   │   ├── models.py           # Modelos GeoAlchemy2 / SQLAlchemy
│   │   ├── schemas.py          # Schemas Pydantic / GeoJSON
│   │   ├── region.py           # Limite da Amazônia Legal (IBGE)
│   │   ├── worker.py           # Worker agendado (APScheduler)
│   │   ├── api/                # Endpoints REST (/hotspots, /plumes, /frames, /stats, /health)
│   │   ├── ingest/             # bdqueimadas.py, goes_adp.py, dsat_frames.py
│   │   └── processing/         # smoke.py, association.py, geos.py
│   └── tests/                  # Testes unitários pytest
└── frontend/
    ├── Dockerfile
    ├── nginx.conf              # Nginx com proxy reverso para API e mídia
    ├── src/
    │   ├── App.tsx             # Aplicação React
    │   ├── api.ts              # Cliente REST
    │   ├── types.ts            # Tipagens TypeScript
    │   ├── index.css           # Design system escuro (Glassmorphism)
    │   └── components/
    │       ├── MapView.tsx         # Mapa interativo Leaflet
    │       ├── Header.tsx          # Métricas em tempo real e toggles
    │       ├── TimelineDeck.tsx    # Controle temporal com player
    │       ├── PlumeInspector.tsx  # Painel de auditoria da pluma
    │       └── Legend.tsx          # Legenda das camadas
```

---

## 🚀 Como Executar

### Opção 1: Via Docker Compose (Recomendado)

Suba toda a infraestrutura com um único comando:

```bash
docker compose up --build
```

O compose inicializará:
- **Frontend:** http://localhost:3000
- **FastAPI / Swagger:** http://localhost:8000/docs
- **PostGIS:** `localhost:5433` (banco `amazonwatch`, usuário `amazonwatch`)
- **Worker:** Executa a ingestão automaticamente a cada 5 minutos.

---

### Opção 2: Desenvolvimento Local

#### 1. Banco de Dados PostGIS
Suba apenas o PostGIS via Docker:
```bash
docker compose up -d postgis
```

#### 2. Backend (FastAPI + Worker)
```bash
cd backend

# Executar migrações do banco
alembic upgrade head

# Executar testes unitários
python3 -m pytest -v

# Iniciar API
uvicorn app.main:app --reload --port 8000

# Executar o worker de ingestão (em outro terminal)
python3 -m app.worker
```

#### 3. Frontend (Vite + React)
```bash
cd frontend
npm install
npm run dev
```
Acesse em: http://localhost:5173

---

## 📡 Endpoints da API REST

- `GET /api/plumes` — Lista polígonos de plumas de fumaça no formato GeoJSON.
- `GET /api/plumes/{id}` — Detalhes completos da pluma, centróide e focos de incêndio de origem.
- `GET /api/plumes/timeline` — Horários com scans de satélite disponíveis nas últimas 24h.
- `GET /api/hotspots` — Focos de calor em formato GeoJSON com filtros de data e bounding box.
- `GET /api/frames` — Lista de quadros de imagem de satélite True Color reprojetados.
- `GET /api/stats` — Totais de focos, plumas ativas, área total coberta e incêndios de origem.
- `GET /api/region` — GeoJSON do polígono da Amazônia Legal.
- `GET /api/health` — Status de conectividade e horários dos últimos dados ingeridos.
