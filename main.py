import json
import openai
import os
import logging
import sys
import re
from io import StringIO
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

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
    allow_origins=["*"],
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
    vega_spec: dict = None
    analysis_result: str = None

# Sanitize input for Python REPL execution
def sanitize_input(query: str) -> str:
    query = re.sub(r"^(\s|`)*(?i:python)?\s*", "", query)
    query = re.sub(r"(\s|`)*$", "", query)
    return query

# Execute the Python code for data analysis
import pandas as pd
from io import StringIO
import sys
import logging

def execute_panda_dataframe_code(code):
    logging.info(f"Generated Python Code:\n{code}")  # Log the generated Python code

    old_stdout = sys.stdout
    sys.stdout = mystdout = StringIO()
    last_dataframe = None  # To store the last detected DataFrame
    last_series = None  # To store the last detected Series

    # Variables to ignore, e.g., 'df' is for raw data and should not be returned
    ignore_vars = ['df']

    # Check if the last line of the code contains a single quote
    code_lines = code.strip().splitlines()
    last_line = code_lines[-1] if code_lines else ""
    contains_text_output = "'" in last_line

    try:
        # Define a local dictionary with 'pd' to provide context for exec
        local_vars = {'pd': pd}
        cleaned_command = sanitize_input(code)
        
        # Execute code within this local namespace
        exec(cleaned_command, {}, local_vars)
        sys.stdout = old_stdout

        # Check if there was printed output (e.g., from print("hello"))
        printed_output = mystdout.getvalue().strip()
        
        # If the last line contains text (a single quote), return only the printed text
        if contains_text_output and printed_output:
            return printed_output

        # If no explicit text output, check for DataFrames and Series
        for var_name, var_value in local_vars.items():
            if var_name in ignore_vars:
                continue  # Skip variables we want to ignore
            if isinstance(var_value, pd.DataFrame):
                last_dataframe = var_value  # Update to the latest non-ignored DataFrame found
            elif isinstance(var_value, pd.Series):
                last_series = var_value  # Update to the latest non-ignored Series found

        # If a non-ignored DataFrame was found, return it as HTML
        if last_dataframe is not None:
            return last_dataframe.to_html(index=False)

        # If no DataFrame but a Series was found, return it as HTML
        if last_series is not None:
            return last_series.to_frame().to_html(header=True, index=True)

        # If neither is found, return any standard text output
        return printed_output
    except Exception as e:
        sys.stdout = old_stdout
        return repr(e)






# Data analysis function description in OpenAI format
data_analysis_function_tool = {
    "type": "function",
    "function":{
        "name": "data_analysis",
        "description": "Performs data analysis based on the user's request by generating Python code to analyze a provided dataset. This function excludes any chart or visualization generation.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_query": {
                    "type": "string",
                    "description": "The user's request for data analysis, which specifies the type of analysis to perform on the dataset.",
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "A list of column names in the dataset relevant to the analysis.",
                },
                "dataTypes": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "A dictionary with column names as keys and their respective data types as values.",
                },
                "sampleData": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "A list of sample rows from the dataset to provide context to the analysis.",
                },
            },
            "required": ["user_query", "columns", "dataTypes", "sampleData"],
            "additionalProperties": False,
        },
    }
}

# Chart generation function description in OpenAI format
chart_generation_function_description = {
    "type": "function",
    "function":{
        "name": "chart_generation",
        "description": "Generates a Vega-Lite chart specification based on the user's request. This function creates the JSON code needed to render the chart visualization.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_query": {
                    "type": "string",
                    "description": "The user's request for a specific chart type, specifying what kind of chart to create with the dataset.",
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "A list of column names in the dataset relevant to the chart creation.",
                },
                "dataTypes": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "A dictionary with column names as keys and their respective data types as values.",
                },
                "sampleData": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "A list of sample rows from the dataset to provide context for the chart.",
                },
            },
            "required": ["user_query", "columns", "dataTypes", "sampleData"],
            "additionalProperties": False,
        },
    }
}


# Helper functions for debugging
def print_red(*strings):
    print("\033[91m" + " ".join(strings) + "\033[0m")

def print_blue(*strings):
    print("\033[94m" + " ".join(strings) + "\033[0m")

def chart_generation(user_query, columns, dataTypes, sampleData):
    prompt = construct_prompt(user_query, columns, dataTypes, sampleData, "chart")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a data visualization assistant. Generate a Vega-Lite specification if the user's request requires chart generation."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=3000,
        temperature=0.3,
    )
    assistant_message = response['choices'][0]['message']['content']
    vega_spec, description, is_relevant = parse_assistant_response(assistant_message, "chart")
    if not is_relevant:
        return None, "Your question does not seem to be related to the dataset. Please ask a question relevant to the data."
    return vega_spec, description

# Data analysis function
def data_analysis(user_query, columns, dataTypes, sampleData):
    prompt = construct_prompt(user_query, columns, dataTypes, sampleData, "analysis")
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a data analysis assistant. Generate Python code if the user's request requires data analysis."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=3000,
        temperature=0.3,
    )
    assistant_message = response['choices'][0]['message']['content']
    logging.info(f"Assistant Response (Python Code and Description): {assistant_message}")  # Log the raw response from assistant

    code_snippet, description, is_relevant = parse_assistant_response(assistant_message, "analysis")
    if not is_relevant:
        return None, "Your question does not seem to require data analysis. Please ask a question relevant to data analysis."
    result = execute_panda_dataframe_code(code_snippet)
    return result, description

# Unified request handling function with ReAct loop
def handle_request(user_query, columns, dataTypes, sampleData, max_iterations=3):
    tool_descriptions = {
        "data_analysis": data_analysis_function_tool,
        "chart_generation": chart_generation_function_description
    }
    
    # Prepare prompt
    prompt = construct_prompt(user_query, columns, dataTypes, sampleData, "determine", tool_descriptions)
    messages = [
        {"role": "system", "content": "You are a data assistant. Determine if the user's request requires data analysis, graph generation, both, or neither."},
        {"role": "user", "content": prompt},
    ]

    for iteration in range(max_iterations):
        print(f"Iteration: {iteration + 1}")

        # Call OpenAI API for type determination
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=2000,
            temperature=0.3,
        )
        
        assistant_message = response['choices'][0]['message']

        # Check if the response includes a valid content message
        if assistant_message.get("content"):
            result = parse_assistant_response(assistant_message["content"], "determine")
            request_type = result["type"]

            if request_type in ["chart", "analysis", "both"]:
                # Based on determined request type, handle specific tasks
                if request_type == "chart":
                    vega_spec, description = chart_generation(user_query, columns, dataTypes, sampleData)
                    if vega_spec:
                        return {"type": "chart", "vega_spec": vega_spec, "description": description}
                
                elif request_type == "analysis":
                    analysis_result, description = data_analysis(user_query, columns, dataTypes, sampleData)
                    if analysis_result:
                        return {"type": "analysis", "analysis_result": analysis_result, "description": description}

                elif request_type == "both":
                    vega_spec, chart_desc = chart_generation(user_query, columns, dataTypes, sampleData)
                    analysis_result, analysis_desc = data_analysis(user_query, columns, dataTypes, sampleData)
                    if vega_spec and analysis_result:
                        return {
                            "type": "both",
                            "vega_spec": vega_spec,
                            "analysis_result": analysis_result,
                            "description": f"{chart_desc} {analysis_desc}"
                        }
            
            # If no valid tool call was detected, append the assistant's response and continue the loop
            messages.append(assistant_message)

        # If the max iterations are reached without completion
        if iteration == max_iterations - 1:
            print("Max iterations reached.")
            return {"type": "none", "description": "The assistant could not complete the task in the given time. Please try again."}

    return {"type": "none", "description": "Your question does not relate to the dataset."}

# Endpoint to interact with OpenAI API
@app.post("/query", response_model=QueryResponse)
async def query_openai(request: QueryRequest):
    try:
        result = handle_request(request.query, request.columns, request.dataTypes, request.FullData)
        if result["type"] == "chart":
            return QueryResponse(vega_spec=result["vega_spec"], description=result["description"])
        elif result["type"] == "analysis":
            return QueryResponse(analysis_result=result["analysis_result"], description=result["description"])
        elif result["type"] == "both":
            return QueryResponse(vega_spec=result["vega_spec"], analysis_result=result["analysis_result"], description=result["description"])
        else:
            return QueryResponse(description="Your question does not relate to the dataset.")
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {str(e)}")
        raise HTTPException(status_code=500, detail="Assistant's response was not in a valid JSON format.")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

# Construct prompt for OpenAI API
def construct_prompt(user_query, columns, dataTypes, sampleData, query_type, tool_descriptions=None):
    dataset_info = f"Dataset columns and types:\n"
    for col in columns:
        dataset_info += f"- {col}: {dataTypes[col]}\n"
    dataset_info += "Sample data:\n"
    for row in sampleData:
        dataset_info += f"{row}\n"

        # Include tool descriptions in the prompt if provided
    tool_desc = ""
    if tool_descriptions:
        tool_desc = "Tool Descriptions:\n"
        for tool_name, tool in tool_descriptions.items():
            tool_desc += f"{tool_name.capitalize()} - {tool['function']['description']}\n"
    
    # Tailored prompt based on query type

    if query_type == "chart":
        prompt = (
            f"**You are a data visualization assistant. The user provided this request: '{user_query}'.\n"
            f"You have access to the following dataset information:\n{dataset_info}\n"
            f"generate a Vega-Lite JSON specification for a chart that satisfies the user's request. Format the response as follows:\n"
            f"{{\n"
            f'"vega_spec": {{\n'
            f'"$schema": "https://vega.github.io/schema/vega-lite/v5.json",\n'
            f'"description": "...",\n'
            f'"data": {{"values": [..]}}, # Sample data or reference to dataset\n'
            f'"mark": "...", # Chart type (e.g., "bar", "line", etc.)\n'
            f'"encoding": {{\n"x": {{...}}, # Field mappings for X-axis\n"y": {{...}}, # Field mappings for Y-axis\n... # Additional encoding if needed\n'
            f'}}}},\n'
            f'"description": "A brief description of the generated chart."\n'
            f"}}\n"
            f"Respond **only** in JSON format with 'vega_spec' for the chart specification and 'description' for an explanation.\n"
        )
    elif query_type == "analysis":
        prompt = (
            f"You are a data analysis assistant. Your task is to analyze the data based on the user's request: '{user_query}'. "
            f"Only focus on data analysis tasks and do not include any chart or visualization generation code, such as scatter plots, line charts, or other graphs. "
            f"Generate a Python code solution that performs the requested analysis without any plotting commands.\n"
            f"Respond strictly in JSON format with two keys: 'code' (a single string containing the complete Python code block) and 'description' (an explanation of the analysis in words).\n"
            f"Ensure the response is complete and valid JSON with no syntax errors, as this code will be run by a specific program to generate text-based answers for the user. "
            f"Dataset information: {dataset_info}"
        )
    elif query_type == "determine":
        prompt = (
            f"You are a data assistant. The user provided this request: '{user_query}'.\n"
            f"{tool_desc}"
            f"Based on the tool descriptions and the dataset information, determine if the user's request requires data analysis, chart generation, both, or neither.Check if the user's question is directly related to the dataset. A question is relevant if it includes keywords or terms that match the dataset columns, types, or content.\n"
            f"Dataset information:\n{dataset_info}\n"
            f"Respond in JSON format with 'type' (options: 'chart', 'analysis', 'both', 'none') and 'description' explaining the response.\n"
        )
    elif query_type == "both":
        prompt = (
            f"The user provided this request: '{user_query}', which requires both data analysis and chart generation.\n"
            f"1. First, generate Python code for the data analysis required to fulfill the user's request.\n"
            f"2. Then, create a Vega-Lite JSON specification for the chart.\n"
            f"Respond **only** in JSON format with the following structure:\n"
            f"{{\n"
            f" 'code': '<Python code for analysis>',\n"
            f" 'vega_spec': <Vega-Lite JSON specification>,\n"
            f" 'description': 'Brief explanation of the chart and analysis.'\n"
            f"}}\n"
            f"Dataset information:\n{dataset_info}\n"
        )
    return prompt

# Parse response from OpenAI
def parse_assistant_response(response_content, query_type):
    logging.info(f"Raw assistant response content: {response_content}")
    if response_content.startswith("```json"):
        response_content = response_content.strip("```json").strip()
    elif response_content.startswith("```"):
        response_content = response_content.strip("```").strip()

    try:
        # Attempt to parse the response as JSON
        response_json = json.loads(response_content)

        # Check if the JSON response has the expected structure for each query type
        if query_type == "chart":
            vega_spec = response_json.get("vega_spec")
            description = response_json.get("description")
            if vega_spec and description:
                return vega_spec, description, True
            else:
                logging.warning("Incomplete JSON response for chart generation.")
                return None, "The assistant did not provide a valid chart specification.", False

        elif query_type == "analysis":
            code_snippet = response_json.get("code")
            description = response_json.get("description")
            if code_snippet and description:
                return code_snippet, description, True
            else:
                logging.warning("Incomplete JSON response for data analysis.")
                return None, "The assistant did not provide valid Python code for analysis.", False

        elif query_type == "both":
            vega_spec = response_json.get("vega_spec")
            code_snippet = response_json.get("code")
            description = response_json.get("description")
            if vega_spec and code_snippet and description:
                return {"vega_spec": vega_spec, "code": code_snippet, "description": description}, True
            else:
                logging.warning("Incomplete JSON response for both chart and analysis.")
                return None, "The assistant did not provide complete information for both chart and analysis.", False

        elif query_type == "determine":
            return {"type": response_json.get("type")}

    except json.JSONDecodeError:
        # If JSON decoding fails, assume the response is plain text
        logging.error("Failed to parse response as JSON.")
        logging.error(f"Response content that caused error: {response_content}")

        # Handle plain text response that may be guidance or incomplete
        if "I'm here to help" in response_content.lower():
            return None, "The assistant returned a general guidance message.", False
        elif "does not require" in response_content.lower():
            return {"type": "none", "description": response_content}

        # Raise an HTTP error if parsing failed for another reason
        raise HTTPException(status_code=500, detail="The assistant's response was not in a valid JSON format.")

# Root endpoint
@app.get("/")
async def read_root():
    return FileResponse('static/index.html')
