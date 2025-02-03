import discord
import os
import requests  # To send POST requests to FastAPI
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from discord.ext import commands
import time
import json
import tempfile
from sentence_transformers import SentenceTransformer
import faiss
import PyPDF2
import tempfile
from scraper_methods import save_markdown_to_file, scrape_webpage, search_duckduckgo_async

# Intents and Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Load SentenceTransformer Model and Initialize FAISS Index
# embedding_model = SentenceTransformer("all-MiniLM-L6-v2")  # Lightweight embedding model
# embedding_dim = embedding_model.get_sentence_embedding_dimension()
# index = faiss.IndexFlatL2(embedding_dim)  # FAISS index for embeddings
# user_contexts = {}  # Store user-specific chunks




# Event: Bot Ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Async helper to send requests to FastAPI
async def generate_with_api(query, context=None, max_length=200):
    """
    Sends a POST request to the FastAPI server for inference.
    """
    try:
        url = "http://localhost:8001/generate"
        payload = {
            "query": query,
            "context": context,
            "max_length": max_length,
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise error for bad status codes
        return response.json()["response"]
    except requests.RequestException as e:
        return f"Error: Unable to reach FastAPI server. Details: {e}"

# Command: !prompt
@bot.command()
async def prompt(ctx, *, prompt_text: str):
    """
    Handles user queries and retrieves responses from the LLM.
    """
    query = prompt_text
    context = None

    # Extract context if specified
    if "Context:" in prompt_text:
        parts = prompt_text.split("Context:", 1)
        query = parts[0].strip()
        context = parts[1].strip()

    # Measure API request time
    start_time = time.time()
    try:
        async with ctx.typing():
            # Send query to the API
            generated_text = await generate_with_api(query, context=context, max_length=300)
            
            # Extract and send the response
            response = extract_answer(generated_text)
            await ctx.send(f"**Response:** {response}")

    except Exception as e:
        # Handle errors and inform the user
        await ctx.send(f"Error: {e}")

    end_time = time.time()
    await ctx.send(f"API Request took {end_time - start_time:.2f} seconds.")

@bot.command()
async def rag(ctx):
    """
    Uploads a document to Django's backend, triggering the RAG pipeline.
    """
    if not ctx.message.attachments:
        await ctx.send("📄 Please attach a document to use this command.")
        return

    attachment = ctx.message.attachments[0]
    file_ext = attachment.filename.split(".")[-1].lower()

    # Supported file types
    if file_ext not in ["pdf", "py", "ipynb", "xlsx", "xls", "txt"]:
        await ctx.send("❌ Unsupported file type. Please upload a PDF, Python file, Jupyter Notebook, Excel file, or a text file.")
        return

    # Save the file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
        await attachment.save(temp_file.name)

    # Prepare the request payload
    files = {"file": open(temp_file.name, "rb")}
    url = "http://localhost:8000/api/upload-document/"  # Django backend upload endpoint

    # Send the file to Django
    try:
        async with ctx.typing():
            response = requests.post(url, files=files)
            os.remove(temp_file.name)  # Cleanup temp file

            if response.status_code == 200:
                result = response.json()
                print(f"✅ **Upload Successful!**\n📄 **Processed Chunks:** {result.get('chunks', 'Unknown')}\n🔄 Your document is now being indexed for retrieval.")
                await ctx.send(f"✅ **Upload Successful!**\n📄 **Processed Chunks:** {len(result.get('chunks', 'Unknown'))}\n🔄 Your document is now being indexed for retrieval.")
            else:
                await ctx.send(f"❌ **Upload Failed!**\n🔍 Error: {response.text}")

    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

@bot.command()
async def rag_query(ctx, *, user_query: str):
    """
    Queries the stored documents in Qdrant and returns relevant text chunks in a dedicated thread.
    If a chunk exceeds 1900 characters, it is split into multiple messages labeled as Part 1, Part 2, etc.
    """
    formatted_query = user_query.replace(" ", "_")
    url = f"http://127.0.0.1:8003/query?query={formatted_query}&limit=5"

    response = requests.get(url)

    if response.status_code != 200:
        await ctx.send("❌ Error querying the document database.")
        return

    results = response.json()

    if not results:
        await ctx.send("❌ No relevant documents found.")
        return

    # Create a thread to display the query results
    thread = await ctx.channel.create_thread(
        name=f"📖 RAG Query: {user_query[:50]}",
        message=ctx.message,
        auto_archive_duration=60
    )

    # Send each retrieved chunk in the thread
    for i, result in enumerate(results):
        chunk_text = result['text']
        metadata = result['metadata']['filename']
        score = result['score']

        if len(chunk_text) <= 1900:
            # If the chunk is short enough, send it as a single message
            formatted_result = (
                f"**📌 Match {i+1}:**\n"
                f"🔹 *{chunk_text}*\n"
                f"📝 **Source:** {metadata} (Score: {score:.4f})"
            )
            await thread.send(formatted_result)
        else:
            # If the chunk is too long, split it into multiple messages
            parts = [chunk_text[i:i+1900] for i in range(0, len(chunk_text), 1900)]
            for part_num, part in enumerate(parts, start=1):
                part_label = f"**📌 Match {i+1}, Part {part_num}:**" if len(parts) > 1 else f"**📌 Match {i+1}:**"
                formatted_result = (
                    f"{part_label}\n"
                    f"🔹 *{part}*"
                )
                await thread.send(formatted_result)

            # After the last part, attach metadata information
            await thread.send(f"📝 **Source:** {metadata} (Score: {score:.4f})")

    await thread.send("✅ **All relevant document chunks have been posted.**")

@bot.command()
async def query(ctx, *, user_query: str):
    """
    Requests /query_llm for just the response without document retrieval.
    The bot will indicate that it's typing while waiting for a response.
    """
    formatted_query = user_query.replace(" ", "_")
    url = f"http://127.0.0.1:8003/query_llm?query={formatted_query}"

    async with ctx.typing():  # Show "Kitty is typing..." while processing
        response = requests.get(url)

        if response.status_code != 200:
            await ctx.send("❌ Error querying the database.")
            return

        data = response.json()
        if "error" in data:
            await ctx.send(f"❌ {data['error']}")
            return

        llm_response = data.get("llm_response", "No response found.")

    # Create a thread for clean organization
    thread = await ctx.channel.create_thread(
        name=f"Query: {user_query[:50]}",
        message=ctx.message,
        auto_archive_duration=60
    )

    # Send response in thread
    if len(llm_response) > 2000:
        chunks = [llm_response[i:i+2000] for i in range(0, len(llm_response), 2000)]
        for chunk in chunks:
            await thread.send(chunk)
    else:
        await thread.send(f"**Response:**\n{llm_response}")

    if len(llm_response) > 6000:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
            temp_file.write(llm_response.encode("utf-8"))
            temp_file_path = temp_file.name

        await thread.send("📂 The response is too long. Here's a file instead:", file=discord.File(temp_file_path))



@bot.command()
async def summarize(ctx):
    """
    Handles file uploads and summarizes the content.
    """
    if not ctx.message.attachments:
        await ctx.send("Please upload a file with this command!")
        return

    # Get the uploaded file
    attachment = ctx.message.attachments[0]
    file_ext = attachment.filename.split(".")[-1].lower()

    # Only accept .txt or .pdf files
    if file_ext not in ["pdf", "txt"]:
        await ctx.send("Unsupported file type. Please upload a PDF or TXT file.")
        return

    # Save the uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
        await attachment.save(temp_file.name)

        # Extract text based on file type
        if file_ext == "pdf":
            text = extract_text_from_pdf(temp_file.name)
        elif file_ext == "txt":
            with open(temp_file.name, "r", encoding="utf-8") as f:
                text = f.read()

    # Send the extracted text to FastAPI for summarization
    prompt = f"Summarize the following text:\n{text[:2000]}"  # Limit input size for safety
    start_time = time.time()
    async with ctx.typing():
        generated_summary = await generate_with_api(prompt, max_length=300)
        end_time = time.time()

        # Send the summary to the user
        await ctx.send(f"**Summary:**\n{extract_answer(generated_summary)}")
        await ctx.send(f"API Request took {end_time - start_time:.2f} seconds.")

@bot.command()
async def scrape(ctx, *, user_query: str):
    if user_query.startswith("http"):  # Detects a URL
        async with ctx.typing():
            markdown_result, preview = scrape_webpage(user_query)
            print(markdown_result, preview)
            if not preview:
                await ctx.send("Error scraping the webpage.")
                return
            
            file_path = save_markdown_to_file(markdown_result)
            
            # Send response with preview and file
            await ctx.send(f"**📄 Extracted Content from {user_query}**\n\n"
                           f"📝 *Preview:* `{preview}...`\n"
                           f"📂 Full content attached ⬇️")
            
            await ctx.send(file=discord.File(file_path))  # Upload .md file
    else:
        await ctx.send("Invalid input. Please provide a valid URL.")

@bot.command()
async def search(ctx, *, query: str):
    """Performs a web search using DuckDuckGo."""
    async with ctx.typing():
        results = await search_duckduckgo_async(query)
        await ctx.send(f"**🔍 Search Results for:** `{query}`\n\n{results}")

@bot.command()
async def function(ctx, *, user_query: str):
    prompt = f"""
    Respond ONLY in JSON. Do not add notes, explanations, or any other text. Output strictly the JSON format. 
    Respond with ONLY ONE function argument pair. Provide the function argument pair only ONCE.
    For example:
    User: Calculate the sum of 5 and 7.
    Assistant: {{"function": "calculate_sum", "arguments": {{"a": 5, "b": 7}}}}
    User: What are the top trending Github repos?
    Assistant: {{"function": "scrape_github_trending", "arguments": {{"since": "daily"}}}}
    User: This week's trending top github repos?
    Assistant: {{"function": "scrape_github_trending", "arguments": {{"since": "weekly"}}}}
    User: What are the trending top Github repos for the month?
    Assistant: {{"function": "scrape_github_trending", "arguments": {{"since": "monthly"}}}}
    Query: {user_query}

    """
    async with ctx.typing():
        response_text = await generate_with_api(prompt)

        # Parse and execute the function
        parsed_response = extract_json(response_text)
        print("parsed responseo", parsed_response)
        
        if "error" not in parsed_response:
            result = execute_function(parsed_response)
            await ctx.send(result)
        else:
            await ctx.send(parsed_response["error"])

# function map for all discord bot function call capablilities:
# Example function map
function_map = {
    "calculate_sum": lambda a, b: a + b,
    "scrape_github_trending": lambda **kwargs: scrape_github_trending(**kwargs),
    # Add more functions as needed
}

def execute_function(parsed_response):
    try:
        # If parsed_response is a list, grab the first function call
        if isinstance(parsed_response, list) and len(parsed_response) > 0:
            parsed_response = parsed_response[0]  # Take the first function call
        
        function_name = parsed_response["function"]
        arguments = parsed_response["arguments"]
        
        if function_name in function_map:
            result = function_map[function_name](**arguments) if arguments else function_map[function_name]()
            
            if function_name == "scrape_github_trending":
                if not result:
                    return "No trending repositories found."

                # Format the message for better readability
                formatted_message = "**🚀 Trending GitHub Repositories:**\n\n"
                for repo in result:
                    repo_name = repo['name'].replace("\n", "").strip()
                    formatted_message += (
                        f"**[{repo_name}]({repo['url']})**\n"
                        f"📌 *{repo['description']}*\n"
                        f"🛠️ Language: `{repo['language']}`\n"
                        f"⭐ Stars: `{repo['stars']}` | 🍴 Forks: `{repo['forks']}`\n\n"
                    )
                return formatted_message
            
            return f"Result: {result}"
        
        else:
            return f"Error: Function `{function_name}` not found."
    except Exception as e:
        return f"Error: {e}"


# Helper: Extract JSON from the model's response
def extract_json(response_text):
    print("DEBUG: Raw response from model:\n", response_text)
    try:
        # Extract JSON after "Answer:"
        if "Answer:" in response_text:
            json_text = response_text.split("Answer:", 1)[1].strip()

            # Check if multiple JSON objects exist
            json_text = json_text.replace("}{", "},{")  # Fix improper object merging
            json_text = f"[{json_text}]"  # Wrap it into a list

            return json.loads(json_text)  # Convert to Python list
        else:
            return {"error": "No JSON found in response."}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format."}

# Helper: Extract text from PDFs
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        return " ".join(page.extract_text() for page in reader.pages)

# Helper: Split text into chunks
def split_into_chunks(text, chunk_size=500):
    words = text.split()
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]


# Helper: Extract answer after "Answer:" keyword
def extract_answer(response_text):
    try:
        # Extract all text after "Answer:"
        if "Answer:" in response_text:
            return response_text.split("Answer:", 1)[1].strip()
        else:
            return "No answer found in the response."
    except Exception as e:
        return f"Error: {e}"
# Scraping function that supports daily, weekly, or monthly trends
def scrape_github_trending(since="daily"):
    url = f"https://github.com/trending?since={since}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        repo_articles = soup.find_all("article", class_="Box-row")
        trending_repos = []

        for article in repo_articles[:5]:  # Limit to top 5 results
            repo_name_tag = article.find("h2", class_="h3 lh-condensed").find("a")
            repo_name = repo_name_tag.text.strip()
            repo_url = "https://github.com" + repo_name_tag["href"]

            repo_description_tag = article.find("p", class_="col-9 color-fg-muted my-1 pr-4")
            repo_description = repo_description_tag.text.strip() if repo_description_tag else "No description provided."

            language_tag = article.find("span", itemprop="programmingLanguage")
            language = language_tag.text.strip() if language_tag else "Unknown"

            stars_tag = article.find("a", href=lambda href: href and "stargazers" in href)
            stars = stars_tag.text.strip() if stars_tag else "0"

            forks_tag = article.find("a", href=lambda href: href and "forks" in href)
            forks = forks_tag.text.strip() if forks_tag else "0"

            trending_repos.append({
                "name": repo_name,
                "url": repo_url,
                "description": repo_description,
                "language": language,
                "stars": stars,
                "forks": forks,
            })

        return trending_repos
    except Exception as e:
        return f"Error occurred: {str(e)}"

def calculate_sum(a, b):
    return a + b

# Load environment variables and run the bot
load_dotenv()
bot.run(os.getenv("BOT_TOKEN"))
