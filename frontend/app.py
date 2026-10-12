import streamlit as st
import json
import requests
import math
from pathlib import Path
import streamlit.components.v1 as components
import os
import io
import hashlib
import subprocess
import tempfile
import speech_recognition as sr
try:
    from streamlit_mic_recorder import mic_recorder
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False


# ==========================================================


def render_speech_controls(text, key="nyaya-speech"):
    """Play an assistant response using the browser's speech engine."""
    spoken_text = json.dumps(str(text)).replace("<", "\\u003c")
    components.html(
        f"""
        <div style="display:flex;gap:8px;font-family:Arial,sans-serif">
          <button onclick="speakAnswer()"
            style="padding:8px 14px;border:0;border-radius:9px;
            background:#273449;color:white;cursor:pointer">
            🔊 Listen
          </button>
          <button onclick="stopAnswer()"
            style="padding:8px 14px;border:1px solid #64748b;
            border-radius:9px;background:transparent;
            color:inherit;cursor:pointer">
            ⏹ Stop
          </button>
        </div>
        <script>
          const answerText = {spoken_text};
          function speakAnswer() {{
            if (!('speechSynthesis' in window)) {{
              alert('Speech playback is not supported in this browser.');
              return;
            }}
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(answerText);
            utterance.lang = 'en-IN';
            window.speechSynthesis.speak(utterance);
          }}
          function stopAnswer() {{
            if ('speechSynthesis' in window) window.speechSynthesis.cancel();
          }}
        </script>
        """,
        height=52,
    )


# SESSION STATE INITIALIZATION
# ==========================================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "document_profile" not in st.session_state:
    st.session_state.document_profile = None
if "document_uploaded" not in st.session_state:
    st.session_state.document_uploaded = False
if "document_name" not in st.session_state:
    st.session_state.document_name = ""
if "search_mode" not in st.session_state:
    st.session_state.search_mode = "Indian Laws"
if "language" not in st.session_state:
    st.session_state.language = "English"
ANSWER_LANGUAGES = [
    "English",
    "Hindi",
    "Tamil",
    "Telugu",
    "Bengali",
    "Marathi",
    "Kannada",
    "Malayalam",
    "Gujarati",
    "Punjabi",
]
if "triggered_prompt" not in st.session_state:
    st.session_state.triggered_prompt = None

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

# Attempt to load dynamic config as requested, with fallbacks
try:
    from backend.utils.config import OLLAMA_MODEL, EMBEDDING_MODEL, RETRIEVAL_STRATEGY
except ImportError:
    OLLAMA_MODEL = "Llama3"
    EMBEDDING_MODEL = "MiniLM"
    RETRIEVAL_STRATEGY = "Hybrid"

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="NyayaAI | Legal Assistant", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
:root { color-scheme: dark; }
.stApp {
  background: radial-gradient(ellipse at top left, #14283a 0%, #0b1220 45%, #080d17 100%);
  color: #e5edf7;
}
[data-testid="stSidebar"] {
  background: linear-gradient(180deg,#101d2d,#0a111d);
  border-right: 1px solid #25364b;
}
.block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem; }
h1,h2,h3 { letter-spacing: -0.035em; }
h1 { color:#f3f7fc; }
h2,h3 { color:#dbeafe; }
p, label, .stMarkdown { color:#d3deec; }
div[data-testid="stMetric"] {
  background:#111e2e; border:1px solid #2a3b51;
  padding:16px; border-radius:14px;
}
div[data-testid="stChatMessage"] {
  border:1px solid #26384e; border-radius:16px;
  padding:14px; margin-bottom:12px;
  background:rgba(16,29,45,.82);
}
.stButton button, .stDownloadButton button {
  border-radius:10px; border:1px solid #38536e;
  transition:all .15s ease;
}
.stButton button[kind="primary"] {
  background:linear-gradient(135deg,#0f766e,#0e7490);
  border:0; color:white;
}
.stButton button:hover { border-color:#5eead4; color:white; }
div[data-testid="stExpander"] {
  border:1px solid #2a3b51; border-radius:12px;
}
div[data-testid="stFileUploader"] {
  background:#111e2e; border:1px dashed #3b526d;
  border-radius:12px; padding:8px;
}
.nyaya-hero {
  padding:30px; border-radius:22px; margin-bottom:20px;
  background:linear-gradient(120deg,rgba(15,118,110,.25),rgba(30,64,110,.25));
  border:1px solid #2b5260;
}
.nyaya-kicker {
  color:#5eead4; font-size:.8rem; font-weight:700;
  letter-spacing:.16em; text-transform:uppercase;
}
.nyaya-muted { color:#9fb2c8; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# CONFIG & STATE INITIALIZATION
# ==========================================
API_BASE_URL = "http://localhost:8000"
UPLOAD_URL = f"{API_BASE_URL}/upload"
ASK_URL = f"{API_BASE_URL}/ask"

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def calculate_relevance(raw_score):
    try:
        return 1 / (1 + math.exp(-float(raw_score)))
    except OverflowError:
        return 0.0 if float(raw_score) < 0 else 1.0

def get_relevance_details(conf):
    if conf >= 0.75:
        return "High 🟢"
    elif conf >= 0.5:
        return "Medium 🟡"
    else:
        return "Low 🔴"

def clear_chat():
    st.session_state.messages = []

def count_items(field_data):
    if isinstance(field_data, list):
        return len(field_data)
    elif isinstance(field_data, str) and field_data.strip():
        return len([x for x in field_data.split('\n') if x.strip()])
    return 0

def render_sources(sources):
    if not sources:
        return
        
    with st.expander("📚 Legal Sources", expanded=False):
        for idx, source in enumerate(sources):
            conf = calculate_relevance(source.get("score", 0.0))
            label = get_relevance_details(conf)
            
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns(4)
                col1.markdown(f"**Law:** {source.get('law', 'N/A')}")
                col2.markdown(f"**Section:** {source.get('section', 'N/A')}")
                col3.markdown(f"**Page:** {source.get('page', 'N/A')}")
                col4.markdown(f"**Relevance:** {label} ({conf:.2%})")
                
                st.markdown("**Retrieved Context:**")
                st.info(source.get("context", "Context details unavailable."))

def generate_case_brief_pdf(doc_name, summary, profile):
    if not HAS_FPDF:
        error_text = f"FPDF dependency missing.\n\nSUMMARY:\n{summary}\n\nFACTS:\n{profile.get('facts', 'N/A')}"
        return error_text.encode('utf-8')
        
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "AI CASE BRIEF", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Document: {doc_name}", ln=True, align='C')
    pdf.ln(10)
    
    sections = [
        ("SUMMARY", summary),
        ("FACTS", profile.get("facts", "N/A")),
        ("ISSUES", profile.get("issues", "N/A")),
        ("ARGUMENTS", profile.get("arguments", "N/A")),
        ("REASONING", profile.get("reasoning", "N/A")),
        ("DECISION", profile.get("decision", "N/A")),
        ("ENTITIES", profile.get("people", "N/A")),
        ("DATES", profile.get("dates", "N/A")),
        ("LEGAL REFERENCES", profile.get("important_sections", profile.get("citations", "N/A"))),
        ("IMPORTANT DATES", profile.get("important_dates", profile.get("dates", []))),
        ("OBLIGATIONS", profile.get("obligations", profile.get("demands_or_actions", []))),
        ("RESPONSE DEADLINE", profile.get("response_deadline", "Not specified")),
        ("POTENTIAL CONCERNS", profile.get("potential_concerns", [])),
        ("LAWYER REVIEW POINTS", profile.get("review_points", []))
    ]
    
    for title, content in sections:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"[ {title} ]", ln=True)
        pdf.set_font("Arial", '', 11)
        safe_content = str(content).encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 7, safe_content)
        pdf.ln(5)
        
    try:
        val = pdf.output(dest='S')
        return val.encode('latin-1') if isinstance(val, str) else bytes(val)
    except Exception:
        return bytes(pdf.output())

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.title("⚖️ NyayaAI")
    st.divider()

    st.subheader("Search Database")
    st.session_state.search_mode = st.radio(
        "Search Database",
        options=["Indian Laws", "Uploaded Document"],
        index=["Indian Laws", "Uploaded Document"].index(st.session_state.search_mode),
        key="search_mode_radio",
        label_visibility="collapsed"
    )

    st.session_state.language = st.selectbox(
        "Answer language",
        options=ANSWER_LANGUAGES,
        index=ANSWER_LANGUAGES.index(st.session_state.language),
        key="answer_language",
    )

    st.divider()
    st.subheader("Upload PDF")
    
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
    
    if st.button("Upload & Analyze", type="primary", use_container_width=True) and uploaded_file is not None:
        with st.status("Processing PDF...", expanded=True) as status:
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                response = requests.post(UPLOAD_URL, files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        st.session_state.document_profile = data
                        st.session_state.search_mode = "Uploaded Document"
                        st.session_state.document_uploaded = True
                        st.session_state.document_name = uploaded_file.name
                        
                        status.update(label="Analysis Complete", state="complete", expanded=False)
                        st.success("✓ Uploaded Successfully")
                        
                        st.markdown(f"""
                        **Document:** {uploaded_file.name}
                        
                        **Type:** {data.get('document_type', 'Document')}
                        
                        **Pages:** {data.get('pages', 0)}
                        
                        **Chunks:** {data.get('chunks', 0)}
                        """)
                    else:
                        status.update(label="Processing failed", state="error")
                        st.error("Failed to parse the PDF text.")
                else:
                    status.update(label="API Error", state="error")
                    st.error(f"Server Error {response.status_code}: {response.text}")
            except requests.exceptions.ConnectionError:
                status.update(label="Backend Offline", state="error")
                st.error("Cannot connect to the NyayaAI backend. Make sure FastAPI is running on localhost:8000.")
            except Exception as e:
                status.update(label="System Error", state="error")
                st.error(f"Error: {e}")

    st.divider()
    st.button("🗑️ Clear Chat", use_container_width=True, on_click=clear_chat)

# ==========================================
# MAIN PAGE HEADER & WORKSPACE
# ==========================================

# Home Page (Empty State)
if not st.session_state.messages and not st.session_state.document_profile:
    st.markdown("""
    <div class="nyaya-hero">
      <div class="nyaya-kicker">Legal intelligence workspace</div>
      <h1>NyayaAI</h1>
      <p>Research Indian law. Understand legal documents. Explore answers with sources.</p>
      <div class="nyaya-muted">BNS · BNSS · BSA · Constitution of India</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    
    col1, col2, col3 = st.columns([1, 0.2, 1])
    with col1:
        st.markdown("### 📄 Upload a legal PDF")
        st.write("Extract facts, issues, and reasoning automatically using AI.")
    
    with col2:
        st.markdown("<h3 style='text-align:center; color:#64748B;'>OR</h3>", unsafe_allow_html=True)
        
    with col3:
        st.markdown("### 🔍 Search Indian Laws")
        st.write("Ask natural language legal questions across Indian databases.")
        
    st.divider()
    
    st.markdown("### Supported Documents")
    st.markdown("""
    * ✓ Court Judgments
    * ✓ Constitution
    * ✓ BNS
    * ✓ BNSS
    * ✓ BSA
    """)

else:
    # Active Workspace Header
    st.header("⚖️ NyayaAI")
    st.markdown("##### AI-Powered Indian Legal Research & Document Analysis Platform")

with st.expander("Find a Lawyer — Demo Directory", expanded=False):
    st.warning(
        "Fictional demo profiles and illustrative photos only. Contact details "
        "are placeholders; replace them with verified information before publishing."
    )
    demo_lawyers = [
        {
            "name": "Advocate Demo One",
            "practice": "Civil Law",
            "phone": "+91 94542 32111",
            "photo": "advocate_civil.svg",
        },
        {
            "name": "Advocate Demo Two",
            "practice": "Criminal Law",
            "phone": "+91 98765 43210",
            "photo": "advocate_criminal.svg",
        },
        {
            "name": "Advocate Demo Three",
            "practice": "Family Law",
            "phone": "+91 99922 91231",
            "photo": "advocate_family.svg",
        },
        {
            "name": "Advocate Demo Four",
            "practice": "Property Law",
            "phone": "+91 88888 12345",
            "photo": "advocate_property.svg",
        },
    ]
    for lawyer in demo_lawyers:
        photo_column, details_column = st.columns([1, 4])
        with photo_column:
            photo_path = Path(__file__).parent / "assets" / lawyer["photo"]
            st.markdown(
                photo_path.read_text(encoding="utf-8"),
                unsafe_allow_html=True,
            )
        with details_column:
            st.markdown(f"### {lawyer['practice']} Advocate")
            st.write(f"**{lawyer['name']}** — {lawyer['phone']} (placeholder)")

# Active Workspace Metrics
if st.session_state.messages or st.session_state.document_profile:
    st.divider()
    st.subheader("Workspace")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Mode", st.session_state.search_mode)
    col2.metric("LLM", OLLAMA_MODEL)
    col3.metric("Embedding", EMBEDDING_MODEL)
    col4.metric("Retrieval", RETRIEVAL_STRATEGY)
    col5.metric("Status", "Active")

# ==========================================
# DOCUMENT ANALYSIS DASHBOARD
# ==========================================
if st.session_state.document_profile:
    doc_data = st.session_state.document_profile
    profile = doc_data.get("profile", {})
    
    st.divider()
    st.subheader("Document Overview")
    
    with st.container(border=True):
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("File Name", doc_data.get('document', 'N/A'))
        m2.metric("Type", doc_data.get('document_type', 'N/A'))
        m3.metric("Court", profile.get('court', 'N/A'))
        m4.metric("Judge", profile.get('judge', 'N/A'))
        m5.metric("Case No.", profile.get('case_number', 'N/A'))

    with st.container(border=True):
        s1, s2, s3, s4, s5, s6 = st.columns(6)
        s1.metric("Pages", doc_data.get("pages", 0))
        s2.metric("Chunks", doc_data.get("chunks", 0))
        s3.metric("Issues", count_items(profile.get("issues", "")))
        s4.metric("Entities", count_items(profile.get("people", "")))
        s5.metric("Dates", count_items(profile.get("dates", "")))
        s6.metric("References", count_items(profile.get("important_sections", profile.get("citations", profile.get("articles", "")))))

    brief_tabs = st.tabs([
        "Summary", 
        "Facts", 
        "Issues", 
        "Arguments", 
        "Reasoning", 
        "Decision",
        "Citations"
    ])
    
    with brief_tabs[0]:
        st.write(doc_data.get("summary", "No summary available."))
    with brief_tabs[1]:
        st.write(profile.get("facts", "N/A"))
    with brief_tabs[2]:
        st.write(profile.get("issues", "N/A"))
    with brief_tabs[3]:
        st.write(profile.get("arguments", "N/A"))
    with brief_tabs[4]:
        st.write(profile.get("reasoning", "N/A"))
    with brief_tabs[5]:
        st.success(profile.get("decision", "No ruling available."))
    with brief_tabs[6]:
        st.write(profile.get("important_sections", profile.get("citations", profile.get("articles", "No explicit reference extracted."))))
        
    # Enhanced legal document findings
    st.divider()
    st.subheader("Additional Legal Findings")

    finding_tabs = st.tabs([
        "Important Dates",
        "Obligations / Demands",
        "Potential Concerns",
        "Lawyer Review Points",
    ])

    with finding_tabs[0]:
        dates = profile.get("important_dates", [])
        if profile.get("response_deadline"):
            dates = list(dates) if isinstance(dates, list) else [dates]
            dates.append({"date": profile["response_deadline"], "context": "Response deadline"})
        if dates:
            for item in dates if isinstance(dates, list) else [dates]:
                st.write(item)
        else:
            st.info("No important dates were extracted from this document.")

    with finding_tabs[1]:
        items = profile.get("obligations", profile.get("demands_or_actions", []))
        if items:
            for item in items if isinstance(items, list) else [items]:
                st.write(item)
        else:
            st.info("No obligations or demands were extracted.")

    with finding_tabs[2]:
        concerns = profile.get("potential_concerns", [])
        if concerns:
            for item in concerns if isinstance(concerns, list) else [concerns]:
                st.warning(str(item))
        else:
            st.info("No potential concerns were identified by the analyzer.")

    with finding_tabs[3]:
        points = profile.get("review_points", [])
        if points:
            for item in points if isinstance(points, list) else [points]:
                st.write(item)
        else:
            st.info("No additional review points were extracted.")

    st.caption(
        "AI-generated findings are preliminary and may omit context. "
        "Verify important dates and obligations against the original document "
        "and consult a qualified lawyer for legal advice."
    )

    doc_name_clean = doc_data.get('document', 'Document').replace('.pdf', '')
    pdf_bytes = generate_case_brief_pdf(doc_name_clean, doc_data.get('summary', ''), profile)
    
    st.download_button(
        label="📄 Download AI Case Brief", 
        data=pdf_bytes, 
        file_name=f"{doc_name_clean}_Case_Brief.pdf", 
        mime="application/pdf"
    )

# ==========================================
# SUGGESTED QUESTIONS
# ==========================================
if st.session_state.document_profile or not st.session_state.messages:
    if not st.session_state.messages and st.session_state.document_profile:
        st.divider()
        st.markdown("**Suggested Questions**")
        
        doc_type_upper = st.session_state.document_profile.get("document_type", "UNKNOWN").upper().replace(" ", "_")
            
        if doc_type_upper == "COURT_JUDGMENT":
            suggestions = [
                "Why did the court reach this decision?",
                "Who won?",
                "Summarize this judgement",
                "Key legal issues",
                "Sections cited"
            ]
        elif doc_type_upper == "CONSTITUTION":
            suggestions = ["Explain this Article", "Summarize this Article", "What are the key rights?"]
        elif doc_type_upper in ["CONTRACT", "AGREEMENT"]:
            suggestions = ["Summarize the Termination Clause", "What are the primary obligations?", "Is there an Arbitration Clause?"]
        else:
            suggestions = ["Summarize this document", "What are the main actionable points?", "Identify key entities"]

        sug_cols = st.columns(len(suggestions))
        for idx, suggestion in enumerate(suggestions):
            if sug_cols[idx].button(f"✨ {suggestion}", use_container_width=True):
                st.session_state.triggered_prompt = suggestion
                st.rerun()

# ==========================================
# CHAT INTERFACE
# ==========================================
if st.session_state.messages or st.session_state.document_profile:
    st.divider()
    st.subheader("Legal Assistant")

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(msg["content"])
                render_speech_controls(msg["content"], key="history-" + str(len(st.session_state.messages)))
                if "sources" in msg and msg["sources"]:
                    render_sources(msg["sources"])

# ==========================================
# CHAT INPUT & EXECUTION
# ==========================================

voice_text = None

if VOICE_AVAILABLE:
    with st.expander("🎙️ Ask by voice", expanded=False):
        st.caption("Click Start recording, speak, then stop recording.")

        audio = mic_recorder(
            start_prompt="Start recording",
            stop_prompt="Stop recording",
            key="nyaya_voice_input",
        )

        if audio and audio.get("bytes"):
            audio_bytes = audio["bytes"]
            audio_hash = hashlib.sha256(audio_bytes).hexdigest()

            if audio_hash != st.session_state.get("last_voice_audio_hash"):
                st.session_state["last_voice_audio_hash"] = audio_hash

                try:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        webm_path = os.path.join(temp_dir, "recording.webm")
                        wav_path = os.path.join(temp_dir, "recording.wav")

                        with open(webm_path, "wb") as f:
                            f.write(audio_bytes)

                        subprocess.run(
                            [
                                "/opt/homebrew/bin/ffmpeg",
                                "-y", "-i", webm_path,
                                "-ac", "1", "-ar", "16000",
                                wav_path,
                            ],
                            check=True,
                            capture_output=True,
                            text=True,
                        )

                        recognizer = sr.Recognizer()
                        with sr.AudioFile(wav_path) as source:
                            recording = recognizer.record(source)

                        voice_text = recognizer.recognize_google(
                            recording, language="en-IN"
                        )

                    if voice_text:
                        st.success(f"Recognized: {voice_text}")
                        st.session_state["voice_prompt"] = voice_text

                except sr.UnknownValueError:
                    st.warning("Speech wasn't clear. Please try again.")
                except sr.RequestError as exc:
                    st.error(f"Speech recognition service error: {exc}")
                except subprocess.CalledProcessError:
                    st.error("Audio conversion failed.")
                except Exception as exc:
                    st.error(f"Voice input error: {exc}")


user_input = st.chat_input("Ask a legal question...")

voice_prompt = st.session_state.pop("voice_prompt", None)

if voice_prompt:
    st.session_state.triggered_prompt = voice_prompt
    st.rerun()

prompt = st.session_state.triggered_prompt or user_input

if prompt:
    if st.session_state.triggered_prompt:
        st.session_state.triggered_prompt = None

    if st.session_state.search_mode == "Uploaded Document" and not st.session_state.document_profile:
        st.warning("⚠️ Please upload a PDF first to search within a document.")
    else:
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            answer = None
            sources = []

            with st.status("Generating answer...", expanded=True) as chat_status:
                try:
                    mode = (
                        "permanent"
                        if st.session_state.search_mode == "Indian Laws"
                        else "dynamic"
                    )

                    payload = {
                        "question": prompt,
                        "mode": mode,
                        "language": st.session_state.language,
                    }

                    response = requests.post(
                        ASK_URL,
                        json=payload,
                        timeout=180,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        answer = data.get("answer", "No response generated.")
                        sources = data.get("sources", [])
                        chat_status.update(
                            label="Analysis Complete",
                            state="complete",
                            expanded=False,
                        )
                    else:
                        chat_status.update(label="API Error", state="error")
                        st.error(
                            f"Error {response.status_code}: {response.text}"
                        )

                except requests.exceptions.ConnectionError:
                    chat_status.update(label="Backend Offline", state="error")
                    st.error(
                        "Cannot connect to NyayaAI. Ensure FastAPI is running "
                        "on localhost:8000."
                    )

                except requests.exceptions.Timeout:
                    chat_status.update(label="Request timed out", state="error")
                    st.error("The request took too long. Please try again.")

                except Exception as exc:
                    chat_status.update(label="Error", state="error")
                    st.error(f"An error occurred: {exc}")

            if answer:
                st.markdown(answer)
                render_speech_controls(answer, key="latest-answer")
                render_sources(sources)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                })



# ==========================================
# FOOTER
# ==========================================
if st.session_state.messages or st.session_state.document_profile:
    st.divider()
    foot_col1, foot_col2, foot_col3 = st.columns([2, 1, 2])
    with foot_col2:
        st.caption("**NyayaAI Enterprise Legal Intelligence**")
        st.caption("Version 1.0 • Stable Release Workflow")
        st.caption("FastAPI • Streamlit • ChromaDB • Ollama • Hybrid Retrieval • Cross Encoder")
