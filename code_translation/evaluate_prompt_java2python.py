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
    # Use regular expression to extract Python code block
    code_match = re.search(r'```python(.*?)```', response_text, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    return response_text.strip()

def process_java_file(java_file_path, output_dir):
    with open(java_file_path, 'r') as java_file:
        java_code = java_file.read()

    prompt = f"The Java code to be translated is as follows:\n```java\n{java_code}\n```"
    translated_code = GEN_SOLUTION(prompt)
    python_code = extract_code(translated_code)

    java_file_name = os.path.basename(java_file_path)
    python_file_name = java_file_name.replace('.java', '.py')
    output_path = os.path.join(output_dir, python_file_name)

    with open(output_path, 'w') as python_file:
        python_file.write(python_code)

def main():
    # TODO: change the following parameters
    # path to the dataset
    input_dir = ''

    # output path
    output_dir = ""

    os.makedirs(output_dir, exist_ok=True)

    java_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith('.java')]

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        list(tqdm(executor.map(lambda java_file: process_java_file(java_file, output_dir), java_files), total=len(java_files), desc="Translating Java files"))

if __name__ == "__main__":
    main()