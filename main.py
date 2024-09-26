import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import os
from dotenv import load_dotenv
import logging  # Add this for logging

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to restrict allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load OpenAI API key from environment variable
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Define request and response models
class QueryRequest(BaseModel):
    query: str
    columns: list
    dataTypes: dict
    FullData: list

class QueryResponse(BaseModel):
    vega_spec: dict
    description: str

# Endpoint to interact with OpenAI API
@app.post("/query", response_model=QueryResponse)
async def query_openai(request: QueryRequest):
    try:
        # Construct the prompt
        prompt = construct_prompt(request.query, request.columns, request.dataTypes, request.FullData)
        
        # Call the OpenAI API with the chat model
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  
            messages=[
                {"role": "system", "content": "You are a data visualization assistant. Generate Vega-Lite specifications."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.3  # Lower temperature to make responses more predictable
        )

        # Log the raw response
        assistant_message = response['choices'][0]['message']['content']
        logging.info(f"Assistant raw response: {assistant_message}")
        
        # Parse the assistant's message to extract the Vega-Lite spec and description
        vega_spec, description = parse_assistant_response(assistant_message)
        
        return QueryResponse(vega_spec=vega_spec, description=description)
    
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {str(e)}")  # Log the actual error
        raise HTTPException(status_code=500, detail="Assistant's response was not in a valid JSON format.")
    
    except Exception as e:
        logging.error(f"Error occurred: {str(e)}")  # Log the actual error
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


def construct_prompt(user_query, columns, dataTypes, sampleData):
    # Construct dataset information
    dataset_info = f"Dataset columns and types:\n"
    for col in columns:
        dataset_info += f"- {col}: {dataTypes[col]}\n"
    dataset_info += "Sample data:\n"
    for row in sampleData:
        dataset_info += f"{row}\n"

    # Construct the full prompt
    prompt = (
                    f"""
            You are an expert data visualization assistant. The user provided this request: '{user_query}'.
            You have access to the following dataset information:
            {dataset_info}

            Please generate a Vega-Lite JSON specification for a chart that satisfies the user's query using the dataset provided.
            Respond in the following JSON format:

            {{
            "vega_spec": {{
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "description": "...",
                "data": {{"values": [..]}},  # Sample data or reference to dataset
                "mark": "...",  # Chart type (e.g., "bar", "line", etc.)
                "encoding": {{
                "x": {{...}},  # Field mappings for X-axis
                "y": {{...}},  # Field mappings for Y-axis
                ...  # Additional encoding if needed
                }}
            }},
            "description": "A brief description of the generated chart."
            }}

            If the user's request is NOT related to data visualization, respond with:
            {{
            "bot_response": "Your request does not seem to be related to data visualization. Please ask a question about visualizing data from the provided dataset."
            }}"""
    )
    return prompt

def parse_assistant_response(response_content):
    import json
    try:
        # Try to parse the response as JSON
        response_json = json.loads(response_content)
        vega_spec = response_json.get('vega_spec')
        description = response_json.get('description')
        return vega_spec, description
    except json.JSONDecodeError:
        # Handle parsing error
        raise HTTPException(status_code=500, detail="Failed to parse assistant response as JSON.")

# Root endpoint
@app.get("/")
async def read_root():
    return FileResponse('static/index.html')
