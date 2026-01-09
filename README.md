# 🤖 Sales Agent API - LangGraph + OpenAI

Agente de ventas inteligente construido con **LangGraph**, **OpenAI** y **herramientas locales**. Sin dependencias de servicios cloud, con observabilidad completa via **LangSmith**.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-green)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0.5%2B-orange)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/License-MIT-purple)](#)

---

## 🎯 Características

### 🤖 Agente de Ventas
- **Conversación natural** en español
- **Búsqueda de productos** mediante semántica local
- **Gestión de órdenes** con persistencia
- **Logística inversa** (devoluciones)
- **Supervisión y escalation** con intervención humana

### 💾 Almacenamiento Local
- **SQLite** para datos estructurados
- **ChromaDB** para búsqueda semántica
- Sin servicios cloud, sin costos adicionales
- Fácil de backupear y versionar

### 📊 Observabilidad Completa
- **LangSmith Integration** para tracing de agentes
- Debugging visual de prompts y respuestas
- Monitoreo de costos OpenAI
- Evaluación automática de calidad

### 🔒 Secure & Local First
- Variables de entorno para credenciales
- Base de datos local (no en cloud)
- Embeddings locales (ChromaDB)
- Únicamente OpenAI como dependencia externa

---

## 🚀 Quick Start

### Requisitos
- Python 3.10+
- OpenAI API Key (get it at https://platform.openai.com/api-keys)

### Instalación (3 pasos)

```bash
# 1. Clonar y navegar
git clone <repo>
cd ProyectoFinalUtecBack

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables
cp .env.local.example .env.local
# Editar .env.local y agregar OPENAI_API_KEY
```

### Ejecutar

```bash
python main.py
```

La API estará disponible en:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs (Swagger UI)

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI (Presentación)               │
│  /api/agent/chat  /api/products  /api/orders           │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────┐
│                 LangGraph (Orquestación)                │
│  ┌─────────────────┐  ┌──────────────────┐             │
│  │ Sales Agent     │  │ Supervisor Node  │             │
│  └────────┬────────┘  └──────────┬───────┘             │
│           │                      │                     │
│  ┌────────┴───────────────────────┴─────────────────┐  │
│  │ Memory Optimizer │ Context Injector │ Followers │  │
│  └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
    ┌───▼────┐  ┌──────▼─────┐  ┌───▼────┐
    │ SQLite │  │  ChromaDB  │  │ OpenAI │
    │        │  │            │  │        │
    │local   │  │ Embeddings │  │ LLM    │
    └────────┘  └────────────┘  └────────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
                ┌──────▼───────┐
                │  LangSmith   │
                │ (Observ.)    │
                └──────────────┘
```

---

## 📁 Estructura del Proyecto

```
ProyectoFinalUtecBack/
├── main.py                          # Punto de entrada
├── requirements.txt                 # Dependencias
├── .env.local.example               # Configuración (plantilla)
│
├── docs/
│   ├── SETUP_GUIDE.md               # Cómo instalar y configurar
│   ├── LANGSMITH_INTEGRATION.md      # Guía de observabilidad
│   └── CHECKLIST.md                 # Progress tracker
│
├── data/                            # 🔒 No commitear
│   ├── app.db                       # SQLite database
│   └── chroma_db/                   # Vectores embeddings
│
├── static/
│   └── images/                      # Imágenes locales
│
├── src/
│   ├── config.py                    # Configuración (pydantic)
│   ├── main.py                      # Lógica principal
│   │
│   ├── domain/
│   │   ├── entities.py              # Modelos de negocio
│   │   └── repositories.py          # Interfaces de datos
│   │
│   ├── infrastructure/
│   │   ├── database/
│   │   │   ├── sqlite_db.py         # Cliente SQLite
│   │   │   └── models.py            # ORM (SQLAlchemy)
│   │   │
│   │   ├── vectorstore/
│   │   │   ├── chroma_store.py      # ChromaDB wrapper
│   │   │   └── pinecone_store.py    # Compatibilidad
│   │   │
│   │   ├── langgraph/
│   │   │   ├── graph.py             # Grafo principal
│   │   │   ├── state.py             # Estado compartido
│   │   │   └── nodes/
│   │   │       ├── sales_agent_v3.py
│   │   │       ├── supervisor.py
│   │   │       ├── orchestrator.py
│   │   │       └── ...
│   │   │
│   │   ├── openai/
│   │   │   ├── http_client.py       # Client HTTP
│   │   │   └── audio_client.py      # Audio processing
│   │   │
│   │   ├── repositories/            # Data access
│   │   │   ├── product_repository.py
│   │   │   ├── order_repository.py
│   │   │   └── ...
│   │   │
│   │   ├── services/
│   │   │   ├── district_matcher.py
│   │   │   ├── pdf_generator.py
│   │   │   └── stock_reservation.py
│   │   │
│   │   └── cache/
│   │       └── memory_store.py
│   │
│   └── presentation/
│       ├── api.py                   # FastAPI setup
│       └── routes/
│           ├── agent.py             # /api/agent
│           ├── products.py          # /api/products
│           ├── orders.py            # /api/orders
│           ├── download.py          # /api/download
│           ├── audio.py             # /api/audio
│           ├── tts.py               # /api/tts
│           ├── images.py            # /api/images
│           ├── health.py            # /health
│           └── receipt.py           # /api/receipt
│
├── scripts/
│   ├── setup_test_data.py           # Cargar datos de prueba
│   ├── seed_database.py             # Seed de productos
│   ├── seed_coupons.py              # Cupones de descuento
│   ├── seed_districts.py            # Distritos
│   ├── seed_all_catalog.py          # Catálogo completo
│   └── load_product_images.py       # Imágenes de productos
│
└── .venv/                           # 🔒 Virtual environment (no git)
```

---

## ⚙️ Configuración

### Variables de Entorno Requeridas

```env
# OpenAI (requerido)
OPENAI_API_KEY=sk-proj-your-key-here
OPENAI_MODEL=gpt-4o-mini

# Base de datos (por defecto es local)
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
CHROMA_PERSIST_DIR=./data/chroma_db
```

### Variables Opcionales

```env
# LangSmith (para observabilidad)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=utec-sales-agent
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# Aplicación
ENVIRONMENT=development
API_HOST=0.0.0.0
API_PORT=8000
```

Ver [SETUP_GUIDE.md](./SETUP_GUIDE.md) para más detalles.

---

## 🎮 Uso

### Chat con el Agente

```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Necesito una mesa para mi comedor",
    "user_id": "user_123"
  }'
```

**Response:**
```json
{
  "response": "He encontrado estas opciones de mesas para ti...",
  "products": [
    {
      "id": "prod_001",
      "name": "Mesa de Comedor Madera",
      "price": 599.99
    }
  ],
  "confidence": 0.95
}
```

### Buscar Productos

```bash
curl http://localhost:8000/api/products/search?query=sofa&limit=5
```

### Ver API Completa

Abre http://localhost:8000/docs en tu navegador para documentación interactiva.

---

## 🔍 Observabilidad con LangSmith

### Setup Rápido

1. Registrarse en https://smith.langchain.com
2. Obtener API key
3. Agregar a `.env.local`:
   ```env
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=your-key
   ```
4. Reiniciar API
5. Ver trazas en https://smith.langchain.com

### Beneficios

- 📊 Visualizar flujo del agente
- 🐛 Debuggear problemas sin código
- ⚡ Optimizar prompts en tiempo real
- 📈 Monitorear costos OpenAI
- ✅ Evaluar calidad automáticamente

Ver [LANGSMITH_INTEGRATION.md](./LANGSMITH_INTEGRATION.md) para guía completa.

---

## 🗄️ Base de Datos

### SQLite (Local)

```python
# Ubicación: data/app.db
# Sin contraseña, sin configuración

# Tablas principales:
- customers (usuarios)
- products (catálogo)
- orders (órdenes)
- order_items (ítems de órdenes)
- coupons (descuentos)
- delivery_slots (horarios de entrega)
```

### ChromaDB (Embeddings)

```python
# Ubicación: data/chroma_db/
# Almacena embeddings de productos
# Permite búsqueda semántica

# Colecciones:
- products (descripciones de productos)
- districts (nombres de distritos)
```

### Backup

```bash
# Respaldar datos
cp -r data/ backups/data_$(date +%Y%m%d)

# Restaurar
cp -r backups/data_20250108/ data/
```

---

## 🧪 Testing

### Ejecutar Tests

```bash
pytest
pytest -v  # Verbose
pytest --cov  # Con coverage
```

### Test de Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Chat con agente
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola"}'

# Documentación Swagger
open http://localhost:8000/docs
```

---

## 🐛 Troubleshooting

| Problema | Solución |
|----------|----------|
| `OpenAI API key not found` | Verificar `.env.local` tiene `OPENAI_API_KEY` |
| `SQLite connection failed` | Ejecutar `mkdir -p data` |
| `ChromaDB not initialized` | Los embeddings se regenerarán automáticamente |
| `Port 8000 already in use` | Cambiar en `.env.local`: `API_PORT=8001` |
| `LangSmith traces no appear` | Verificar `LANGCHAIN_TRACING_V2=true` |

Ver [SETUP_GUIDE.md](./SETUP_GUIDE.md#-troubleshooting) para más.

---

## 📦 Dependencias Principales

```
FastAPI             - Framework web
LangGraph           - Orquestación de agentes
LangChain           - Framework LLM
OpenAI              - Modelo GPT-4o-mini
SQLAlchemy          - ORM para SQLite
ChromaDB            - Vector store local
LangSmith           - Observabilidad
Uvicorn             - Servidor ASGI
```

Ver [requirements.txt](./requirements.txt) para lista completa.

---

## 🚀 Deployment

### Local Development
```bash
python main.py
```

### Production
```bash
# Desactivar debug
ENVIRONMENT=production
DEBUG=false

# Ejecutar con Gunicorn
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

### Docker (Opcional)
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

---

## 🔐 Seguridad

- ✅ API key OpenAI en variables de entorno
- ✅ Base de datos local (no en cloud)
- ✅ No hay datos sensibles en logs
- ✅ CORS configurado
- ✅ Rate limiting

### Checklist de Seguridad

```bash
# Antes de producción:
[ ] OPENAI_API_KEY nunca en código
[ ] .env.local en .gitignore
[ ] DATABASE_URL no tiene credenciales
[ ] SECRET_KEY es único
[ ] DEBUG=false en production
```

---

## 📚 Documentación

- **[SETUP_GUIDE.md](./SETUP_GUIDE.md)** - Instalación y configuración
- **[LANGSMITH_INTEGRATION.md](./LANGSMITH_INTEGRATION.md)** - Observabilidad
- **[CHECKLIST.md](./CHECKLIST.md)** - Progreso del proyecto
- **Swagger UI** - http://localhost:8000/docs
- **ReDoc** - http://localhost:8000/redoc

---

## 🤝 Contribuir

1. Fork el repo
2. Crear rama: `git checkout -b feature/mi-feature`
3. Commit cambios: `git commit -am 'Agregar feature'`
4. Push: `git push origin feature/mi-feature`
5. Pull Request

---

## 📄 Licencia

MIT - Ver [LICENSE](./LICENSE) para más detalles.

---

## 📧 Contacto

- **Email**: info@blackcombinator.com
- **GitHub Issues**: Reportar bugs aquí
- **Documentación**: Ver archivos `.md` en la raíz

---

## 🎉 Agradecimientos

Construido con:
- 🦾 LangGraph - Orquestación
- 🤖 OpenAI GPT-4o-mini - IA
- 📡 LangSmith - Observabilidad
- ⚡ FastAPI - API web
- 💾 SQLite + ChromaDB - Almacenamiento local

---

**Versión**: 1.0.0 (LangGraph + OpenAI Simplificado)
**Última actualización**: 2025-01-08
**Estado**: ✅ Listo para usar
