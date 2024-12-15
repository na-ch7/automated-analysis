import pandas as pd
import base64
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
import seaborn as sns
import requests
import json
import sys
import os

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
        data = pd.read_csv(file_name)
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

# Specialized analysis functions
def outlier_detection(data, column):
    plt.figure(figsize=(8, 4))
    sns.boxplot(x=data[column])
    plt.title(f"Outlier Analysis for {column}")
    file_path = os.path.join(output_dir, f"outlier_analysis_{column}.png")
    plt.savefig(file_path)
    plt.close()
    return file_path

def correlation_analysis(data, column1, column2):
    plt.figure(figsize=(8, 6))
    sns.scatterplot(x=data[column1], y=data[column2])
    plt.title(f"Correlation Analysis: {column1} vs {column2}")
    file_path = os.path.join(output_dir, f"correlation_analysis_{column1}_vs_{column2}.png")
    plt.savefig(file_path)
    plt.close()
    return file_path

def clustering_analysis(data, columns):
    cluster_data = data[columns].dropna()
    kmeans = KMeans(n_clusters=3, random_state=42).fit(cluster_data)
    cluster_data["Cluster"] = kmeans.labels_
    # Visualization
    plt.figure(figsize=(8, 6))
    sns.scatterplot(x=cluster_data[columns[0]], y=cluster_data[columns[1]], hue=cluster_data["Cluster"], palette="viridis")
    plt.title(f"Clustering Analysis: {columns[0]} vs {columns[1]}")
    file_path = os.path.join(output_dir, f"clustering_analysis_{columns[0]}_vs_{columns[1]}.png")
    plt.savefig(file_path)
    plt.close()
    return file_path

function_descriptions = [
    {
        "name": "outlier_detection",
        "description": "Detects and visualizes outliers in a specified column of the dataset.",
        "parameters": {
            "type": "object",
            "properties": {
                "column": {
                    "type": "string",
                    "description": "The name of the column to analyze for outliers."
                }
            },
            "required": ["column"]
        }
    },
    {
        "name": "correlation_analysis",
        "description": "Performs correlation analysis between two columns and visualizes the relationship.",
        "parameters": {
            "type": "object",
            "properties": {
                "column1": {
                    "type": "string",
                    "description": "The name of the first column."
                },
                "column2": {
                    "type": "string",
                    "description": "The name of the second column."
                }
            },
            "required": ["column1", "column2"]
        }
    },
    {
        "name": "clustering_analysis",
        "description": "Performs clustering analysis on specified columns and visualizes the clusters.",
        "parameters": {
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "The list of column names to use for clustering analysis."
                }
            },
            "required": ["columns"]
        }
    }
]

# Function to send a request to LLM for summaries and function call suggestions
def ask_llm_for_analysis(summary, api_url, api_key):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    prompt = (
        f"Analyse this data: {json.dumps(summary)}, and give a concise summary. "
        "For specialized analysis, call one of the functions with relevant parameters (columns of the dataset)."
    )
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "functions": function_descriptions,
        "function_call": "auto",
        "max_tokens": 1000,
    }
    try:
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        print("Full Response:", json.dumps(data, indent=2))
        if "choices" in data and data["choices"]:
                return data["choices"][0]["message"]
        else:
                print("No valid response from LLM.")
                return None
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with the LLM: {e}")
        return None

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Create a Markdown report
def create_readme(analysis, charts, api_key, url):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    #chart_descriptions = ""
    for chart in charts:
        base64_image = encode_image(chart)  # Get base64 string of the image
        #chart_descriptions += f"![Chart](data:image/png;base64,{base64_image})\n"
    
    prompt = (
            f"Analyze this information: {analysis}. Use the attached charts below to create a concise and engaging "
            "narrative that includes a description of the data, analysis performed, insights discovered, and implications "
            f"of the findings" #Attached Charts:\n{chart_descriptions}
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}",
                            "detail": "low"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1000,
    }
    try:
        response = requests.post(url, headers=headers, data={"payload": json.dumps(payload)})
        response.raise_for_status()
        readme = response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with the LLM: {e}")
        return None

    with open("README.md", "w") as readme_file:
        readme_file.write("# Analysis Summary of {filename}\n\n")
        readme_file.write(f"{readme}\n\n")
        readme_file.write("## Charts\n")
        for chart in charts:
            readme_file.write(f"![{chart}]({chart})\n")

def main():

    api_key = os.environ.get("AIPROXY_TOKEN")
    if not api_key:
        print("API key not found. Please set the AIPROXY_TOKEN environment variable.")
        sys.exit(1)
    print(api_key)
    api_url = "https://aiproxy.sanand.workers.dev/openai/"

    data, summary = analyze_csv(file_name)
    if summary is None:
        sys.exit(1)
    
    analysis = ask_llm_for_analysis(summary, api_url, api_key)
    if not analysis:
        print("Failed to get analysis from LLM.")
        sys.exit(1)

    function_calls = []
    charts = []
    if "function_call" in analysis:
        function_call = analysis["function_call"]
        function_name = function_call["name"]
        function_args = json.loads(function_call["arguments"])

        try:
            selected_function = globals()[function_name]
            chart_path = selected_function(data, **function_args)
            charts.append(chart_path)
            function_calls.append(f"{function_name}: {function_args}")
        except Exception as e:
            print(f"Error executing function {function_name}: {e}")
    else:
        print("No specialized analysis suggested by LLM.")
    try:
        create_readme(analysis, charts, api_key, api_url)
        print("README.md generated successfully.")
    except Exception as e:
        print(f"Error generating README: {e}")

if __name__ == "__main__":
    main()
