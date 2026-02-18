"""
Arduino Co-Pilot - Setup Script
Builds the knowledge base, FAISS index, and verifies all components.
Run this once after installation.
"""
import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))


def check_dependencies():
    """Check that all required packages are installed."""
    print("\n=== Checking Dependencies ===\n")
    required = {
        'llama_cpp': 'llama-cpp-python',
        'faiss': 'faiss-cpu',
        'sentence_transformers': 'sentence-transformers',
        'numpy': 'numpy',
        'bs4': 'beautifulsoup4',
        'requests': 'requests',
        'streamlit': 'streamlit',
    }

    missing = []
    for module, package in required.items():
        try:
            __import__(module)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - NOT INSTALLED")
            missing.append(package)

    if missing:
        print(f"\n  Missing packages: {', '.join(missing)}")
        print(f"  Install with: pip install {' '.join(missing)}")
        return False

    print("\n  All dependencies satisfied!")
    return True


def check_model():
    """Check that the LLM model file exists."""
    print("\n=== Checking Model ===\n")
    model_path = SCRIPT_DIR / "Phi-3-mini-4k-instruct.Q4_0.gguf"
    if model_path.exists():
        size_gb = model_path.stat().st_size / (1024**3)
        print(f"  ✅ Model found: {model_path.name} ({size_gb:.1f} GB)")
        return True
    else:
        print(f"  ❌ Model not found at: {model_path}")
        print(f"  Download from: https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf")
        return False


def build_knowledge_base():
    """Build the Arduino knowledge base."""
    print("\n=== Building Knowledge Base ===\n")
    from scraper import ArduinoDocsScraper
    scraper = ArduinoDocsScraper(output_dir=str(SCRIPT_DIR / "docs_data"))
    docs = scraper.build_knowledge_base()
    return len(docs) > 0


def build_vector_index():
    """Build the FAISS vector index."""
    print("\n=== Building Vector Index ===\n")
    from vector_store import ArduinoVectorStore
    store = ArduinoVectorStore(data_dir=str(SCRIPT_DIR / "docs_data"))
    return store.build_index()


def test_rag_search():
    """Test the RAG search pipeline."""
    print("\n=== Testing RAG Search ===\n")
    from vector_store import ArduinoVectorStore
    store = ArduinoVectorStore(data_dir=str(SCRIPT_DIR / "docs_data"))

    queries = ["blink LED", "servo motor", "I2C LCD", "PWM Arduino Uno"]
    for q in queries:
        results = store.search(q, top_k=3)
        print(f"  Query: '{q}'")
        for r in results:
            print(f"    [{r['score']:.3f}] {r['title']}")
        print()

    return True


def test_llm():
    """Quick test of the LLM."""
    print("\n=== Testing LLM ===\n")
    try:
        from llama_cpp import Llama
        model_path = str(SCRIPT_DIR / "Phi-3-mini-4k-instruct.Q4_0.gguf")
        llm = Llama(model_path=model_path, n_ctx=512, n_threads=4, verbose=False)
        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": "You are an Arduino expert. Reply briefly."},
                {"role": "user", "content": "What pin is LED_BUILTIN on Arduino Uno?"}
            ],
            max_tokens=50, temperature=0.1
        )
        answer = response['choices'][0]['message']['content'].strip()
        print(f"  Test query: 'What pin is LED_BUILTIN on Arduino Uno?'")
        print(f"  Response: {answer}")
        print(f"  ✅ LLM working!")
        return True
    except Exception as e:
        print(f"  ❌ LLM test failed: {e}")
        return False


def main():
    print("=" * 60)
    print("  Arduino Co-Pilot - Setup")
    print("=" * 60)

    steps = [
        ("Checking dependencies", check_dependencies),
        ("Checking model", check_model),
        ("Building knowledge base", build_knowledge_base),
        ("Building vector index", build_vector_index),
        ("Testing RAG search", test_rag_search),
        ("Testing LLM", test_llm),
    ]

    results = {}
    for name, func in steps:
        try:
            results[name] = func()
        except Exception as e:
            print(f"\n  ❌ {name} failed: {e}")
            results[name] = False

    # Summary
    print("\n" + "=" * 60)
    print("  Setup Summary")
    print("=" * 60)
    all_pass = True
    for name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_pass = False

    if all_pass:
        print(f"\n  🎉 Setup complete! All systems operational.")
        print(f"\n  To run:")
        print(f"    VS Code Extension: Press F5 in VS Code")
        print(f"    Streamlit Demo:    streamlit run app.py")
        print(f"    CLI:               python copilot_runner.py \"blink LED on pin 13\"")
    else:
        print(f"\n  ⚠️  Some steps failed. Fix the issues above and re-run setup.")

    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
