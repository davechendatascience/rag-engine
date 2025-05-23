# leetcode_adapter.py

import time
import json
from urllib.parse import quote_plus, unquote_plus, urlparse # Added urlparse here
from bs4 import BeautifulSoup
import requests 

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import re 

import requests

api_key = "BSAJ4SpjbW9xCJCyb69qU_EqEmyJXhG"

def find_leetcode_url_with_brave(problem_number, api_key):
    # Compose the search query
    query = f"leetcode {problem_number}"
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key
    }
    params = {"q": query, "count": 3}
    response = requests.get(url, headers=headers, params=params)
    results = response.json()
    # Loop through results and find the first LeetCode problem URL
    for item in results.get("web", {}).get("results", []):
        link = item.get("url", "")
        if link.startswith("https://leetcode.com/problems/"):
            return link
    return None

def find_leetcode_problem_url_via_brave(query: str, api_key: str) -> str | None:
    """
    Searches Brave for a LeetCode problem using the Brave Search API and 
    returns the first valid problem URL found.
    """
    try:
        encoded_query = quote_plus(query)
        search_url = f"https://api.search.brave.com/res/v1/web/search?q=site:leetcode.com%20{encoded_query}"
        print(f"Searching Brave with API for URL: {search_url}")

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()  # Raise an error for bad responses
        results = response.json()

        for item in results.get("web", {}).get("results", []):
            link = item.get("url", "")
            if link.startswith("https://leetcode.com/problems/"):
                print(f"Found valid LeetCode problem URL: {link}")
                slug = link.split("/")[4]  # Extract slug from URL
                return slug
        print("No direct LeetCode problem URL found in search results that matches criteria.")
        return None
    except Exception as e:
        print(f"An error occurred during Brave search: {e}")
        return None

def extract_data_from_leetcode_problem_page(slug: str) -> dict | None:
    """
    Extracts the title and description from a LeetCode problem page using its slug.
    """
    problem_url = f"https://leetcode.com/problems/{slug}/"
    driver = None
    
    TITLE_SELECTOR = 'div[data-cy="question-title"]' 
    DESCRIPTION_CONTAINER_SELECTOR = 'div[data-track-load="description_content"]' 
    DESCRIPTION_CONTENT_SELECTOR = f"{DESCRIPTION_CONTAINER_SELECTOR} > div" 

    try:
        print(f"Fetching LeetCode page with Selenium: {problem_url}")
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")

        try:
            import logging
            logging.getLogger('WDM').setLevel(logging.NOTSET)
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e_wdm:
            print(f"Error initializing WebDriver via ChromeDriverManager: {e_wdm}")
            try:
                service = ChromeService(executable_path='/usr/bin/chromedriver')
                driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e_fallback:
                print(f"Fallback WebDriver initialization also failed: {e_fallback}")
                return None
        
        driver.get(problem_url)
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, DESCRIPTION_CONTAINER_SELECTOR))
        )
        time.sleep(1) 

        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')

        title_element = soup.select_one(TITLE_SELECTOR) 
        extracted_title = title_element.get_text(strip=True) if title_element else None
        
        if not extracted_title: 
            title_element_alt = soup.find("div", class_=re.compile(r"text-title-\w+|title__\w+"))
            if title_element_alt:
                extracted_title = title_element_alt.get_text(strip=True)
            else: 
                h1_title = soup.find('h1')
                if h1_title: extracted_title = h1_title.get_text(strip=True)
                else:
                    h2_title = soup.find('h2') 
                    if h2_title: extracted_title = h2_title.get_text(strip=True)
        
        description_container = soup.select_one(DESCRIPTION_CONTENT_SELECTOR)
        extracted_description = None
        if description_container:
            extracted_description = description_container.get_text(separator='\n', strip=True)
        else: 
            description_container_main = soup.select_one(DESCRIPTION_CONTAINER_SELECTOR)
            if description_container_main:
                 extracted_description = description_container_main.get_text(separator='\n', strip=True)

        if not extracted_title and not extracted_description: 
            print(f"Failed to extract both title and description from {problem_url}")
            return None
        
        print(f"Successfully extracted data for slug: {slug}")
        return {
            "title": extracted_title or f"Problem: {slug.replace('-', ' ').title()}", 
            "description": extracted_description or "Description not found.", 
            "url": problem_url
        }

    except TimeoutException:
        print(f"Timeout waiting for description content for slug: {slug} at {problem_url}")
        return None
    except Exception as e:
        print(f"An error occurred extracting data for slug {slug}: {e}")
        return None
    finally:
        if driver:
            print("Closing Selenium WebDriver for LeetCode page.")
            driver.quit()

def run_leetcode_adapter(query: str) -> dict | None:
    """
    Main adapter function to get LeetCode problem data.
    It tries the local map ONLY.
    """
    print(f"LeetCode Adapter: Received query '{query}'")
    slug = find_leetcode_problem_url_via_brave(query, api_key) 
    if slug:
        print(f"LeetCode Adapter: Slug '{slug}' found locally.")
        return extract_data_from_leetcode_problem_page(slug)
    else:
        print(f"LeetCode Adapter: Slug for query '{query}' not found in local map. No data fetched.")
        return None


def format_leetcode_data_to_markdown(problem_data: dict | None) -> str:
    """
    Formats LeetCode problem data into a Markdown string.
    """
    if not problem_data or not isinstance(problem_data, dict):
        return "### LeetCode Problem Data Not Available\n\nCould not retrieve or format LeetCode problem data.\n"

    title = problem_data.get("title", "N/A")
    url = problem_data.get("url", "#")
    description = problem_data.get("description", "No description available.")

    if '\n' in description:
        formatted_description = f"```\n{description}\n```"
    else:
        formatted_description = description

    markdown_parts = [
        f"### {title}\n", 
        f"**URL:** [{title}]({url})\n",
        "**Description:**\n", 
        f"{formatted_description}\n" 
    ]
    return "\n".join(markdown_parts)

# Note: main() and get_args() will be in content-crawler.py
# Wikipedia specific functions will be in wikipedia_adapter.py
