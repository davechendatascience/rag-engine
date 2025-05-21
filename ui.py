import streamlit as st
from ollama_rag import rag_chain

st.title("Web RAG with Ollama")

query = st.text_input("Ask a question:")

if st.button("Submit"):
    if query:
        answer = rag_chain(query)
        answer_content = answer.content
        st.write(answer_content)
    else:
        st.warning("Please enter a question.")
