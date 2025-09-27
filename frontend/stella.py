import streamlit as st
import requests
import time
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_URL = "http://127.0.0.1:8001/analyze"
API_TIMEOUT = 60

# LLM Configuration for Streamlit
USE_OPENAI = os.getenv("USE_OPENAI", "true").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3-4b-2507")

if USE_OPENAI and OPENAI_API_KEY:
    from langchain_openai import ChatOpenAI
    frontend_llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)
elif not USE_OPENAI:
    from langchain_openai import ChatOpenAI
    frontend_llm = ChatOpenAI(
        model=LM_STUDIO_MODEL,
        base_url=LM_STUDIO_URL,
        api_key="not-needed"
    )
else:
    frontend_llm = None

# Page configuration
st.set_page_config(
    page_title="Stella - Financial AI Assistant",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Global Typography & Spacing Fixes */
    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        line-height: 1.4;
    }
    .stTextInput > div > div > input {
        font-size: 16px;
    }
    
    /* Chat Container: Scrollable with subtle shadow */
    .chat-container {
        max-height: 70vh;
        overflow-y: auto;
        padding: 1rem;
        background: linear-gradient(to bottom, #f8f9fa 0%, #ffffff 100%);
        border-radius: 0.5rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        width: 100%;
    }
    
    /* Native Chat Message Overrides: Reduce spacing, improve wrapping */
    .st-chat-message {
        margin-bottom: 0.75rem !important;
        padding: 0.5rem !important;
        width: 100% !important;
    }
    .st-chat-message > div {
        white-space: pre-wrap !important;
        overflow-wrap: break-word !important;
        word-break: break-word !important;
        hyphens: auto !important; /* Better hyphenation for long words */
        line-height: 1.5 !important; /* Slightly looser for readability */
        font-size: 14px !important;
        width: 100% !important;
    }
    
    /* User Message: Blue theme with better contrast */
    .user-message {
        background-color: #0b77d9 !important;
        color: #fff !important;
        border-radius: 0.75rem !important;
        border-left: 4px solid #095bb5 !important;
        box-shadow: 0 1px 3px rgba(11, 119, 217, 0.3);
        padding: 0.75rem !important;
        margin: 0.25rem 0 !important;
    }
    
    /* Assistant Message: Neutral with green accent */
    .assistant-message {
        background-color: #f8f9fa !important;
        color: #0b0b0b !important;
        border-radius: 0.75rem !important;
        border-left: 4px solid #4caf50 !important;
        box-shadow: 0 1px 3px rgba(76, 175, 80, 0.1);
        padding: 0.75rem !important;
        margin: 0.25rem 0 !important;
    }
    
    /* Enhance headings inside assistant messages */
    .assistant-message h1, .assistant-message h2, .assistant-message h3, .assistant-message h4 {
        color: #2c3e50 !important;
        font-weight: bold !important;
        margin-top: 1rem !important;
        margin-bottom: 0.5rem !important;
        line-height: 1.2 !important;
    }
    .assistant-message h2 {
        font-size: 1.3em !important;
        border-bottom: 2px solid #4caf50 !important;
        padding-bottom: 0.25rem !important;
    }
    .assistant-message ul, .assistant-message ol {
        margin: 0.5rem 0 !important;
        padding-left: 1.5rem !important;
    }
    .assistant-message li {
        margin-bottom: 0.25rem !important;
    }
    
    
    /* Sidebar Polish: Compact examples */
    .task-examples {
        background-color: #e3f2fd !important;
        padding: 0.75rem !important;
        border-radius: 0.5rem;
        border-left: 4px solid #0b77d9;
        font-size: 0.9rem;
        line-height: 1.3;
    }
    
    /* Dark Mode Compatibility */
    @media (prefers-color-scheme: dark) {
        .chat-container { background: linear-gradient(to bottom, #2d2d2d 0%, #1e1e1e 100%); }
        .assistant-message { background-color: #3a3a3a !important; color: #e0e0e0 !important; }
        .assistant-message h1, .assistant-message h2, .assistant-message h3, .assistant-message h4 { color: #ecf0f1 !important; }
        .assistant-message h2 { border-bottom-color: #4caf50 !important; }
        .user-message { background-color: #1e40af !important; }
        .task-examples { background-color: #1e3a5f !important; }
    }
    
    /* Reduce Streamlit defaults */
    .css-1d391kg, .css-10trblm { background-color: transparent !important; }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "use_llm_processing" not in st.session_state:
        st.session_state.use_llm_processing = True

def call_stella_api(query: str, chat_history: List[Dict]) -> Optional[str]:
    """Call the Stella API and return the response"""
    try:
        payload = {
            "query": query,
            "source": "web",
            "chat_history": chat_history
        }

        with st.spinner("Stella is analyzing..."):
            response = requests.post(API_URL, json=payload, timeout=API_TIMEOUT)
            response.raise_for_status()

        data = response.json()
        return data.get("result", "No response received")

    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to Stella API. Please ensure the FastAPI server is running on http://127.0.0.1:8001")
        return None
    except requests.exceptions.Timeout:
        st.error("Request timed out. Try a simpler query.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP Error: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None

def process_response_with_llm(raw_response: str, user_query: str) -> str:
    """Process the raw Stella response with LLM to make it more user-friendly"""
    if not frontend_llm or not st.session_state.use_llm_processing:
        return raw_response

    try:
        from langchain.prompts import PromptTemplate

        prompt = PromptTemplate.from_template(
            """You are a helpful financial assistant. The user asked: "{query}"

            Here's the raw response from our financial analysis system:
            {response}

            Please reformat this response to be more user-friendly and conversational. Keep all the important information but:
            - Use natural, conversational language
            - Organize information with clear headings (e.g., ## Heading) and bullet points (e.g., - Item) where appropriate
            - Ensure every line has proper line breaks for readability—avoid run-on sentences
            - Remove any technical artifacts or formatting issues
            - Make it easy to read and understand, with short paragraphs
            - Keep financial data accurate and precise
            - If it's a list or structured data, present it in a readable Markdown format
            - Start directly with the content—no introductory phrases like 'Sure!', 'Here's...', or descriptions of the format. Jump straight into the key information.

            Respond directly to the user as if you're the financial assistant, diving right into the response without any setup."""
        )

        processed_response = frontend_llm.invoke(
            prompt.format(query=user_query, response=raw_response)
        ).content

        return processed_response

    except Exception as e:
        st.warning(f"Could not process response with LLM: {e}. Showing raw response.")
        return raw_response

def display_chat_history():
    """Display the chat history using native st.chat_message for better UX"""
    if not st.session_state.messages:
        st.info("💬 Start chatting about stocks, companies, or financial news below!")
        return

    # Scrollable chat container
    with st.container():
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                if message["role"] == "user":
                    st.markdown(message["content"], unsafe_allow_html=True)
                else:
                    st.markdown(message["content"])
                st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Reliable auto-scroll
        st.markdown("""
            <script>
            const chatContainer = document.querySelector('.chat-container');
            if (chatContainer) {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            </script>
        """, unsafe_allow_html=True)

def main():
    initialize_session_state()

    with st.sidebar:
        st.title("Stella")
        st.markdown("---")

        st.markdown("### 💡 Quick Examples")
        st.markdown("""
        <div class="task-examples">
        <strong>Stock Analysis:</strong><br>
        • "Generate a stock report for Tesla"<br>
        • "Overview of Microsoft"<br>
        • "Latest news on Apple"<br>
        • "Today's update on Tesla, Apple"<br><br>
        <strong>News & Follow-ups:</strong><br>
        • "Latest AI news"<br>
        • "More on Nvidia's AI chips"<br>
        • "Explain Tesla's new model"
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🔧 Status")
        try:
            response = requests.get("http://127.0.0.1:8001/docs", timeout=5)
            st.success("API Connected")
        except:
            st.error("API Not Reachable")
            st.info("Run: `uvicorn app:app --host 127.0.0.1 --port 8001`")

        st.markdown("### Enhancements")
        st.session_state.use_llm_processing = st.toggle(
            "Use LLM for Response Polish", 
            value=st.session_state.use_llm_processing, 
            key="llm_processing_toggle"
        )
        if frontend_llm and st.session_state.use_llm_processing:
            st.success("LLM Active")
        elif frontend_llm:
            st.info("LLM Ready – Toggle above to enable")
        else:
            st.warning("Configure LLM")

        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_history = []
            st.rerun()

    # Main Area: Cleaner header
    st.title("Your AI Assistant")
    st.caption("Ask about stocks, companies, and financial news – I'll handle the analysis!")

    # Display chat
    display_chat_history()

    # Bottom Input:
    if prompt := st.chat_input("Enter your query (e.g., 'Latest news on Meta')"):
        timestamp = time.strftime("%H:%M:%S")
        
        # Add user message immediately
        with st.chat_message("user"):
            st.markdown(f'<div class="message-timestamp">{timestamp}</div><div class="user-message">{prompt}</div>', unsafe_allow_html=True)
        
        st.session_state.messages.append({"role": "user", "content": prompt, "timestamp": timestamp})

        # Call API and process
        with st.chat_message("assistant"):
            response = call_stella_api(prompt, st.session_state.chat_history)
            if response:
                processed_response = process_response_with_llm(response, prompt)
                assistant_timestamp = time.strftime("%H:%M:%S")
                st.markdown(f'<div class="message-timestamp">{assistant_timestamp}</div><div class="assistant-message">', unsafe_allow_html=True)
                st.markdown(processed_response)
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.session_state.messages.append({"role": "assistant", "content": processed_response, "timestamp": assistant_timestamp})
                st.session_state.chat_history.append({
                    "query": prompt,
                    "response": response,
                    "timestamp": time.time()
                })
                if len(st.session_state.chat_history) > 10:
                    st.session_state.chat_history = st.session_state.chat_history[-10:]
            else:
                st.error("Failed to get response. Check the sidebar status.")

        st.rerun()

if __name__ == "__main__":
    main()