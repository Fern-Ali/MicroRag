import requests
from bs4 import BeautifulSoup
from markdownify import markdownify
import tempfile

def scrape_webpage(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extract title
        title = soup.title.string.strip() if soup.title else "No title"
        
        # Extract metadata description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc["content"].strip() if meta_desc else "No description"

        # Extract main text content
        paragraphs = soup.find_all("p")
        content = "\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])

        # Extract headings (h1, h2, h3, etc.)
        headings = "\n".join([h.get_text().strip() for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text().strip()])

        # Extract tables
        table_text = extract_tables(soup)

        # Convert HTML structure into Markdown
        markdown_content = markdownify(response.text, heading_style="ATX")

        # Format the Markdown
        markdown_result = f"# {title}\n\n"
        markdown_result += f"## Description\n{description}\n\n"
        # markdown_result += f"## Headings\n{headings}\n\n"
        markdown_result += f"## Content\n{content[:200]}...\n\n"  # Limit content size
        # markdown_result += f"## Tables\n{table_text}\n\n"
        markdown_result += f"---\n\n## Full Page Markdown\n\n{markdown_content}"  # Append full conversion

        return markdown_result, markdown_result[:200]  # Return full content + preview
    
    except Exception as e:
        return f"Error: {e}", None
    
def save_markdown_to_file(content):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".md") as temp_file:
        temp_file.write(content.encode("utf-8"))
        return temp_file.name

def extract_tables(soup):
    tables = soup.find_all("table")
    markdown_tables = []

    for table in tables:
        rows = table.find_all("tr")
        table_markdown = []

        for i, row in enumerate(rows):
            cols = [col.get_text().strip() for col in row.find_all(["td", "th"])]

            # Add header separator if it's the first row (assuming it's a header)
            if i == 0:
                table_markdown.append("| " + " | ".join(cols) + " |")
                table_markdown.append("|" + " | ".join(["---"] * len(cols)) + "|")  # Markdown table separator
            else:
                table_markdown.append("| " + " | ".join(cols) + " |")

        markdown_tables.append("\n".join(table_markdown))

    return "\n\n".join(markdown_tables) if markdown_tables else "No tables found."

import aiohttp
from bs4 import BeautifulSoup
import urllib.parse

async def search_duckduckgo_async(query):
    url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    results = []

    for result in soup.find_all("a", class_="result__a", limit=5):  # Top 5 results
        title = result.get_text().strip()
        redirect_url = result["href"]
        
        # Extract the real URL
        parsed_url = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url).query).get("uddg", [""])[0]

        # Format results
        results.append(f"**[{title}]({parsed_url})**")

    return "\n".join(results) if results else "No results found."


