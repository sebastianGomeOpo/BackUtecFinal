# 🚀 Setup Guide - Sales Agent API (LangGraph + OpenAI)

## Visión General

El proyecto ha sido simplificado para usar **solo dependencias locales**:
- **LangGraph** para orquestación de agentes
- **OpenAI** como LLM
- **SQLite** para base de datos local
- **ChromaDB** para búsqueda semántica local
- **LangSmith** para observabilidad y debugging

## 🔧 Requisitos Previos

- Python 3.10+
- pip o uv package manager
- OpenAI API Key (obtener en https://platform.openai.com/api-keys)
- LangSmith API Key (opcional, para observabilidad)

## 📋 Instalación Rápida

### 1. Clonar o descargar el proyecto
```bash
cd ProyectoFinalUtecBack
```

### 2. Crear ambiente virtual
```bash
# Con venv (Python estándar)
python -m venv .venv

# Activar (Windows)
.venv\Scripts\activate

# Activar (macOS/Linux)
source .venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
```bash
# Copiar archivo de ejemplo
cp .env.local.example .env.local

# Editar .env.local con tus credenciales
nano .env.local  # o usar tu editor favorito
```

### 5. Inicializar base de datos
```bash
# (Opcional) Crear datos de prueba
python scripts/setup_test_data.py
```

### 6. Ejecutar la API
```bash
python main.py
```

La API estará disponible en: `http://localhost:8000`

Documentación interactiva: `http://localhost:8000/docs`

---

## 🌍 Variables de Entorno

### Requeridas

```env
# OpenAI (https://platform.openai.com/api-keys)
OPENAI_API_KEY=sk-proj-your-api-key-here
OPENAI_MODEL=gpt-4o-mini
```

### Opcionales pero Recomendadas

```env
# LangSmith para Observabilidad
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=your-project-name
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### Valores por Defecto

```env
# Base de Datos (SQLite - Local)
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# Vector Store (ChromaDB - Local)
CHROMA_PERSIST_DIR=./data/chroma_db

# Aplicación
ENVIRONMENT=development
API_HOST=0.0.0.0
API_PORT=8000
```

---

## 📊 LangSmith Setup (Observabilidad)

### ¿Por qué LangSmith?

LangSmith te permite:
- **Rastrear** todas las llamadas del agente en tiempo real
- **Debuggear** problemas de lógica sin código
- **Evaluar** el rendimiento de LLM
- **Optimizar** prompts directamente
- **Monitorear** costos de API

### Pasos para Activar LangSmith

#### 1. Crear Cuenta en LangSmith
- Ir a https://smith.langchain.com
- Registrarse (gratuito)

#### 2. Obtener API Key
- Dashboard → Settings → API Keys
- Copiar tu API key

#### 3. Configurar Variables
Agregar a `.env.local`:
```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-copied-key
LANGCHAIN_PROJECT=utec-sales-agent
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

#### 4. Verificar Integración
```bash
# Después de reiniciar la API
curl http://localhost:8000/health

# Ve a https://smith.langchain.com → Proyectos
# Deberías ver "utec-sales-agent" con trazas
```

---

## 📁 Estructura de Carpetas

```
ProyectoFinalUtecBack/
├── main.py                          # Punto de entrada
├── requirements.txt                 # Dependencias
├── .env.local.example               # Plantilla de configuración
├── SETUP_GUIDE.md                   # Este archivo
│
├── data/                            # ⚠️ No commitear a git
│   ├── app.db                       # SQLite database
│   └── chroma_db/                   # ChromaDB embeddings
│
├── static/
│   └── images/                      # Imágenes locales
│
├── src/
│   ├── config.py                    # Configuración global
│   ├── main.py                      # Lógica principal
│   ├── domain/                      # Modelos de dominio
│   ├── infrastructure/
│   │   ├── database/
│   │   │   ├── sqlite_db.py         # SQLite client
│   │   │   └── models.py            # ORM models
│   │   ├── vectorstore/
│   │   │   ├── chroma_store.py      # ChromaDB wrapper
│   │   │   └── pinecone_store.py    # Compatibility layer
│   │   ├── langgraph/
│   │   │   ├── graph.py             # Definición del grafo
│   │   │   ├── state.py             # Estado compartido
│   │   │   └── nodes/               # Agentes individuales
│   │   ├── openai/                  # Clientes OpenAI
│   │   └── repositories/            # Acceso a datos
│   └── presentation/
│       ├── api.py                   # Setup de FastAPI
│       └── routes/                  # Endpoints HTTP
│
├── scripts/
│   ├── setup_test_data.py           # Cargar datos de prueba
│   └── seed_*.py                    # Scripts de seed
│
└── .venv/                           # ⚠️ Virtual environment (no commitear)
```

---

## 🔍 Observabilidad Sin LangSmith

Si prefieres no usar LangSmith, la aplicación sigue funcionando. Solo cambia:

```env
LANGCHAIN_TRACING_V2=false
```

Los logs se guardarán en `logs/` directorio.

---

## 🧪 Testing

### Ejecutar Tests
```bash
pytest
```

### Testing de Endpoints
```bash
# Health check
curl http://localhost:8000/health

# Agent endpoint
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Necesito ayuda con una mesa"}'

# Buscar productos
curl http://localhost:8000/api/products/search?query=sofa
```

---

## 🐛 Troubleshooting

### SQLite Connection Error
```
❌ SQLite connection failed
```
**Solución:**
```bash
# Asegúrate que data/ existe
mkdir -p data

# Reinicia la API
python main.py
```

### ChromaDB Initialization Failed
```
⚠️ ChromaDB initialization failed
```
**Solución:**
```bash
# ChromaDB se re-inicializará automáticamente
# Si persiste:
rm -rf data/chroma_db
python main.py
```

### OpenAI API Error
```
❌ OpenAI API key not found
```
**Solución:**
1. Verificar `.env.local` tiene `OPENAI_API_KEY`
2. Key debe empezar con `sk-proj-`
3. Reiniciar API: `python main.py`

### LangSmith Tracing No Funciona
```
# Verificar credenciales
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-key-here
```

---

## 📈 Próximos Pasos

### 1. Cargar Datos de Producción
```bash
# Usa los scripts en scripts/ para seed data
python scripts/seed_database.py
```

### 2. Monitorear con LangSmith
- Accede a https://smith.langchain.com
- Observa trazas de agentes en tiempo real
- Evalúa LLM responses

### 3. Optimizar Prompts
- En LangSmith, haz click en una traza
- Edita el prompt directamente
- Prueba cambios sin redeploy

### 4. Agregar Autenticación
Ver `src/infrastructure/openai/` para ejemplos de JWT tokens

---

## 🔗 Recursos

- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **OpenAI API**: https://platform.openai.com/docs
- **LangSmith**: https://docs.smith.langchain.com/
- **ChromaDB**: https://docs.trychroma.com/

---

## ❓ Preguntas Frecuentes

### ¿Dónde se guardan los datos?
Todo en `data/` directorio (no commitear):
- `data/app.db` - SQLite
- `data/chroma_db/` - Vectores

### ¿Cuánto cuesta?
- **SQLite**: Gratis (local)
- **ChromaDB**: Gratis (local)
- **OpenAI**: Pay-as-you-go (~$0.15 por 1M tokens)
- **LangSmith**: Gratuito hasta 100K tokens/mes

### ¿Cómo deploy a producción?
- Cambiar `ENVIRONMENT=production`
- Usar variable `OPENAI_API_KEY` de sistema
- Usar servicio de base datos externo si es necesario

---

**Última actualización**: 2025-01-08
**Versión del Proyecto**: 1.0.0 (LangGraph + OpenAI)
