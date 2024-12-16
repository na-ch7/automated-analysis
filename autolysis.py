# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "uv",
#     "pandas",
#     "matplotlib",
#     "seaborn",
#     "dotenv",
#     "chardet",
#     "requests",
#     "json",
#     "sys",
#     "os",
#     "scipy.stats"
# ]
# ///

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv
import chardet
import requests
import json
import sys
import os
from scipy.stats import pearsonr

if len(sys.argv) != 2:
    print("Usage: uv run autolysis.py dataset.csv")
    sys.exit(1)

file_name = sys.argv[1]
dataset_name = os.path.splitext(os.path.basename(file_name))[0]
output_dir = os.path.join(os.getcwd(), dataset_name)
os.makedirs(output_dir, exist_ok=True)

# Function to perform generic analysis on the CSV
def analyze_csv(file_name):
    try:
        with open(file_name, 'rb') as f:
            result = chardet.detect(f.read())
            encoding = result['encoding']

        data = pd.read_csv(file_name, encoding=encoding)
    except Exception as e:
        print(f"Error reading the CSV file: {e}")
        return None, None

    summary = {
        "Name": file_name,
        "Shape": data.shape,
        "Columns": data.columns.tolist(),
        "Sample Data": data.head(5).to_dict(),
        "Summary Stats": data.describe(include='all').to_dict(),
    }
    return data, summary

def correlation_matrix(data):
    df = pd.DataFrame(data)
    numeric_columns = df.select_dtypes(include=['number'])
    correlation = numeric_columns.corr()
    plt.figure(figsize=(10, 8))
    sns.heatmap(correlation, annot=True, cmap='coolwarm', fmt='.2f', linewidths=0.5)
    plt.title("Correlation Matrix of Numerical Columns")
    file_path = os.path.join(output_dir, "correlation_matrix.png")
    plt.savefig(file_path)
    plt.close()
    return file_path

def correlation_analysis(data, column1, column2):
    if column1 not in data.columns or column2 not in data.columns:
        return None, "One or both columns are not in the dataset."
    data[column1] = pd.to_numeric(data[column1], errors='coerce')
    data[column2] = pd.to_numeric(data[column2], errors='coerce')

    data_cleaned = data.dropna(subset=[column1, column2])

    if data[column1].dtype != 'float64' and data[column1].dtype != 'int64':
        raise ValueError(f"Column {column1} is not numeric after conversion.")
    if data[column2].dtype != 'float64' and data[column2].dtype != 'int64':
        raise ValueError(f"Column {column2} is not numeric after conversion.")
    
    if len(data_cleaned[column1]) < 2 or len(data_cleaned[column2]) < 2:
        return {"insufficient data for correlation - skip in analysis"}

    correlation_coefficient, p_value = pearsonr(data[column1], data[column2])
    
    # Check for statistical significance (typically p < 0.05)
    significance = "statistically significant" if p_value < 0.05 else "not statistically significant"
    
    # Create a scatter plot of the correlation
    plt.figure(figsize=(8, 6))
    sns.scatterplot(x=data[column1], y=data[column2])
    plt.title(f"Correlation Analysis: {column1} vs {column2}")
    file_path = os.path.join(output_dir, f"correlation_analysis_{column1}_vs_{column2}.png")
    plt.savefig(file_path)
    plt.close()
    
    # Return the correlation results and the path to the generated chart
    result = {
        "correlation_coefficient": correlation_coefficient,
        "p_value": p_value,
        "significance": significance,
        "chart_path": file_path
    }
    
    return result

# Function to send a request to LLM for summary and function call
def llm_argument_generation(data, api_url, api_key):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    prompt = (
        "Give a JSON of column_pairs array of upto 4 column pairs on which correlation analysis would be useful."
    )
    schema = {
        "type": "object",
        "properties": {
            "column_pairs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                "column1": {
                    "type": "string",
                    "description": "The name of the first column for correlation analysis."
                },
                "column2": {
                    "type": "string",
                    "description": "The name of the second column for correlation analysis."
                }
                },
                "required": ["column1", "column2"],
                "additionalProperties": False
            },
            "description": "An array of objects where each object represents a pair of columns for correlation analysis."
            }
        },
        "required": ["column_pairs"],
        "additionalProperties": False
    }
    payload = {
        "model": "gpt-4o-mini",
        "response_format": {
            "type": "json_schema", 
            "json_schema": {
                "name": "correlation_analysis_schema",
                "schema": schema}
        },
        "messages": [
            {
                "role": "system", 
                "content": prompt
            },
            {
                "role": "user", 
                "content": json.dumps({col: str(dtype) for col, dtype in data.dtypes.to_dict().items()})

            },
            ],
        "max_tokens": 500,
    }
    try:
        response = requests.post(api_url, headers=headers, json=payload)
        result = response.json()


        print("Full Response:", json.dumps(result, indent=2))
        if "choices" in result and result["choices"]:
                return json.loads(result["choices"][0]["message"]["content"])
        else:
                print("No valid response from LLM.")
                return None
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with the LLM: {e}")
        return None

# Create a Markdown report
def create_readme(summary, corr_analysis, charts, api_key, url):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    prompt = (
            f"As a creative data analyst, use the summary and correlation details to create markdown text for a concise and engaging "
            "narrative that includes a description of the data, analysis performed, insights discovered, and implications "
            f"of the findings."
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system", 
                "content": prompt
            },
            {
                "role": "user", 
                "content": f"Summary: {summary}\n\nCorrelation Analysis: {corr_analysis}"
            },
            ],
        "max_tokens": 1000,
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        readme_text = response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with the LLM: {e}")
        return None
    
    readme_path = os.path.join(output_dir, "README.md")

    with open(readme_path, "w") as readme_file:
        readme_file.write(f"{readme_text}\n\n")
        readme_file.write("## Visualization: \n")
        for chart in charts:
            readme_file.write(f"![{chart}]({chart})\n")

def main():
    load_dotenv()
    api_key = os.environ.get("AIPROXY_TOKEN")
    api_url = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"

    if not api_key:
        print("API key not found. Please set the AIPROXY_TOKEN environment variable.")
        sys.exit(1)

    data, summary = analyze_csv(file_name)
    if summary is None:
        sys.exit(1)
    
    arguments = llm_argument_generation(data, api_url, api_key)
    if not arguments:
        print("Failed to get arguments from LLM.")
        sys.exit(1)

    charts = []
    file_path = correlation_matrix(data)
    charts.append(file_path)
    pairs = arguments["column_pairs"]
    for pair in pairs:
        c1 = pair["column1"]
        c2 = pair["column2"]
        result = correlation_analysis(data, c1, c2)
        if "correlation_analysis" in result:
            pair["correlation_analysis"] = result
            charts.append(result["chart_path"])

    try:
        create_readme(summary, arguments, charts, api_key, api_url)
        print("README.md generated successfully.")
    except Exception as e:
        print(f"Error generating README: {e}")

if __name__ == "__main__":
    main()
