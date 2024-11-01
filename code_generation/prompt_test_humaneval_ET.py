import re
import json
import os
from evalplus.data import write_jsonl
from openai import OpenAI
import concurrent.futures
from tqdm import tqdm
from dotenv import load_dotenv


load_dotenv()

# Set the API key
client = OpenAI(
    base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

# TODO: change the prompt
task_describe_template = """

"""


def GEN_SOLUTION(prompt, entry_point):
    attempts = 0
    task_describe = task_describe_template.format(entry_point=entry_point)

    while attempts < 5:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": task_describe},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.0
        )
        # Use regular expression to match content starting with ```python and ending with ```
        match = re.search(r'```python(.*?)```', response.choices[0].message.content, re.DOTALL)
        if match:
            code = match.group(1).strip()
            # Ensure that the generated code contains the correct function name
            if entry_point in code:
                return code
        attempts += 1

    # If no result after 5 attempts, print a message and return None
    print(f"Failed to extract valid Python code after 3 attempts for prompt: {prompt}")
    return None


def process_task(task_id, prompt, entry_point):
    completion = GEN_SOLUTION(prompt, entry_point)
    if completion is not None:
        return dict(task_id=task_id, entry_point=entry_point, completion=completion)
    else:
        return dict(task_id=task_id, entry_point=entry_point, completion="")


def load_tasks_from_jsonl(file_path):
    tasks = {}
    with open(file_path, 'r') as file:
        for line in file:
            task = json.loads(line)
            tasks[task['task_id']] = task
    return tasks


# TODO: change the following parameters
# Specify the file to read
input_file_path = '/path/to/dataset'
problems = load_tasks_from_jsonl(input_file_path)

if __name__ == "__main__":
    samples = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(process_task, task_id, problem["prompt"], problem["entry_point"])
            for task_id, problem in problems.items()
        ]

        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing tasks"):
            samples.append(future.result())

    output_file_path = "/output/path"
    write_jsonl(output_file_path, samples)
    print(f"Results saved to {output_file_path}")