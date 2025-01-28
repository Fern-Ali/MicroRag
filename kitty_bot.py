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

# Intents and Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Load SentenceTransformer Model and Initialize FAISS Index
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")  # Lightweight embedding model
embedding_dim = embedding_model.get_sentence_embedding_dimension()
index = faiss.IndexFlatL2(embedding_dim)  # FAISS index for embeddings
user_contexts = {}  # Store user-specific chunks

# Function map for dynamic function calling
def calculate_sum(a, b):
    return a + b

function_map = {
    "calculate_sum": calculate_sum,
}

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


# Command: !context
@bot.command()
async def context(ctx):
    """
    Handles file uploads and creates embeddings for user-specific contexts.
    """
    if not ctx.message.attachments:
        await ctx.send("Please upload a file with this command!")
        return

    attachment = ctx.message.attachments[0]
    file_ext = attachment.filename.split(".")[-1].lower()

    if file_ext not in ["pdf", "txt"]:
        await ctx.send("Unsupported file type. Please upload a PDF or TXT file.")
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
        await attachment.save(temp_file.name)

        if file_ext == "pdf":
            text = extract_text_from_pdf(temp_file.name)
        elif file_ext == "txt":
            with open(temp_file.name, "r", encoding="utf-8") as f:
                text = f.read()

        chunks = split_into_chunks(text, chunk_size=100)
        embeddings = embedding_model.encode(chunks, show_progress_bar=True)

        for i, embedding in enumerate(embeddings):
            index.add(embedding.reshape(1, -1))
            user_contexts[f"{ctx.author.id}_{i}"] = chunks[i]
    print(f"FAISS index contains {index.ntotal} vectors.")
    await ctx.send("Your document has been indexed and is ready for queries!")

# Command: !query
@bot.command()
async def query(ctx, *, user_query: str):
    """
    Handles queries based on uploaded user context.
    """
    if index.ntotal == 0:
        await ctx.send("No context available. Please upload a document first using `!context`.")
        return

    # Embed the user query
    query_embedding = embedding_model.encode([user_query])
    distances, indices = index.search(query_embedding, k=3)  # Retrieve top 3 chunks
    print("Distances:", distances)
    print("Indices:", indices)

    # Retrieve the most relevant chunks
    relevant_chunks = [
        user_contexts.get(f"{ctx.author.id}_{idx}", "")
        for idx in indices[0] if f"{ctx.author.id}_{idx}" in user_contexts
    ]
    print("Relevant Chunks Retrieved:", relevant_chunks)

    # Use the top chunks as context
    context = "\n\n".join(relevant_chunks[:2])  # Use top 2 chunks

    if not context.strip():  # Ensure context isn't empty
        await ctx.send("No relevant context found for your query.")
        return

    # Send request to FastAPI for generation
    start_time = time.time()
    generated_text = await generate_with_api(user_query, context=context, max_length=300)
    await ctx.send(f"**Query:** {user_query}\n\n**Response:**\n{generated_text}")
    end_time = time.time()
    await ctx.send(f"API Request took {end_time - start_time:.2f} seconds.")

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

# Load environment variables and run the bot
load_dotenv()
bot.run(os.getenv("BOT_TOKEN"))
