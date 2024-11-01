import os
import json
import re
import httpx
import concurrent.futures
from tqdm import tqdm
from openai import OpenAI
from evalplus.data import write_jsonl
from dotenv import load_dotenv

load_dotenv()

# Set the API key
client = OpenAI(
    base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

task_describe = """
You are an expert prompt engineer.
"""

information = """
I need to translate Python code into Java code while maintaining the same functionality.
Maintaining the same functionality means that the translated Python code should pass all the test cases that the original Python code could pass.
I have a prompt written for this task. Based on the previous description, revise and optimize this prompt so that it can better guide the model to complete the code translation task effectively.
"""

prompt = """
The prompt ready to be optimized are as follows and wrapped in []:
[You are a code translation assistant. Your task is to translate the Python Code to Java Code.]\n
"""

format = """
You may add any information you think will help improve the task's effectiveness during the prompt optimization process.
If you find certain expressions and wording in the original prompt inappropriate, you can also modify these usages.
Ensure that the optimized prompt includes a detailed task description and clear process guidance added to the original prompt.
Ensure that the variables and intermediate results in the translated Java code are stored using the long type instead of the int type.
Wrap the optimized prompt in {{}}.
"""


def GEN_ANSWER(prompt):
    response = client.chat.completions.create(
        # model="deepseek-chat",
        model="gpt-4o",
        messages=[
            {"role": "system", "content": task_describe},
            {"role": "user", "content": information + prompt + format}
        ],
        max_tokens=500,  # Set the maximum length of the generated result, can be adjusted as needed
        temperature=1.0
    )
    return response.choices[0].message.content


def extract_wrapped_content(text):
    match = re.search(r'\{\{(.*?)\}\}', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        return None


def process_task(task_id, prompt):
    while True:
        completion = GEN_ANSWER(prompt)
        wrapped_content = extract_wrapped_content(completion)
        if wrapped_content:
            return dict(prompt_id=task_id, mutated_prompt=wrapped_content)
        else:
            print(f"Task {task_id}: No wrapped content found. Retrying...")


if __name__ == "__main__":
    samples = []
    problems = {i: {"prompt": prompt} for i in range(10)}  # Create 10 tasks

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_task, task_id, problem["prompt"]) for task_id, problem in problems.items()]

        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing tasks"):
            samples.append(future.result())

    # TODO: change the following parameters
    output_dir = "output/path"
    # output file in jsonl
    output_file_path = os.path.join(output_dir, "/output/file/name.jsonl")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    write_jsonl(output_file_path, samples)