# Arduino Co-Pilot — AI-Powered Code Assistant

> **Project ID:** 24KIDS436  
> An on-device, RAG-augmented VS Code extension that generates Arduino sketches, wiring guides, bilingual explanations, and IoT integration code — all running locally with no cloud dependency.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Technical Details](#technical-details)
- [License](#license)

---

## Overview

Arduino Co-Pilot is a fully offline AI assistant for Arduino development, built as a VS Code extension. It combines a quantized large language model (Phi-3-mini) with a Retrieval-Augmented Generation (RAG) pipeline backed by FAISS vector search over 58 curated Arduino documents. The result is fast, context-aware code generation that runs entirely on the developer's machine.

---

## Key Features

| Feature | Description |
|---|---|
| **Code Generation** | Generates complete Arduino sketches — pin setup, ISR templates, sensor reads, Wi-Fi/BLE, state machines, sleep modes |
| **RAG Pipeline** | FAISS vector index over 58 documents with MiniLM-L6-v2 embeddings; injects relevant context into every prompt |
| **Wiring Guides** | Pin-by-pin connection instructions with component lists and safety notes |
| **Bilingual Explanations** | Tamil and English "why-it-works" breakdowns for each generated sketch |
| **IoT Export** | MQTT topic suggestions for EMQX broker and Node-RED flow JSON for dashboard integration |
| **VS Code Integration** | Activity Bar sidebar with tabbed UI (Code, Connections, Explain, IoT) and one-click Insert to Editor |
| **Fully Offline** | No API keys, no cloud calls — Phi-3-mini GGUF runs locally via llama.cpp |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    User Interface                     │
│   ┌────────────┐   ┌────────────┐   ┌─────────────┐  │
│   │  VS Code   │   │ Streamlit  │   │     CLI     │  │
│   │ Extension  │   │   Demo     │   │   Runner    │  │
│   └─────┬──────┘   └─────┬──────┘   └──────┬──────┘  │
│         └─────────────────┼─────────────────┘         │
├───────────────────────────┼───────────────────────────┤
│                  copilot_runner.py                     │
│   ┌───────────────────────┼────────────────────────┐  │
│   │          RAG Pipeline                          │  │
│   │   ┌────────────┐   ┌────────────────────────┐  │  │
│   │   │   FAISS    │   │  MiniLM-L6-v2          │  │  │
│   │   │   Index    │   │  Sentence Embeddings   │  │  │
│   │   └────────────┘   └────────────────────────┘  │  │
│   └────────────────────────────────────────────────┘  │
│   ┌────────────────────────────────────────────────┐  │
│   │     LLM Engine — Phi-3-mini via llama.cpp      │  │
│   └────────────────────────────────────────────────┘  │
│   ┌────────────┐  ┌──────────────┐  ┌──────────────┐  │
│   │   Code     │  │   Explain    │  │ MQTT/NodeRED │  │
│   │ Generator  │  │ Tamil + Eng  │  │  IoT Export  │  │
│   └────────────┘  └──────────────┘  └──────────────┘  │
├───────────────────────────────────────────────────────┤
│             Knowledge Base (SQLite + JSON)             │
│   • Arduino Language Reference — 40+ functions         │
│   • Board Pinouts — Uno, Nano, Mega, ESP32, R4 WiFi    │
│   • Cookbook Patterns — 12+ common circuits             │
└───────────────────────────────────────────────────────┘
```

---

## Project Structure

```
arduino-co-pilot/
├── extension.js            VS Code extension (sidebar + panel webview)
├── setup_wizard.js         First-run setup wizard
├── package.json            Extension manifest and contributes
├── copilot_runner.py       RAG pipeline and LLM code generator
├── scraper.py              Arduino knowledge base builder (58 entries)
├── vector_store.py         FAISS index builder + SQLite store
├── app.py                  Streamlit demo UI
├── setup.py                One-click environment verification
├── requirements.txt        Python dependencies
├── media/
│   └── arduino-icon.svg    Activity Bar icon
├── docs_data/              Pre-built knowledge base (included)
│   ├── arduino_faiss.index
│   ├── arduino_docs.db
│   ├── arduino_knowledge_base.json
│   └── id_mapping.json
└── test/
    └── extension.test.js   Extension unit tests
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **VS Code** | 1.85+ | Required for webview API |
| **Python** | 3.10.x | 3.10 recommended; llama-cpp-python wheels available |
| **Node.js** | 18+ | For extension packaging only |

### Python Packages

```
llama-cpp-python
faiss-cpu
sentence-transformers
numpy
```

### LLM Model

Download the quantized model (~2 GB) and place it in the project root:

```
Phi-3-mini-4k-instruct.Q4_0.gguf
```

Source: [Hugging Face — microsoft/Phi-3-mini-4k-instruct-gguf](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf)

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/sandeepmk2006/arduino-co-pilot.git
cd arduino-co-pilot
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Verify Setup

```bash
python setup.py
```

This checks Python version, required packages, model file, and FAISS index.

### 4. Install the VS Code Extension

**Option A — From VSIX:**
```bash
npx @vscode/vsce package --allow-missing-repository
code --install-extension arduino-co-pilot-*.vsix
```

**Option B — Development Mode:**
```
Press F5 in VS Code → opens Extension Development Host
```

---

## Usage

### VS Code Extension

1. Click the **Arduino Co-Pilot** icon in the Activity Bar (left sidebar)
2. Type a prompt, e.g., `blink LED on pin 13`
3. Click **Generate Code**
4. Browse the tabbed results:
   - **Code** — Complete Arduino sketch with Copy and Insert buttons
   - **Connections** — Wiring guide with component list
   - **Explain** — Bilingual Tamil/English explanation
   - **IoT** — MQTT topics and Node-RED flow JSON

### Command Line

```bash
python copilot_runner.py "blink an LED on pin 13"
python copilot_runner.py "read DHT11 temperature sensor"
python copilot_runner.py "servo motor sweep 0 to 180"
```

### Streamlit Demo

```bash
streamlit run app.py
```

---

## Configuration

### VS Code Settings

| Setting | Default | Description |
|---|---|---|
| `arduino-co-pilot.pythonPath` | Auto-detect | Path to Python 3.10 executable |
| `arduino-co-pilot.modelPath` | Auto-detect | Path to the GGUF model file |

### CLI Arguments

| Argument | Description |
|---|---|
| `--workspace <path>` | Set workspace directory for model and index lookup |
| `--no-rag` | Disable RAG retrieval |
| `--no-explain` | Skip bilingual explanation |
| `--no-iot` | Skip MQTT/Node-RED export |
| `--top-k <n>` | Number of RAG documents to retrieve (default: 5) |

---

## Technical Details

| Component | Technology |
|---|---|
| LLM | Phi-3-mini-4K-Instruct, Q4_0 quantization (~2 GB) |
| Inference | llama-cpp-python (CPU, auto-threaded) |
| Embeddings | all-MiniLM-L6-v2 (384-dim, sentence-transformers) |
| Vector Store | FAISS IndexFlatIP, 58 vectors |
| Metadata Store | SQLite (arduino_docs.db) |
| Knowledge Base | 40+ language reference entries, 6 board pinouts, 12 cookbook patterns |
| Extension UI | VS Code Webview API, HTML/CSS/JS |
| Context Window | 2048 tokens (optimized for speed) |

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).
