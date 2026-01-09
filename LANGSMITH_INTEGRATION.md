# 📊 LangSmith Integration Guide

## ¿Qué es LangSmith?

LangSmith es una plataforma de observabilidad para aplicaciones LLM que te permite:

- **Rastrear (Trace)** cada llamada al LLM, herramientas y procesos intermedios
- **Debuggear (Debug)** problemas visualizando el flujo completo
- **Evaluar (Evaluate)** la calidad de respuestas automáticamente
- **Monitorear (Monitor)** uso de API, costos y latencias
- **Optimizar (Optimize)** prompts sin cambiar código

---

## 🚀 Inicio Rápido

### 1. Registrarse en LangSmith
1. Visita https://smith.langchain.com
2. Haz clic en "Sign Up"
3. Completa el registro (puedes usar GitHub)
4. Confirma tu email

### 2. Obtener API Key
1. En el dashboard de LangSmith, ve a **Settings** (ícono de engranaje)
2. Haz clic en **API Keys**
3. Crea una nueva key o copia la existente
4. Copia el valor completo

### 3. Configurar Proyecto

#### Opción A: Archivo .env.local (Recomendado)
```env
# .env.local
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_your-api-key-here
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_PROJECT=utec-sales-agent
```

#### Opción B: Variables de Sistema
```bash
# macOS/Linux
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=lsv2_pt_your-api-key-here
export LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
export LANGCHAIN_PROJECT=utec-sales-agent

# Windows PowerShell
$env:LANGCHAIN_TRACING_V2="true"
$env:LANGCHAIN_API_KEY="lsv2_pt_your-api-key-here"
$env:LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
$env:LANGCHAIN_PROJECT="utec-sales-agent"
```

### 4. Verificar que Funciona

```bash
# Reinicia la API
python main.py

# En otra terminal, haz una solicitud
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola, necesito una mesa"}'

# Espera unos segundos y ve a https://smith.langchain.com
# Deberías ver trazas en el proyecto "utec-sales-agent"
```

---

## 📖 Cómo Funciona en el Proyecto

### Trazas Automáticas

Cuando `LANGCHAIN_TRACING_V2=true`, automáticamente se rastrean:

```
Chat Request
├─ Message: "Quiero una mesa"
├─ Sales Agent Node
│  ├─ OpenAI Call (gpt-4o-mini)
│  │  └─ Total tokens: 342
│  ├─ Product Search (ChromaDB)
│  │  └─ Resultados: 5 productos
│  └─ Response
├─ Supervisor Node
│  └─ Routing decision
└─ Response to User
```

Cada uno de estos pasos es **rastreable** en LangSmith.

### Ejemplo: Rastrear un Chat

```python
# En src/presentation/routes/agent.py
# Las trazas se capturan automáticamente

@router.post("/chat")
async def chat(request: ChatRequest):
    # LangSmith automáticamente registra:
    # 1. Entrada del usuario
    # 2. Llamadas a LLM
    # 3. Búsquedas de productos
    # 4. Decisiones del supervisor
    # 5. Salida final

    response = await graph.ainvoke(...)
    return response
```

---

## 🔍 Usando LangSmith Dashboard

### Vista Principal

1. **Projects** - Todos tus proyectos (e.g., "utec-sales-agent")
2. **Runs** - Todas las ejecuciones/trazas
3. **Tests** - Crear datasets de prueba
4. **Datasets** - Datos para evaluación

### Inspeccionar una Traza

```
Haz clic en cualquier "Run" en la lista
↓
Se abre la traza con:
  - Árbol de llamadas (qué llamó a qué)
  - Tokens usados
  - Latencia (tiempo de respuesta)
  - Inputs y outputs
  - Errores (si hay)
```

### Ejemplo: Debug de Problema

**Problema:** "El agente no encuentra productos"

**Solución con LangSmith:**
1. Ve a tu proyecto
2. Filtra por última ejecución
3. Abre la traza
4. Busca el nodo "search_products"
5. Inspecciona la query que se envió a ChromaDB
6. Mira los resultados retornados
7. Identifica si el problema es la query o la búsqueda

---

## 📊 Evaluación Automática

### Crear Dataset de Prueba

```python
# En LangSmith Dashboard:
# 1. Ve a "Datasets"
# 2. Haz clic en "Create Dataset"
# 3. Agrega ejemplos:
#    Input: "Quiero una mesa grande"
#    Expected Output: [ID del producto de mesa]
```

### Ejecutar Evaluación

```bash
# Opción 1: Desde LangSmith UI
# - Ve a tu dataset
# - Clic en "Evaluate"
# - Selecciona evaluador (e.g., "Exact Match")

# Opción 2: Desde código (avanzado)
from langsmith import evaluate
from src.main import graph

results = evaluate(
    lambda x: graph.invoke({"input": x}),
    data=dataset,
    evaluators=[exact_match_evaluator],
    experiment_prefix="v1"
)
```

---

## 🎯 Casos de Uso Común

### 1. Entender Latencia

**Pregunta:** "¿Por qué la respuesta tarda 5 segundos?"

**En LangSmith:**
1. Abre la traza
2. Cada nodo muestra su tiempo
3. El nodo más lento es el cuello de botella

**Ejemplo de Output:**
```
Sales Agent: 2.3s
├─ ChromaDB Search: 1.8s ← ¡AQUÍ está el problema!
├─ OpenAI Call: 0.4s
└─ Response Formatting: 0.1s
```

### 2. Optimizar Prompts

**Problema:** "Las respuestas no son lo suficientemente buenas"

**Con LangSmith:**
1. Abre la traza del "OpenAI Call"
2. Haz clic en "Edit Prompt"
3. Modifica el prompt directamente
4. Prueba sin redeploy (feature: "Playground")
5. Si es mejor, copia el nuevo prompt
6. Actualiza en `sales_agent_v3.py`

### 3. Monitorear Costos

**Dashboard → Monitoring:**
- Total tokens gastados
- Costo en USD
- Desglose por modelo
- Tasa de errores

---

## ⚙️ Configuración Avanzada

### Proyectos Separados por Entorno

```env
# .env.development
LANGCHAIN_PROJECT=utec-sales-agent-dev

# .env.production
LANGCHAIN_PROJECT=utec-sales-agent-prod
```

### Filtrar Trazas

En LangSmith, filtra por:
- **User ID** - Rastrear usuario específico
- **Status** - Error vs Success
- **Latency** - Tiempo de respuesta
- **Token Count** - Uso de API

### Custom Tags

```python
# En tu código (avanzado)
from langchain_core.callbacks import tags_callbacks

with tags_callbacks({"user_id": "user_123", "feature": "chat"}):
    response = await graph.ainvoke(input_data)

# En LangSmith, verás estos tags y podrás filtrar
```

---

## 🚨 Solución de Problemas

### Las trazas no aparecen

**Checklist:**
1. `LANGCHAIN_TRACING_V2=true` ✓
2. `LANGCHAIN_API_KEY` no está vacío ✓
3. API reiniciada después de cambios `.env` ✓
4. Red permite conexiones a `https://api.smith.langchain.com` ✓

**Debug:**
```python
# En Python shell
import os
print(os.getenv("LANGCHAIN_TRACING_V2"))
print(os.getenv("LANGCHAIN_API_KEY")[:10] + "...")
```

### Errores de Rate Limit

"Too many requests" → Plan gratuito de LangSmith tiene límites

**Soluciones:**
1. Aumentar delay entre requests
2. Upgrade a plan pagado
3. Reducir frecuencia de ejecuciones

### Datos sensibles en Trazas

**Problemas:** Los prompts/respuestas se ven en LangSmith

**Soluciones:**
1. Configurar masking en LangSmith (Settings → Data)
2. Usar `LANGCHAIN_ENDPOINT` privado
3. No incluir datos sensibles en prompts

---

## 💡 Best Practices

### 1. Nombres Descriptivos
```env
# ❌ Evitar
LANGCHAIN_PROJECT=test

# ✅ Recomendado
LANGCHAIN_PROJECT=utec-sales-agent-v3-openai
```

### 2. Tags Útiles
```python
# Agregar contexto a cada ejecución
tags = {
    "model": "gpt-4o-mini",
    "feature": "chat",
    "user_type": "anonymous",
    "language": "es"
}
```

### 3. Monitorear Regularmente
- Revisa métricas semanalmente
- Alertas de errores
- Tendencias de latencia

---

## 📚 Recursos

- **LangSmith Docs**: https://docs.smith.langchain.com/
- **LangChain Observability**: https://docs.langchain.com/docs/langsmith/
- **Video Tutorial**: https://www.youtube.com/watch?v=...

---

## 🔐 Seguridad

### No Compartir API Keys
```bash
# ❌ Nunca hagas esto
git add .env.local  # ← contiene LANGCHAIN_API_KEY

# ✅ Correcto
echo ".env.local" >> .gitignore
git add .gitignore
```

### Rotación de Keys
```
LangSmith Dashboard → Settings → API Keys
→ Revoke old key
→ Crear nueva key
→ Actualizar en tu código
```

---

**Última actualización**: 2025-01-08
**Compatible con**: LangSmith 0.2.0+
