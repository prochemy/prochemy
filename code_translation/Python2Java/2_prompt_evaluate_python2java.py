import os
import re
import json
import concurrent.futures
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Set the API key
client = OpenAI(
    base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

def GEN_SOLUTION(task_describe, prompt):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": task_describe},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1500,
        temperature=0.0
    )
    return response.choices[0].message.content

def extract_code(response_text):
    # Use regular expression to extract Java code block
    code_match = re.search(r'```java(.*?)```', response_text, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    return None

def process_python_file(python_file_path, task_describe, prompt_change, output_dir, progress_bar):
    with open(python_file_path, 'r') as python_file:
        python_code = python_file.read()

    # python2java
    prompt = prompt_change + f"The Python code to be translated is as follows:\n```python\n{python_code}\n```"

    java_code = None
    attempts = 0
    while java_code is None and attempts < 3:  # Retry multiple times, up to 3 times
        translated_code = GEN_SOLUTION(task_describe, prompt)
        java_code = extract_code(translated_code)
        if java_code is None:
            print(f"Failed to extract valid Java code from response. Retrying... (Attempt {attempts + 1})")
        attempts += 1

    if java_code is None:
        raise ValueError("Failed to extract valid Java code after multiple attempts.")

    python_file_name = os.path.basename(python_file_path)

    # python2java
    java_file_name = python_file_name.replace('.py', '.java')

    output_path = os.path.join(output_dir, java_file_name)

    with open(output_path, 'w') as java_file:
        java_file.write(java_code)

    progress_bar.update(1)

def process_prompt_data(prompt_data, python_files, output_base_dir):
    prompt_id = str(prompt_data["prompt_id"])  # Convert prompt_id to string
    mutated_prompt = prompt_data["mutated_prompt"]
    task_describe = prompt_data.get("task_describe", "You are an expert programming assistant.")  # Default description

    output_dir = os.path.join(output_base_dir, prompt_id)
    os.makedirs(output_dir, exist_ok=True)

    with tqdm(total=len(python_files), desc=f"Processing prompt_id {prompt_id}", unit="file") as progress_bar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_python_file, python_file_path, task_describe, mutated_prompt, output_dir, progress_bar)
                       for python_file_path in python_files]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    print(f'Generated an exception: {exc}')

def main():
    # TODO: change the following parameters
    # Prompt file to be evaluated
    input_file = ""
    # Root directory for output code
    output_base_dir = ""
    # Directory containing the Python code to be translated
    input_dir = ""

    python_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith('.py')]
    # Read the jsonl file
    with open(input_file, 'r') as file:
        lines = file.readlines()
        prompt_data_list = [json.loads(line) for line in lines]

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_prompt_data, prompt_data, python_files, output_base_dir) for prompt_data in prompt_data_list]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(prompt_data_list), desc="Overall progress"):
            try:
                future.result()
            except Exception as exc:
                print(f'Generated an exception: {exc}')

if __name__ == "__main__":
    main()