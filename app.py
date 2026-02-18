"""
Arduino Co-Pilot - Streamlit Demo
Deployable on Hugging Face Spaces (CPU Tier).
"""
import streamlit as st
import json
import sys
import os
from pathlib import Path

# Add parent dir to path
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

# ── Page Config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Arduino Co-Pilot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
.main-header { text-align: center; padding: 1rem 0; }
.main-header h1 { color: #00979D; font-size: 2.5rem; }
.main-header p { color: #666; font-size: 1.1rem; }
.code-box {
    background: #1e1e1e; color: #d4d4d4; padding: 1rem;
    border-radius: 8px; font-family: 'Consolas', monospace;
    font-size: 13px; overflow-x: auto; white-space: pre-wrap;
}
.info-box {
    background: #f0f7ff; border-left: 4px solid #00979D;
    padding: 1rem; border-radius: 4px; margin: 0.5rem 0;
}
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] {
    background-color: #f0f2f6; border-radius: 6px 6px 0 0; padding: 8px 20px;
}
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🤖 Arduino Co-Pilot</h1>
    <p>AI-powered Arduino code generator with RAG retrieval, bilingual explanations, and IoT integration</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    st.subheader("Model Configuration")
    model_path = st.text_input(
        "Model Path",
        value=str(SCRIPT_DIR / "Phi-3-mini-4k-instruct.Q4_0.gguf"),
        help="Path to the quantized Phi-3 GGUF model"
    )
    n_threads = st.slider("CPU Threads", 1, 12, 6)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.1)
    max_tokens = st.slider("Max Tokens", 100, 1500, 800)

    st.subheader("RAG Settings")
    use_rag = st.checkbox("Enable RAG Retrieval", value=True)
    top_k = st.slider("Top-K Documents", 1, 10, 5)

    st.subheader("Output Options")
    show_explain = st.checkbox("Tamil/English Explanation", value=True)
    show_iot = st.checkbox("MQTT/Node-RED Config", value=False)

    st.divider()
    st.subheader("📊 System Info")
    st.caption(f"Model: Phi-3-mini-4K-Instruct (Q4_0)")
    st.caption(f"Engine: llama.cpp")
    st.caption(f"Retrieval: FAISS + MiniLM-L6-v2")

    # Check if model exists
    if Path(model_path).exists():
        model_size_gb = Path(model_path).stat().st_size / (1024**3)
        st.success(f"Model loaded ({model_size_gb:.1f} GB)")
    else:
        st.warning("Model file not found")

    # Check if vector store exists
    if (SCRIPT_DIR / "docs_data" / "arduino_faiss.index").exists():
        st.success("FAISS index ready")
    else:
        st.info("FAISS index not built yet")
        if st.button("🔨 Build Index Now"):
            with st.spinner("Building knowledge base and vector index..."):
                try:
                    from scraper import ArduinoDocsScraper
                    from vector_store import ArduinoVectorStore
                    scraper = ArduinoDocsScraper()
                    scraper.build_knowledge_base()
                    store = ArduinoVectorStore()
                    store.build_index()
                    st.success("Index built!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Build failed: {e}")

# ── LLM Loading ──────────────────────────────────────────────────────
@st.cache_resource
def load_llm(model_path, n_threads):
    """Load the LLM model (cached)."""
    try:
        from llama_cpp import Llama
        llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_threads=n_threads,
            n_batch=512,
            use_mlock=True,
            verbose=False
        )
        return llm
    except Exception as e:
        return None

@st.cache_resource
def load_vector_store():
    """Load the vector store (cached)."""
    try:
        from vector_store import ArduinoVectorStore
        store = ArduinoVectorStore()
        if store.load_index():
            return store
    except Exception:
        pass
    return None


# ── Main Interface ───────────────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    prompt = st.text_area(
        "🎯 Describe your Arduino project:",
        placeholder="e.g., 'blink an LED on pin 13' or 'read DHT11 sensor and display temperature on I2C LCD'",
        height=100,
        key="prompt_input"
    )

with col2:
    st.markdown("**Quick Examples:**")
    examples = [
        "Blink LED on pin 13",
        "Read DHT11 temperature sensor",
        "Control servo with potentiometer",
        "Ultrasonic distance sensor HC-SR04",
        "I2C LCD display Hello World",
        "Motor control with L298N",
        "MQTT publish sensor data (ESP32)",
        "ISR button counter with interrupt",
    ]
    selected_example = st.selectbox("Pick an example:", [""] + examples)
    if selected_example:
        prompt = selected_example

generate_btn = st.button("✨ Generate Arduino Code", type="primary", use_container_width=True)

# ── Generation ───────────────────────────────────────────────────────
if generate_btn and prompt:
    llm = load_llm(model_path, n_threads)

    if llm is None:
        st.error("❌ Could not load the LLM model. Check the model path in the sidebar.")
    else:
        # RAG Retrieval
        rag_context = ""
        rag_docs_count = 0
        if use_rag:
            store = load_vector_store()
            if store:
                with st.spinner("🔍 Retrieving relevant Arduino docs..."):
                    results = store.search(prompt, top_k=top_k)
                    if results:
                        rag_docs_count = len(results)
                        context_parts = [f"[{r['category']}] {r['title']}:\n{r['content']}" for r in results]
                        rag_context = "\n\n---\n\n".join(context_parts)

        # Status bar
        cols = st.columns(3)
        with cols[0]:
            if rag_context:
                st.success(f"🟢 RAG Active: {rag_docs_count} docs retrieved")
            else:
                st.warning("🟡 RAG: No index / no results")
        with cols[1]:
            st.info(f"🧠 Model: Phi-3 Q4_0")
        with cols[2]:
            st.info(f"🔧 Threads: {n_threads}")

        # Generate code
        with st.spinner("⚡ Generating Arduino code..."):
            system_msg = """You are an expert Arduino code generator. Generate code that EXACTLY matches the request.
Rules: Use correct pins, include setup() and loop(), add inline comments, use simplest method.
"""
            if rag_context:
                system_msg += f"\nREFERENCE:\n{rag_context}\n"

            response = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"Generate complete Arduino code for: {prompt}"}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            code = response['choices'][0]['message']['content'].strip()
            if "```" in code:
                lines = code.split('\n')
                clean = [l for l in lines if not l.strip().startswith("```")]
                code = '\n'.join(clean).strip()

        # Tabs
        tabs = st.tabs(["📝 Code", "🔌 Connections", "📖 Explain (English/Tamil)", "📡 IoT Config"])

        with tabs[0]:
            st.code(code, language="cpp")
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button("⬇️ Download .ino", code, file_name="arduino_sketch.ino", mime="text/plain")
            with col_b:
                if st.button("📋 Copy to Clipboard"):
                    st.write("Code copied! (Use Ctrl+C on the code block above)")

        with tabs[1]:
            with st.spinner("Generating wiring instructions..."):
                help_response = llm.create_chat_completion(
                    messages=[
                        {"role": "system", "content": "You are an electronics expert. Provide clear Arduino wiring instructions with exact components and pin connections."},
                        {"role": "user", "content": f"Provide connection instructions for this Arduino code:\n```cpp\n{code}\n```"}
                    ],
                    max_tokens=400, temperature=0.3
                )
                help_text = help_response['choices'][0]['message']['content'].strip()
                st.markdown(help_text)

        with tabs[2]:
            if show_explain:
                with st.spinner("Generating bilingual explanation..."):
                    exp_response = llm.create_chat_completion(
                        messages=[
                            {"role": "system", "content": "You are a bilingual English/Tamil Arduino teacher. Explain code simply for students."},
                            {"role": "user", "content": f'Explain this Arduino code in English AND Tamil:\n```cpp\n{code}\n```\n\nFormat:\n**English:**\n...\n\n**Tamil (தமிழ்):**\n...'}
                        ],
                        max_tokens=400, temperature=0.3
                    )
                    explanation = exp_response['choices'][0]['message']['content'].strip()
                    st.markdown(explanation)
            else:
                st.info("Enable 'Tamil/English Explanation' in the sidebar to see bilingual explanations.")

        with tabs[3]:
            if show_iot:
                with st.spinner("Generating MQTT/Node-RED config..."):
                    iot_response = llm.create_chat_completion(
                        messages=[
                            {"role": "system", "content": "You are an IoT expert creating MQTT topics and Node-RED flows for Arduino projects."},
                            {"role": "user", "content": f"Generate MQTT topic structure and Node-RED flow JSON for this project: {prompt}.\nUse broker.emqx.io:1883 (free public broker)."}
                        ],
                        max_tokens=600, temperature=0.3
                    )
                    iot_text = iot_response['choices'][0]['message']['content'].strip()
                    st.markdown(iot_text)
            else:
                st.info("Enable 'MQTT/Node-RED Config' in the sidebar to generate IoT configurations.")

elif generate_btn and not prompt:
    st.warning("Please enter a description of your Arduino project.")

# ── Footer ───────────────────────────────────────────────────────────
st.divider()
st.markdown("""
<div style="text-align: center; color: #888; font-size: 12px;">
    <p>Arduino Co-Pilot v0.0.4 | Powered by Phi-3-mini (4-bit GGUF) + FAISS + llama.cpp</p>
    <p>Runs fully offline on CPU | Apache-2.0 License</p>
</div>
""", unsafe_allow_html=True)
