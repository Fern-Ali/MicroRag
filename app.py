import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline, BitsAndBytesConfig
# from janus.models import MultiModalityCausalLM, VLChatProcessor
# from janus.utils.io import load_pil_images
from typing import List, Optional

# Initialize FastAPI app
app = FastAPI()

# Explicitly handle VRAM and offloading
bnb_config = BitsAndBytesConfig(
    load_in_8bit=True,
    llm_int8_enable_fp32_cpu_offload=True,  # Offload large layers to CPU when needed
)
# Load the model and tokenizer
# MODEL_NAME = "EleutherAI/gpt-neo-2.7B"  # Replace with your Llama model if needed
# MODEL_NAME = "meta-llama/Llama-2-7b-hf"

# use this when approved
MODEL_NAME = "meta-llama/Llama-3.2-3B-Instruct"
# MODEL_NAME = "deepseek-ai/Janus-Pro-7B" # soon to test, TODO: janus deepseek model 

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_auth_token=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    device_map="auto",          # Automatically uses GPU (and CPU if needed)
    quantization_config=bnb_config,  # Use the efficient quantization
    torch_dtype="auto",         # Use appropriate precision
    token=os.getenv("hgf_access_token")  # Use your environment variable
)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    device_map="auto",          # Automatically uses GPU if available
    torch_dtype="auto",         # Adjust precision based on hardware
    load_in_8bit=True           # Enable 8-bit quantization for memory efficiency
)
generator = pipeline("text-generation", model=model, tokenizer=tokenizer)

# Define input schema
class InferenceRequest(BaseModel):
    prompts: Optional[List[str]] = None  # For batch generation
    context: Optional[str] = None  # For single prompt with context
    query: Optional[str] = None  # Query for single prompt generation
    max_length: int = 200  # Maximum length of generated text


async def llama(prompt):         
    response = generator(
        prompt, 
        max_length=400, 
        num_return_sequences=1,
        truncation=True
    )
    return response[0]["generated_text"]


@app.post("/batch_generate")
async def batch_generate(request: InferenceRequest):
    try:
        # Validate that prompts are provided
        if not request.prompts:
            raise HTTPException(status_code=400, detail="Prompts are required for batch generation.")
        
        # Generate responses for all prompts in the batch
        responses = generator(
            request.prompts,
            max_length=request.max_length,
            num_return_sequences=1,
            return_full_text=False
        )
        # Extract generated text
        results = [response[0]["generated_text"] for response in responses]
        return {"responses": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/generate")
async def generate(request: InferenceRequest):
    try:
        # Validate that query is provided
        if not request.query:
            raise HTTPException(status_code=400, detail="Query is required for single generation.")
        
        # Handle cases where context is optional
        if request.context:
            # prompt = f"Context: {request.context}\n\nQuery: {request.query}\nAnswer:"
            prompt = (
                f"Use the following retrieved context to answer the query.\n\n"
                f"### Context:\n{request.context}\n\n"
                f"### Query:\n{request.query}\n\n"
                f"### Answer:"
            )
        else:
            prompt = f"Query: {request.query}\nAnswer:"
        
        response = generator(
            prompt, 
            # max_length=request.max_length, 
            max_new_tokens=300,  # Allow up to 200 tokens for the output
            # max_new_tokens=request.max_length
            num_return_sequences=1
        )
        generated_text = response[0]["generated_text"]
        
        # Extract text after "Answer:"
        if "Answer:" in generated_text:
            generated_answer = generated_text.split("Answer:", 1)[-1].strip()
        else:
            generated_answer = generated_text.strip()
            
        return {"response": generated_answer}
        # return {"response": response[0]["generated_text"]}
    except Exception as e:
        # Log the error and return a clear message
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# curl -X POST "http://127.0.0.1:8001/generate" \
# -H "Content-Type: application/json" \
# -d '{
#     "context": "Name least 3.",
#     "query": "What are the branches of artificial intelligence?",
#     "max_length": 150
# }'

# curl -X POST "http://127.0.0.1:8001/generate" \
# -H "Content-Type: application/json" \
# -d '{
#     "context": "",
#     "query": " What are the branches of artificial intelligence?",
#     "max_length": 150
# }'