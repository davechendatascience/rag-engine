# content-crawler.py (Main Orchestrator)

import argparse
import time
import re # For processing LeetCode query terms
import json

# Adapter imports
from wikipedia_adapter import crawl_wikipedia_topic, normalize_wiki_link as normalize_wiki_link_wikipedia
from leetcode_adapter import run_leetcode_adapter, format_leetcode_data_to_markdown
from langchain_community.tools import BraveSearch

# Initialize Brave Search tool
api_key = "BSAJ4SpjbW9xCJCyb69qU_EqEmyJXhG"
search_tool = BraveSearch.from_api_key(api_key=api_key, search_kwargs={"count": 3})

def rag_web_crawl(query_string):
    """Main orchestrator function."""
    # Default parameters
    seed_page_domain = "https://en.wikipedia.org/wiki/"
    to_crawl_levels = 2
    pause_seconds = 2
    to_print_levels = 2
    top_k = 5
    top_content_links = 3
    
    domain_to_target = "wikipedia" # Default
    processed_query_for_adapter = query_string 

    if "leetcode" in query_string.lower():
        domain_to_target = "leetcode"
        # Try to extract a more specific query for LeetCode
        # Remove "leetcode" (case-insensitive) and common joining words like "problem"
        temp_lc_query = re.sub(r'leetcode\s*(problem)?', '', query_string, flags=re.IGNORECASE).strip()
        # If the result is empty (e.g., query was just "leetcode"), use the original query for the adapter
        # or a part of it if it makes sense. For now, if empty, might indicate just "leetcode" was searched.
        # The adapter's local map can handle "two sum" or "234" directly.
        processed_query_for_adapter = temp_lc_query if temp_lc_query else query_string 
        print(f"Domain determined: LeetCode. Using query: '{processed_query_for_adapter}' for adapter.")
    else:
        def find_valid_wiki_topic(query_string):
            link = "https://en.wikipedia.org/wiki/?search="+query_string
            search_result = json.loads(search_tool.invoke(link))
            for result in search_result:
                return result["link"].replace("https://en.wikipedia.org/wiki/", "")

        processed_query_for_adapter = find_valid_wiki_topic(query_string).replace(" ", "_")
        print(f"Domain determined: Wikipedia. Using topic: '{processed_query_for_adapter}' for adapter.")

    t0 = time.time()

    if domain_to_target == "leetcode":
        print(f"\n--- Fetching LeetCode Data for: '{processed_query_for_adapter}' ---")
        problem_data = run_leetcode_adapter(processed_query_for_adapter) 
        if problem_data:
            markdown_output = format_leetcode_data_to_markdown(problem_data)
            print("\n## LeetCode Problem Data:\n") # This print is for console visibility
            
            try:
                return markdown_output
            except Exception as e:
                print(f"Error saving LeetCode data to file: {e}")
        else:
            print(f"Could not retrieve LeetCode data for query: '{processed_query_for_adapter}'")
    
    elif domain_to_target == "wikipedia":
        print(f"\n--- Fetching Wikipedia Data for: '{processed_query_for_adapter}' ---")
        
        normalized_start_link = normalize_wiki_link_wikipedia("/wiki/" + processed_query_for_adapter)
        
        if not normalized_start_link:
            print(f"Error: Provided Wikipedia query '{query_string}' results in an invalid topic link ('{processed_query_for_adapter}'). Exiting.")
            return

        wiki_params = { 
            'title_keyword': processed_query_for_adapter, 
            'starting_page': normalized_start_link,    
            'seed_page': seed_page_domain,    
            'to_crawl_levels': to_crawl_levels,
            'pause_seconds': pause_seconds,
            'to_print_levels': to_print_levels,
            'top_k': top_k,
            'top_content_links': top_content_links, 
        }
        crawl_result_message = crawl_wikipedia_topic(wiki_params) 
        return crawl_result_message