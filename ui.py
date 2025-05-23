import streamlit as st
from ollama_rag import rag_chain

st.title("Web RAG with Ollama")

# Use text_area for multi-line input
query = st.text_area("Ask a question:")

if st.button("Submit"):
    if query:
        answer = rag_chain(query)
        answer_content = answer.content
        # Use text_area or st.markdown to preserve newlines in the answer
        st.text_area("Answer", answer_content, height=300)
    else:
        st.warning("Please enter a question.")
