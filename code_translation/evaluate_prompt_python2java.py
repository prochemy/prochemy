import os
import re
import httpx
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

# TODO: change the prompt
task_describe = """

"""

def GEN_SOLUTION(prompt):
    response = client.chat.completions.create(
        # model = "deepseek-chat",
        model="gpt-4o",
        messages=[
            {"role": "system", "content": task_describe},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1500,  # Set the maximum length of the generated result
        temperature=0.0
    )
    return response.choices[0].message.content

def extract_code(response_text):
    # Use regular expression to extract Java code block
    code_match = re.search(r'```java(.*?)```', response_text, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    return response_text.strip()

def process_python_file(python_file_path, output_dir):
    with open(python_file_path, 'r') as python_file:
        python_code = python_file.read()

    prompt = f"The Python code to be translated is as follows:\n```python\n{python_code}\n```"
    translated_code = GEN_SOLUTION(prompt)
    java_code = extract_code(translated_code)

    python_file_name = os.path.basename(python_file_path)
    java_file_name = python_file_name.replace('.py', '.java')
    output_path = os.path.join(output_dir, java_file_name)

    with open(output_path, 'w') as java_file:
        java_file.write(java_code)

def main():
    # TODO: change the following parameters
    # path to the dataset
    input_dir = ''

    # output path
    output_dir = ""

    os.makedirs(output_dir, exist_ok=True)

    python_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith('.py')]

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        list(tqdm(executor.map(lambda python_file: process_python_file(python_file, output_dir), python_files), total=len(python_files), desc="Translating Python files"))

if __name__ == "__main__":
    main()