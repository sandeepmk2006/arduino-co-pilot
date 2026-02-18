"""
Arduino Co-Pilot Runner
RAG-powered Arduino code generator with:
- FAISS vector retrieval
- Phi-3-mini LLM via llama.cpp
- Tamil/English explanations
- MQTT/Node-RED IoT export
"""
import sys
import json
import argparse
import os
from pathlib import Path

# ── Model and paths ──────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()

def _resolve_workspace():
    """Find the workspace directory containing the model file.
    Priority: --workspace arg > ARDUINO_COPILOT_WORKSPACE env > cwd > script dir"""
    # Check --workspace in sys.argv early (before argparse)
    for i, arg in enumerate(sys.argv):
        if arg == '--workspace' and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1]).resolve()
    # Environment variable
    env_ws = os.environ.get('ARDUINO_COPILOT_WORKSPACE')
    if env_ws and Path(env_ws).exists():
        return Path(env_ws).resolve()
    # Current working directory
    cwd = Path.cwd()
    if (cwd / 'Phi-3-mini-4k-instruct.Q4_0.gguf').exists():
        return cwd
    # Fallback to script directory
    return SCRIPT_DIR

WORKSPACE_DIR = _resolve_workspace()
MODEL_PATH = str(WORKSPACE_DIR / "Phi-3-mini-4k-instruct.Q4_0.gguf")
DOCS_DIR = str(WORKSPACE_DIR / "docs_data")


# ── RAG Context Retrieval ────────────────────────────────────────────
def retrieve_context(prompt, top_k=5):
    """Retrieve relevant Arduino docs from FAISS vector store."""
    try:
        from vector_store import ArduinoVectorStore
        store = ArduinoVectorStore(data_dir=DOCS_DIR)
        results = store.search(prompt, top_k=top_k)
        if results:
            context_parts = []
            for r in results:
                context_parts.append(
                    f"[{r['category']}] {r['title']}:\n{r['content']}"
                )
            return "\n\n---\n\n".join(context_parts)
    except Exception as e:
        print(f"RAG retrieval warning: {e}", file=sys.stderr)

    # Fallback: return empty context
    return ""


# ── Code Generation ──────────────────────────────────────────────────
def generate_arduino_code(llm, prompt, rag_context=""):
    """Generate Arduino code using RAG-augmented prompt."""

    system_msg = """You are an expert Arduino code generator with deep knowledge of microcontrollers, sensors, actuators, and embedded systems.

STRICT RULES:
1. Generate code that EXACTLY matches the user's request. Do NOT substitute components.
2. Use the simplest correct method. For "blink LED" use digitalWrite()+delay(). For "fade LED" use analogWrite().
3. Include #include only when the component requires a library.
4. Use correct pins for the specified board. Default to Arduino Uno unless stated otherwise.
   - PWM pins (Uno): 3, 5, 6, 9, 10, 11
   - Interrupt pins (Uno): 2, 3
   - I2C: SDA=A4, SCL=A5
   - SPI: MOSI=11, MISO=12, SCK=13, SS=10
5. Always include complete void setup() and void loop().
6. Use correct timing constants and register names.
7. Add brief inline comments explaining key lines.

REFERENCE DOCUMENTATION (use this to ensure accuracy):
"""

    if rag_context:
        system_msg += f"\n{rag_context}\n"
    else:
        system_msg += "\n(No additional reference available - rely on your training data.)\n"

    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"Generate complete Arduino code for: {prompt}"}
        ],
        max_tokens=800,
        temperature=0.1
    )

    generated_code = response['choices'][0]['message']['content'].strip()

    # Clean code block markers
    if "```" in generated_code:
        lines = generated_code.split('\n')
        clean_lines = []
        in_code = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code or not generated_code.startswith("```"):
                clean_lines.append(line)
        generated_code = '\n'.join(clean_lines).strip()

    return generated_code


# ── Connection Instructions ──────────────────────────────────────────
def generate_connection_help(llm, code, rag_context=""):
    """Generate wiring/connection instructions based on the code."""
    help_prompt = f"""Based on this Arduino code, provide clear connection instructions:

```cpp
{code}
```

Format as a bulleted list with:
- Exact components needed (with values like 220Ω resistor)
- Pin-by-pin wiring (e.g., "LED anode → Pin 13, cathode → 220Ω resistor → GND")
- Power requirements and safety notes
- Common mistakes to avoid"""

    context_note = ""
    if rag_context:
        context_note = f"\n\nReference data:\n{rag_context}"

    try:
        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": f"You are an electronics expert providing Arduino wiring instructions. Be precise about component values and pin connections.{context_note}"},
                {"role": "user", "content": help_prompt}
            ],
            max_tokens=250,
            temperature=0.3
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Could not generate connection help: {str(e)}"


# ── Tamil/English Explanation ────────────────────────────────────────
def generate_explanation(llm, code, prompt):
    """Generate a bilingual Tamil/English 'why it works' explanation."""
    explain_prompt = f"""For this Arduino code that does "{prompt}":

{code}

Provide a short explanation in BOTH English and Tamil.
Do NOT use markdown formatting (no **, no ##, no ```).

English:
Explain in 2-3 simple sentences why this code works.

Tamil:
Provide the same explanation in Tamil using simple terms.

Keep it concise."""

    try:
        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": "You are a bilingual (English/Tamil) Arduino teacher. Give plain text answers. Never use markdown formatting like ** or ## or ```."},
                {"role": "user", "content": explain_prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Could not generate explanation: {str(e)}"


# ── MQTT / Node-RED Export ───────────────────────────────────────────
def generate_mqtt_nodered(llm, code, prompt):
    """Generate MQTT topic structure and Node-RED flow JSON."""

    mqtt_prompt = f"""Analyze this Arduino code and create MQTT integration:

```cpp
{code}
```

Based on the code above, generate:

1. **MQTT Topics** (use broker.emqx.io:1883):
   - For SENSORS (if code has sensors): Publish topic like `arduino/sensor/<type>`
   - For ACTUATORS (LED, motor, relay): Subscribe topic `arduino/command/<device>` + publish status `arduino/status/<device>`
   - For simple LED blink: `arduino/led/status` (publish ON/OFF state)

2. **Node-RED Flow JSON** (one MQTT-in, one MQTT-out, one debug node minimum):
   - Match the actual components in the code
   - Use simple, working Node-RED format

Keep it minimal and functional."""

    try:
        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": "Analyze Arduino code and generate appropriate MQTT topics. For LED projects use led/status and led/command topics. For sensors use sensor/<type> topics. Be specific to the actual code."},
                {"role": "user", "content": mqtt_prompt}
            ],
            max_tokens=300,
            temperature=0.2
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return ""


# ── Main Entry Point ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Arduino Co-Pilot Code Generator")
    parser.add_argument("prompt", help="Natural language description of the Arduino project")
    parser.add_argument("--no-rag", action="store_true", help="Disable RAG retrieval")
    parser.add_argument("--no-explain", action="store_true", help="Skip Tamil/English explanation")
    parser.add_argument("--no-iot", action="store_true", help="Skip MQTT/Node-RED export")
    parser.add_argument("--top-k", type=int, default=5, help="Number of RAG documents to retrieve")
    parser.add_argument("--workspace", type=str, default=None, help="Path to workspace containing model and docs_data")
    args = parser.parse_args()

    try:
        from llama_cpp import Llama

        # Initialize LLM
        import os
        cpu_count = os.cpu_count() or 4
        llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=2048,
            n_threads=cpu_count,
            n_batch=1024,
            use_mlock=True,
            verbose=False
        )

        # Step 1: RAG retrieval
        rag_context = ""
        if not args.no_rag:
            rag_context = retrieve_context(args.prompt, top_k=args.top_k)

        # Step 2: Generate code
        arduino_code = generate_arduino_code(llm, args.prompt, rag_context)

        # Step 3: Generate connection help
        connection_help = generate_connection_help(llm, arduino_code, rag_context)

        # Step 4: Generate Tamil/English explanation
        explanation = ""
        if not args.no_explain:
            explanation = generate_explanation(llm, arduino_code, args.prompt)

        # Step 5: Generate MQTT/Node-RED (optional)
        iot_config = ""
        if not args.no_iot:
            iot_config = generate_mqtt_nodered(llm, arduino_code, args.prompt)

        # Output JSON result
        output = {
            "code": arduino_code,
            "help": connection_help,
            "explanation": explanation,
            "iot": iot_config,
            "rag_used": bool(rag_context),
            "rag_docs": len(rag_context.split("---")) if rag_context else 0
        }
        print(json.dumps(output))

    except Exception as e:
        error_output = {
            "code": f"// Error: {str(e)}",
            "help": "Could not generate due to an error.",
            "explanation": "",
            "iot": "",
            "rag_used": False,
            "rag_docs": 0
        }
        print(json.dumps(error_output))


if __name__ == "__main__":
    main()
