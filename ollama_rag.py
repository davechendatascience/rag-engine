from langchain_community.tools import BraveSearch
from langchain_ollama import ChatOllama

# Initialize Brave Search tool
api_key = "XXXX"
search_tool = BraveSearch.from_api_key(api_key=api_key, search_kwargs={"count": 3})

# Initialize Ollama LLM
llm = ChatOllama(model="llama3.1")

# Function to run RAG with Brave Search
def rag_chain(question):
    websearch_prompt = f"Design a web search query to find information about {question} in one line without any extra text."
    websearch = llm.invoke(websearch_prompt)
    search_results = search_tool.run(websearch.content)
    websearch_context = search_results
    link_crawl_prompt = f"Use the following web search query to find relevant links: {websearch_context}"
    link_crawl = llm.invoke(link_crawl_prompt)
    # crawl links
    def find_links(text):
        # Extract links from the text
        return [line for line in text.split("\n") if line.startswith("http")]
    links = find_links(link_crawl.content)
    # get contents from links with beautifulsoup
    def get_content_from_link(link):
        # Use requests and BeautifulSoup to get the content from the link
        import requests
        from bs4 import BeautifulSoup
        response = requests.get(link)
        soup = BeautifulSoup(response.content, 'html.parser')
        return soup.get_text()
    
    webcontents = [websearch_context] + [get_content_from_link(link) for link in links]
    context = "\n\n".join(webcontents)
    # Optionally, summarize or truncate results if too long
    
    prompt = f"Use the following web results to answer the question:\n\n{context}\n\nQuestion: {question}\nAnswer:"
    return llm.invoke(prompt)