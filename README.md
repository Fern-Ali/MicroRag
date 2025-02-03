
# MicroRag

[![GitHub repo](https://img.shields.io/badge/GitHub-MicroRag-blue?style=flat-square&logo=github)](https://github.com/Fern-Ali/MicroRag)

MicroRag is a lightweight FastAPI-based system for inferencing Large Language Models (LLMs) and other machine learning models. It's paired with **Agent Kitty**, a Discord bot that interacts with the API to provide seamless responses to user queries. Together, MicroRag and Agent Kitty bring the power of Retrieval-Augmented Generation (RAG) to a user-friendly platform.

---

# 📌 Quick Links  
🔹 [**Core Commands**](#sparkles-core-commands)  
🔹 [**RAG Commands**](#sparkles-rag-commands)  
🔹 [**Agent Kitty Patch Notes**](#loudspeaker-agent-kitty-patch-notes)  
🔹 [**Installation Guide**](#wrench-installation--setup)  
🔹 [**Contribute & Feature Ideas**](#bulb-contribute)  
🔹 [**License**](#books-license)  

---

## :rocket: Features
- **FastAPI Backend**:
  - Supports LLM inferencing with models like Llama 3.2.
  - Extendable for other ML models and tasks.
  - RESTful endpoints for single and batch processing.

- **Agent Kitty Discord Bot**:
  - Interacts with the MicroRag API to provide real-time answers to users.
  - Supports commands for text queries, summarization, and function execution.

---

## :wrench: Installation & Setup

### Prerequisites
- Python >= 3.8
- Virtual Environment (recommended)

### Clone the Repository
```bash
git clone https://github.com/Fern-Ali/MicroRag.git
cd MicroRag
```

### Install Dependencies
```bash
pip install -e .
```

### Set Up Environment Variables
Create a `.env` file in the root directory and add:
```
BOT_TOKEN=<Your_Discord_Bot_Token>
```

### Run the FastAPI Server
Start the server on `http://localhost:8001`:
```bash
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

### Run the Discord Bot
Start Agent Kitty:
```bash
python kitty_bot.py
```

---

## :speech_balloon: Agent Kitty Commands

### :sparkles: Core Commands
- **`!prompt [query]`**  
  Send a query to the MicroRag API and receive a concise answer.  
  - Example: `!prompt What is FastAPI?`

- **`!summarize`**  
  Upload a `.txt` or `.pdf` file to receive a concise summary (2000 chars max).  
  - Example: Upload a file with `!summarize`.

- **`!scrape [URL]`**  
  Provide a URL, and MicroRag extracts the webpage, returning it as a formatted Markdown file.  
  - Example: `!scrape https://example.com`
  - Provides a **preview** of the extracted content.  
  - Attaches the full Markdown file for download.  

- **`!function [query]`**  
  Dynamically execute Python functions via JSON requests.  
  - Example: `!function What is 5 plus 7?`  
  - Currently supports:  
    - 🆕 `calculate_sum` | Adds two numbers  
      - **Example Queries:**  
        - `"Add 400 + 800"` → `Result: 1200`  
    - 🆕 `scrape_github_trending` | Fetches the top trending repositories from GitHub.  
      - Supports different time ranges:  
        - `"daily"` (default)  
        - `"weekly"`  
        - `"monthly"`  
      - **Example Queries:**  
        - `"What are today's trending GitHub repos?"` → `since: "daily"`  
        - `"Show me the trending GitHub repos for this week."` → `since: "weekly"`  
        - `"What are the top GitHub projects this month?"` → `since: "monthly"`  
### 🚀 Function calling in action:  
```plaintext
!function show me trending GitHub repos 
```
---
### :sparkles: RAG Commands  
These commands allow for **document retrieval and LLM-powered responses**.

- **`!rag`**  
  Uploads a document to Django’s backend, triggering the **RAG pipeline** for indexing.  
  - **Supported Formats:** `.pdf`, `.py`, `.ipynb`, `.xlsx`, `.xls`, `.txt`  
  - **Example:** Attach a file and type `!rag`

- **`!rag_query [query]`**  
  Searches stored documents in **Qdrant** and returns **relevant text chunks**.  
  - **Example:** `!rag_query How does alpha-beta pruning selection work?`  
  - Creates a dedicated **Discord thread** for responses.  
  - Splits long chunks into multiple messages, labeled **Part 1, Part 2, etc.**  

- **`!query [query]`**  
  Sends the query to the **LLM directly** after retrieving documents Qdrant and passing them as context.  
  - **Example:** `!query Explain reinforcement learning`  
  - The bot **indicates typing** while processing the request.  
  - Creates a **Discord thread** for responses.  

---

## :loudspeaker: Agent Kitty Patch Notes

### **Version Update: New Features & Improvements**

#### :sparkles: What’s New | 2/3/2025
1. **RAG-Powered Commands** 🧠  
   - **`!rag`**: Upload and index documents into Qdrant.  
   - **`!rag_query`**: Retrieve relevant **document chunks** from Qdrant.  
   - **`!query`**: Query the **LLM directly**, skipping document retrieval.  

2. **Improved Message Formatting**  
   - **`!rag_query` & `!query`** create **Discord threads** for better organization.  
   - **Long responses are split into multiple messages** (labeled **Part 1, Part 2, etc.**).  

3. **Better UX** 🚀  
   - **Bot now shows "typing..."** while processing `!query` requests.  
   - Improved error handling & response formatting.  

#### :sparkles: What’s New | 1/30/2025
1. **`!prompt` Revamped**:
   - Returns only the **answer** for a smoother user experience.

2. **`!function` Added**:
   - Dynamically executes Python functions via JSON requests.
   - Available Functions:
     - 🆕 `calculate_sum`
     - 🆕 `scrape_github_trending`   

3. **`!summarize` Added**:
   - Upload `.txt` files to get summaries of up to 2000 characters.

---

### :gear: Improved User Experience
- **Typing Indicator**: Shows when Agent Kitty is actively processing commands.
- Backend optimizations for faster responses.

---

## :bulb: Contribute
### Suggest New Features
We’re always looking to improve! Share your ideas for new functions, features, or enhancements for MicroRag or Agent Kitty.

### Ideas for Future Functions:
- `convert_units`: Converts between units.
- `roll_dice`: Rolls dice for tabletop games.
- `get_weather`: Fetches weather for a given location.
- `translate_text`: Translates text between languages.

---

## :fire: Try It Out
Get started with these commands:
- **`!prompt How do I use FastAPI?`**
- **`!function What is 3546 and 8997?`**
- **Upload a `.txt` file with `!summarize`.**

---

## :books: License
This project is licensed under the [GNU GPL v3 License](LICENSE). See the repository for more details.

---

## :link: Links
- GitHub: [MicroRag Repository](https://github.com/Fern-Ali/MicroRag)
- Documentation: Coming soon!
```
