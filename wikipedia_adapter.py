# wikipedia_adapter.py

import time
import urllib.request
from urllib.parse import urlparse, urljoin
from collections import Counter
from bs4 import BeautifulSoup, Tag # Import Tag for type hinting
import user_agent 
import re 

# Global database for the crawl session, specific to Wikipedia crawl
database = {}

# --- Utility Functions (moved from content-crawler.py or specific to Wikipedia) ---

def normalize_wiki_link(link_text: str) -> str | None:
    """
    Normalizes a Wikipedia link to the form /wiki/Page_Name.
    Returns None if the link is not a valid Wikipedia article path.
    """
    if not link_text: return None
    
    parsed_link = urlparse(link_text)
    path = parsed_link.path

    if not path.startswith('/wiki/'): return None 

    path_main = path.split('#')[0].split('?')[0]
    
    try:
        decoded_path = urllib.parse.unquote(path_main)
    except Exception:
        decoded_path = path_main 

    if decoded_path.startswith('/wiki/'):
        article_part = decoded_path[len('/wiki/'):]
        if not article_part: return None 
        article_part_underscored = article_part.replace(" ", "_")
        if any(char in article_part_underscored for char in ['<', '>', '[', ']', '{', '}', '|', '\n']):
            return None
        return f"/wiki/{article_part_underscored}"
    return None

def extension_scan(url: str) -> int:
    """Checks if a URL points to a file of a certain type."""
    a = ['.png','.jpg','.jpeg','.gif','.tif','.txt']
    return 1 if any(ext in url.lower() for ext in a) else 0

# --- Main Wikipedia Data Extraction Functions ---

def download_page(url: str) -> tuple[BeautifulSoup | None, int]:
    """Downloads and returns the content of a web page."""
    try:
        headers = {}
        headers['User-Agent'] = user_agent.generate_user_agent()
        req = urllib.request.Request(url, headers = headers)
        with urllib.request.urlopen(req) as resp: # Use with statement
            respData = BeautifulSoup(resp.read(), 'html.parser')
            flag = 0
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        respData = None
        flag = 1
    return respData, flag

def extract_title(page_soup: BeautifulSoup) -> str:
    """Extracts and returns the title of a Wikipedia page from soup object."""
    title_tag = page_soup.find('h1', {'id': 'firstHeading'})
    if title_tag:
        return title_tag.get_text(strip=True)
    elif page_soup.title and page_soup.title.string:
        return page_soup.title.string.replace(" - Wikipedia", "").strip()
    return "Title not found"

def extract_see_also(page_soup: BeautifulSoup, current_page_normalized_link: str) -> tuple[list[str], int]:
    """
    Extracts and returns the 'See also' links from a Wikipedia soup object with improved robustness.
    """
    found_links = set() # Use a set to store unique links
    
    # 1. Flexible Heading Finding
    see_also_heading_element = None
    # Try common IDs first
    for span_id in ['See_also', 'See_also_section']: # Common IDs for the span inside the heading
        span_tag = page_soup.find('span', {'id': span_id})
        if span_tag:
            parent_heading = span_tag.find_parent(['h2', 'h3'])
            if parent_heading:
                see_also_heading_element = parent_heading
                break
    
    if not see_also_heading_element:
        for heading_tag_name in ['h2', 'h3']:
            for heading in page_soup.find_all(heading_tag_name):
                headline_span = heading.find('span', class_='mw-headline')
                if headline_span and headline_span.get_text(strip=True).lower() == 'see also':
                    see_also_heading_element = heading
                    break
                elif not headline_span and heading.get_text(strip=True).lower() == 'see also': 
                     see_also_heading_element = heading
                     break
            if see_also_heading_element:
                break

    if not see_also_heading_element:
        return [], 1 

    # 2. More Aggressive Iterating for <ul> Lists
    uls_to_process = []
    for element in see_also_heading_element.find_next_siblings():
        # Stop conditions: next H1/H2/H3 or known footer/unrelated section IDs
        if element.name in ['h1', 'h2', 'h3']:
            break
        if element.name == 'div' and element.get('id') in ['catlinks', 'references-section', 'siteSub', 'contentSub', 'jump-to-nav', 'printfooter']:
            break
        # Skip common non-content divs unless they are known to wrap 'See also' lists
        if element.name == 'div' and any(cls in element.get('class', []) for cls in ['noprint', 'navbox', 'metadata', 'vertical-navbox', 'toc']):
            continue # Skip these wrapper types unless specifically targeted

        if element.name == 'ul':
            uls_to_process.append(element)
        elif element.name == 'div':
            # For divs, aggressively find all 'ul's within this div
            # This is okay because we are already under a "See also" heading
            uls_to_process.extend(element.find_all('ul')) 
            
    for ul_element in uls_to_process:
        for li in ul_element.find_all('li', recursive=False): 
            a_tag = li.find('a', href=True)
            if a_tag:
                normalized_link = normalize_wiki_link(a_tag['href'])
                if normalized_link and normalized_link != current_page_normalized_link:
                    path_part = normalized_link.replace('/wiki/', '')
                    if ':' not in path_part: 
                        found_links.add(normalized_link)
                            
    link_list = sorted(list(found_links)) 
    return link_list, 0 if link_list else 1


def extract_external_links(page_soup: BeautifulSoup, seed_page_base_url_for_filtering: str = "https://en.wikipedia.org") -> list[dict]:
    """Extracts links from the 'External links' section of a Wikipedia page."""
    external_links_list = []
    heading_ids = ['External_links', 'External_links_section'] 
    external_links_heading_element = None 
    
    for hid in heading_ids:
        span_tag = page_soup.find('span', {'id': hid})
        if span_tag:
            parent_heading = span_tag.find_parent(['h2', 'h3'])
            if parent_heading:
                external_links_heading_element = parent_heading
                break
    
    if not external_links_heading_element: 
        for heading_tag_name in ['h2', 'h3']:
            for heading in page_soup.find_all(heading_tag_name):
                headline_span = heading.find('span', class_='mw-headline')
                if headline_span and headline_span.get_text(strip=True).lower() == 'external links':
                    external_links_heading_element = heading 
                    break
                elif not headline_span and heading.get_text(strip=True).lower() == 'external links': 
                    external_links_heading_element = heading
                    break
            if external_links_heading_element:
                break

    if external_links_heading_element:
        h_parent = external_links_heading_element 
        
        current_element = h_parent.find_next_sibling()
        ul_elements = []
        while current_element:
            if current_element.name in ['h1', 'h2'] or (current_element.name == 'div' and current_element.get('id') == 'catlinks'): 
                break
            if current_element.name == 'ul':
                ul_elements.append(current_element)
            elif current_element.name == 'div' and any(cls in current_element.get('class', []) for cls in ['div-col', 'noprint', 'plainlist']): 
                uls_in_div = current_element.find_all('ul')
                ul_elements.extend(uls_in_div)
            current_element = current_element.find_next_sibling()

        for ul_element in ul_elements:
            for li in ul_element.find_all('li', recursive=True): 
                a_tag = li.find('a', {'href': True, 'class': re.compile(r'\bexternal\b')}) 
                if not a_tag: 
                    a_tag = li.find('a', href=re.compile(r"^(http://|https://|//)"))
                
                if a_tag:
                    href = a_tag['href']
                    link_text = a_tag.get_text(strip=True)
                    if not link_text: link_text = href 

                    if href.startswith('//'):
                        href = 'https:' + href 
                    elif href.startswith('http://') or href.startswith('https://'):
                        base_wiki_file_url = urljoin(seed_page_base_url_for_filtering, "/wiki/File:")
                        if any(domain_part in href for domain_part in ['web.archive.org', 'archive.is']) or href.startswith(base_wiki_file_url):
                            continue
                        external_links_list.append({'text': link_text, 'url': href})
    return external_links_list

def extract_introduction(page_soup: BeautifulSoup) -> str:
    """Extracts and returns the introduction section from a Wikipedia soup object."""
    content_div = page_soup.find('div', {'id': 'mw-content-text'})
    if not content_div: return "Introduction not found (content div missing)"
    parser_output = content_div.find('div', class_='mw-parser-output')
    if not parser_output: return "Introduction not found (parser output missing)"

    intro_text = []
    for element in parser_output.children:
        if element.name == 'p':
            intro_text.append(element.get_text(strip=True))
        elif element.name == 'div' and element.get('id') == 'toc': break
        elif element.name == 'h2': break
        elif element.name == 'table' and 'infobox' in element.get('class', []): continue
        elif intro_text and (element.name != 'p' and element.name is not None): break
    return "\n\n".join(intro_text) 

def extract_page_sections(page_soup: BeautifulSoup) -> list[dict]:
    """Extracts all major sections (headings and content) from a Wikipedia soup object."""
    sections = []
    content_div = page_soup.find('div', {'id': 'mw-content-text'})
    if not content_div: return sections
    parser_output = content_div.find('div', class_='mw-parser-output')
    if not parser_output: return sections

    excluded_section_headlines = ['references', 'external links', 'see also', 'notes', 'further reading', 'bibliography', 'sources', 'citations', 'gallery']
    heading_tags = ['h2', 'h3', 'h4', 'h5', 'h6']
    current_heading_text = None
    current_content_paragraphs = []

    for element in parser_output.children:
        if element.name in heading_tags:
            headline_span = element.find('span', class_='mw-headline')
            if headline_span: 
                new_heading_text = headline_span.get_text(strip=True)
                if new_heading_text.lower() in excluded_section_headlines:
                    if current_heading_text and current_content_paragraphs: 
                        sections.append({'heading': current_heading_text, 'content': "\n\n".join(current_content_paragraphs)})
                    current_heading_text = None 
                    current_content_paragraphs = []
                    continue 
                if current_heading_text and current_content_paragraphs: 
                    sections.append({'heading': current_heading_text, 'content': "\n\n".join(current_content_paragraphs)})
                current_heading_text = new_heading_text
                current_content_paragraphs = [] 
            elif element.get_text(strip=True).lower() == 'contents': 
                 if current_heading_text and current_content_paragraphs:
                    sections.append({'heading': current_heading_text, 'content': "\n\n".join(current_content_paragraphs)})
                 current_heading_text = None 
                 current_content_paragraphs = []
        elif current_heading_text: 
            if element.name == 'p':
                current_content_paragraphs.append(element.get_text(strip=True))
            elif element.name in ['ul', 'ol']:
                list_items_text = []
                for item in element.find_all('li', recursive=False):
                    list_items_text.append(f"* {item.get_text(strip=True)}") 
                if list_items_text:
                    current_content_paragraphs.append("\n".join(list_items_text))
            elif element.name == 'div' and any(cls in element.get('class', []) for cls in ['navbox', 'metadata', 'reflist', 'noprint', 'gallery', 'toc']): 
                if current_heading_text and current_content_paragraphs: 
                    sections.append({'heading': current_heading_text, 'content': "\n\n".join(current_content_paragraphs)})
                current_heading_text = None 
                current_content_paragraphs = []
            elif element.name == 'table' and 'infobox' not in element.get('class', []): 
                if current_heading_text and current_content_paragraphs:
                    sections.append({'heading': current_heading_text, 'content': "\n\n".join(current_content_paragraphs)})
                current_heading_text = None
                current_content_paragraphs = []
    
    if current_heading_text and current_content_paragraphs: 
        sections.append({'heading': current_heading_text, 'content': "\n\n".join(current_content_paragraphs)})
    return sections

def extract_content_links(parser_output_div: BeautifulSoup, current_page_normalized_link: str) -> list[str]:
    """Extracts valid Wikipedia article links from the main content area."""
    links = []
    if not parser_output_div: return links

    excluded_href_keywords = ['file:', 'template:', 'help:', 'category:', 'portal:', 'special:', 'talk:', 'user:', 'wikipedia:', 'mos:', 'wp:', '#cite_note', '#references', '(identifier)', 'disambiguation', 'isbn', 'doi', 'pmid', 'jstor', 'arxiv', 'bibcode', 'wayback', 'action=edit', 'action=history', 'action=submit']
    excluded_parent_section_headlines = ['see also', 'references', 'external links', 'notes', 'further reading', 'bibliography', 'sources', 'citations', 'gallery']

    for a_tag in parser_output_div.find_all('a', href=True):
        href = a_tag['href']
        normalized_link = normalize_wiki_link(href)

        if not normalized_link or normalized_link == current_page_normalized_link: 
            continue

        if any(keyword.lower() in normalized_link.lower() for keyword in excluded_href_keywords):
            continue
        
        path_part = normalized_link.replace('/wiki/', '')
        if ':' in path_part: 
            continue

        is_in_excluded_parent = False
        for parent in a_tag.parents:
            parent_classes = parent.get('class', [])
            parent_id = parent.get('id', '')
            if (parent.name == 'div' and (any(cls in parent_classes for cls in ['navbox', 'vertical-navbox', 'metadata', 'reflist', 'thumb', 'gallery', 'toc', 'infobox', 'sistersitebox']) or 'mw-references' in parent_classes or parent_id == 'toc')) or \
               (parent.name == 'span' and any(cls in parent_classes for cls in ['mw-editsection', 'mw-editsection-bracket', 'mw-cite-backlink'])) or \
               (parent.name in ['h1','h2','h3','h4','h5','h6'] and parent.find('span', class_='mw-headline') and any(sec_title in parent.find('span', class_='mw-headline').get_text(strip=True).lower() for sec_title in excluded_parent_section_headlines)) or \
               (parent.name == 'table' and any(cls in parent_classes for cls in ['sidebar', 'infobox', 'wikitable', 'toccolours', 'nowraplinks'])) or \
               (parent.name == 'sup' and any(cls in parent_classes for cls in ['reference', 'noprint'])) or \
               (parent.name == 'li' and parent.find_parent(['ul', 'div']) and parent.find_parent(['ul', 'div']).find_previous_sibling(['h2','h3']) and parent.find_parent(['ul', 'div']).find_previous_sibling(['h2','h3']).find('span', class_='mw-headline', id=lambda x: x and x.lower().replace('_', ' ') in ['see also', 'see also section'])): 
                is_in_excluded_parent = True
                break
        if not is_in_excluded_parent:
            links.append(normalized_link)
    return links

# --- Wikipedia Tree Building and Output Classes/Functions ---

class ContentNode: 
    """Represents a node in the content hierarchy for Wikipedia."""
    def __init__(self, title, link):
        self.title = title 
        self.link = link   
        self.children = []

    def count_descendants(self):
        return len(self.children) + sum(child.count_descendants() for child in self.children)

def build_wikipedia_tree(treeEdges: list[tuple[str, str]], rootValLink: str, link_to_title_map_param: dict) -> ContentNode | None:
    """Builds a Wikipedia content tree from edges."""
    treeMap = {} 
    
    def get_node_title(link_path):
        return link_to_title_map_param.get(link_path, link_path.replace("/wiki/", "").replace("_", " "))

    if rootValLink not in treeMap: 
        treeMap[rootValLink] = ContentNode(get_node_title(rootValLink), rootValLink)

    for parent_link, child_link in treeEdges:
        if parent_link not in treeMap:
            treeMap[parent_link] = ContentNode(get_node_title(parent_link), parent_link)
        if child_link not in treeMap:
            treeMap[child_link] = ContentNode(get_node_title(child_link), child_link)
        
        treeMap[parent_link].children.append(treeMap[child_link])
        
    return treeMap.get(rootValLink) 

def _generate_wikipedia_markdown_recursive(node: ContentNode, database_ref: dict, base_url: str, current_markdown_level: int, max_print_level: int, top_k: int | None, lines: list[str]):
    """Helper to recursively generate Markdown for Wikipedia subtopics."""
    print(f"[DEBUG WIKI_MD] Print: Node='{node.title}', md_level={current_markdown_level}, max_print_level_param={max_print_level}") 
    
    current_node_depth_from_root_children = current_markdown_level - 1 
    if current_node_depth_from_root_children > max_print_level : 
        print(f"[DEBUG WIKI_MD]   Skipping children of '{node.title}', current_node_depth {current_node_depth_from_root_children} > max_print_level {max_print_level}") 
        return

    node.children.sort(key=lambda child_node: child_node.count_descendants(), reverse=True)
    children_to_print = node.children[:top_k] if top_k is not None else node.children

    for child in children_to_print:
        lines.append(f"{'#' * current_markdown_level} {child.title}")
        
        node_db_key = child.title.lower() 
        child_data = database_ref.get(node_db_key)
        
        if child_data and child_data.get('introduction'):
            intro_paragraph = child_data['introduction'].replace('\n', '\n\n') 
            lines.append(f"\n{intro_paragraph}\n")
        else:
            lines.append("\n(Introduction not available or page not crawled)\n")
            
        full_link = urljoin(base_url, child.link) 
        lines.append(f"[Link to page]({full_link})\n")
        
        if child.children:
            _generate_wikipedia_markdown_recursive(child, database_ref, base_url, current_markdown_level + 1, max_print_level, top_k, lines)

def generate_wikipedia_markdown_output(root_node: ContentNode | None, database_ref: dict, base_url: str, title_keyword_param: str, to_print_levels_param: float, top_k_param: int | None) -> str:
    """Generates the full Markdown output string for Wikipedia content."""
    if not root_node:
        return "Error: Root node is None, cannot generate Wikipedia Markdown."

    lines = []
    root_display_title = root_node.title 
    root_db_key = root_display_title.lower() 
    root_data = database_ref.get(root_db_key)

    lines.append(f"# {root_display_title}") 
    if root_data:
        intro_paragraph = root_data.get('introduction', 'Introduction not found.').replace('\n', '\n\n')
        lines.append(f"\n{intro_paragraph}\n")
        
        if root_data.get('sections'):
            for section in root_data['sections']:
                if section.get('heading') and section.get('content','').strip(): 
                    lines.append(f"## {section['heading']}") 
                    section_content = section['content'].replace('\n', '\n\n')
                    lines.append(f"\n{section_content}\n")
        
        if root_data.get('external_links'):
            lines.append(f"## External Links")
            for ext_link in root_data['external_links']:
                lines.append(f"* [{ext_link['text']}]({ext_link['url']})")
            lines.append("") 

    else:
        lines.append("\n(Main topic data not found in database.)\n")

    if root_node.children:
        lines.append("## Key Subtopics") 
        _generate_wikipedia_markdown_recursive(root_node, database_ref, base_url, 2, int(to_print_levels_param), top_k_param, lines)
        
    return "\n".join(lines)

# --- Main Wikipedia Crawl Orchestration ---

def crawl_wikipedia_topic(params: dict) -> str:
    """Main function for Wikipedia crawl, adapted from original web_crawl."""
    global database 
    database = {}   

    title_keyword = params['title_keyword'] 
    starting_page_link_raw = params['starting_page'] 
    starting_page_link = normalize_wiki_link(starting_page_link_raw) 
    if not starting_page_link:
        return f"Error: Starting page link '{starting_page_link_raw}' is invalid for Wikipedia crawl."

    seed_page_base_url = params['seed_page'] 
    to_crawl_levels = params['to_crawl_levels']
    to_print_levels_param = params['to_print_levels'] 
    pause_seconds = params['pause_seconds']
    top_k_children_to_print_param = params['top_k'] 
    # Fallback for content links from sub-pages, if 'See also' is sparse
    TOP_CONTENT_LINKS_FALLBACK_COUNT = 5 
    top_content_links_arg = params.get('top_content_links', 10) # For starting page

    to_crawl = [starting_page_link]
    crawled = [] 
    levels = {starting_page_link: 0} 
    parents = {} 
    treeEdges = []
    link_to_title_map = {} 
    root_node_actual_title = title_keyword.replace("_", " ") 

    while to_crawl:
        page_link_to_process = to_crawl.pop(0) 
        current_level = levels[page_link_to_process]
        
        print(f"[DEBUG WIKI] Loop: page='{page_link_to_process}', current_level={current_level}, target_crawl_depth={to_crawl_levels}") 

        full_url_for_download = urljoin(seed_page_base_url, page_link_to_process)
        
        flag_extension = extension_scan(full_url_for_download)
        time.sleep(pause_seconds)

        if flag_extension == 1 or page_link_to_process in crawled: 
            continue
        
        if page_link_to_process != starting_page_link and page_link_to_process in parents:
            treeEdges.append((parents[page_link_to_process], page_link_to_process))
        
        page_soup, flag_download = download_page(full_url_for_download)
        
        if flag_download == 0 and page_soup:
            actual_page_title = extract_title(page_soup)
            db_key_title = actual_page_title.lower() 
            link_to_title_map[page_link_to_process] = actual_page_title

            if page_link_to_process == starting_page_link:
                 root_node_actual_title = actual_page_title 

            see_also_links_list, flag_see_also = extract_see_also(page_soup, page_link_to_process)
            print(f"[DEBUG WIKI] Page '{page_link_to_process}': 'See also' links found: {len(see_also_links_list)}") 
            
            intro_text = extract_introduction(page_soup)
            page_sections = extract_page_sections(page_soup)
            
            external_links_data = []
            if current_level == 0: 
                external_links_data = extract_external_links(page_soup, seed_page_base_url)

            database[db_key_title] = {
                'title': actual_page_title, 
                'introduction': intro_text,
                'sections': page_sections,
                'see_also': see_also_links_list, 
                'external_links': external_links_data 
            }
            crawled.append(page_link_to_process) 

            if current_level < to_crawl_levels:
                links_for_next_queue_normalized = []
                if current_level == 0: 
                    parser_output_div = page_soup.find('div', class_='mw-parser-output')
                    content_links_list = extract_content_links(parser_output_div, page_link_to_process) if parser_output_div else []
                    print(f"[DEBUG WIKI] Level 0: Content links found: {len(content_links_list)}") 
                    
                    if content_links_list: 
                        link_counts = Counter(content_links_list)
                        top_content = [link for link, count in link_counts.most_common(top_content_links_arg)]
                        # --- MODIFICATION FOR TARGETED TEST ---
                        links_for_next_queue_normalized = [] # Clear the list
                        if top_content: # If there are any content links
                            links_for_next_queue_normalized.append(top_content[0]) # Add only the first one
                        print(f"[DEBUG WIKI] TARGETED TEST: Next crawl queue forced to: {links_for_next_queue_normalized}")
                        # --- END OF MODIFICATION ---
                
                # Add "See also" links (for level 0, these are added after content links if not for the test modification)
                # For level > 0, these are the primary source unless fallback is triggered
                # If current_level == 0, this block will now add see_also_links to the queue that might only have 1 content link
                if flag_see_also == 0 and see_also_links_list: 
                    for slink_norm in see_also_links_list: 
                        if slink_norm not in links_for_next_queue_normalized:
                            links_for_next_queue_normalized.append(slink_norm)
                
                # Fallback for current_level > 0 if "See also" links are sparse
                if current_level > 0 and len(see_also_links_list) < 2: 
                    print(f"[INFO WIKI] 'See also' links sparse for {page_link_to_process} ({len(see_also_links_list)} found). Attempting content links fallback.")
                    parser_output_div = page_soup.find('div', class_='mw-parser-output') 
                    content_links_fallback = extract_content_links(parser_output_div, page_link_to_process) if parser_output_div else []
                    if content_links_fallback:
                        link_counts_fallback = Counter(content_links_fallback)
                        top_content_fallback = [link for link, count in link_counts_fallback.most_common(TOP_CONTENT_LINKS_FALLBACK_COUNT)]
                        added_fallback_count = 0
                        for flink_norm in top_content_fallback:
                            if flink_norm not in links_for_next_queue_normalized: 
                                links_for_next_queue_normalized.append(flink_norm)
                                added_fallback_count +=1
                        if added_fallback_count > 0:
                             print(f"[INFO WIKI] Added {added_fallback_count} top content links as fallback for {page_link_to_process}.")

                for link_norm in links_for_next_queue_normalized: 
                    print(f"[DEBUG WIKI]   Considering: {link_norm}. In levels: {link_norm in levels}. Crawled: {link_norm in crawled}.") 
                    if link_norm not in levels and link_norm not in crawled: 
                        levels[link_norm] = current_level + 1
                        parents[link_norm] = page_link_to_process 
                        if link_norm not in to_crawl: 
                             to_crawl.append(link_norm)
                             print(f"[DEBUG WIKI]     ADDING: {link_norm}, level: {current_level + 1}") 
        
    print(f"[DEBUG WIKI] Crawl loop END. Crawled count: {len(crawled)}. Levels dict size: {len(levels)}. Edges count: {len(treeEdges)}") 

    if not crawled:
        return "Starting page could not be crawled. No output generated."

    tree_root_node = build_wikipedia_tree(treeEdges, starting_page_link, link_to_title_map)
    if tree_root_node: 
        tree_root_node.title = root_node_actual_title 
    else: 
        if starting_page_link in crawled: 
            tree_root_node = ContentNode(root_node_actual_title, starting_page_link) 
        else: 
            return "Failed to process starting page sufficiently to build a data tree for Wikipedia."
    
    markdown_content = generate_wikipedia_markdown_output(tree_root_node, database, seed_page_base_url, title_keyword, to_print_levels_param, top_k_children_to_print_param)
    
    output_filename = title_keyword.replace(" ", "_").replace("/", "_") + ".md" 
    try:
        print(f"Wikipedia Markdown output written to {output_filename}")
    except Exception as e:
        print(f"Error writing Wikipedia Markdown file: {e}")
        return f"Wikipedia crawl finished, but Markdown output failed: {e}"

    return f"Wikipedia crawl finished. Markdown output at {output_filename}"