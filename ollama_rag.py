from langchain_ollama import ChatOllama
from content_crawler import rag_web_crawl
import copy

# Initialize Ollama LLM
llm = ChatOllama(model="llama3.1")

# Function to run RAG with Brave Search
def rag_chain(question):
    websearch_prompt = f"Design a web search query to find information about the following content in one line without any extra text. The content is: {question}"
    websearch = llm.invoke(websearch_prompt)
    # extract the query for websearch in brackets
    extract_prompt = f"Extract one web search query from the following text without any extra text: {websearch.content}"
    extract_query = llm.invoke(extract_prompt)
    websearch_query = extract_query.content
    # strip the words "web search query" from the string
    websearch_query = websearch_query.lower().replace("web search query", "")
    print("web search query:", websearch_query)
    rag_contexts = rag_web_crawl(websearch_query)
    context = "\n\n".join(rag_contexts)
    # Optionally, summarize or truncate results if too long
    
    prompt = f"Use the following web results to answer the question:\n\n{context}\n\nQuestion: {question}\nAnswer:"
    return llm.invoke(prompt)