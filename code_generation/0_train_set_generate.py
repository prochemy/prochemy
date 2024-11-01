import os
import json
import re
import httpx
import concurrent.futures
from tqdm import tqdm
from openai import OpenAI
import argparse 
from dotenv import load_dotenv

load_dotenv()

# Set API Key
client = OpenAI(
    base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

task_describe = """
You are an expert in software engineering.
"""

information = """
Please help me generate similar data based on the format provided below.
"""

prompt_template = """
The reference data format is as follows:
{"task_id": "HumanEval/0", "prompt": "from typing import List\n\n\ndef has_close_elements(numbers: List[float], threshold: float) -> bool:\n    \"\"\" Check if in given list of numbers, are any two numbers closer to each other than\n    given threshold.\n    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)\n    False\n    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)\n    True\n    \"\"\"\n", "entry_point": "has_close_elements", "canonical_solution": "    for idx, elem in enumerate(numbers):\n        for idx2, elem2 in enumerate(numbers):\n            if idx != idx2:\n                distance = abs(elem - elem2)\n                if distance < threshold:\n                    return True\n\n    return False\n", "test": "\n\nMETADATA = {\n    'author': 'jt',\n    'dataset': 'test'\n}\n\n\ndef check(candidate):\n    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True\n    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05) == False\n    assert candidate([1.0, 2.0, 5.9, 4.0, 5.0], 0.95) == True\n    assert candidate([1.0, 2.0, 5.9, 4.0, 5.0], 0.8) == False\n    assert candidate([1.0, 2.0, 3.0, 4.0, 5.0, 2.0], 0.1) == True\n    assert candidate([1.1, 2.2, 3.1, 4.1, 5.1], 1.0) == True\n    assert candidate([1.1, 2.2, 3.1, 4.1, 5.1], 0.5) == False\n\n"}
{"task_id": "HumanEval/1", "prompt": "from typing import List\n\n\ndef separate_paren_groups(paren_string: str) -> List[str]:\n    \"\"\" Input to this function is a string containing multiple groups of nested parentheses. Your goal is to\n    separate those group into separate strings and return the list of those.\n    Separate groups are balanced (each open brace is properly closed) and not nested within each other\n    Ignore any spaces in the input string.\n    >>> separate_paren_groups('( ) (( )) (( )( ))')\n    ['()', '(())', '(()())']\n    \"\"\"\n", "entry_point": "separate_paren_groups", "canonical_solution": "    result = []\n    current_string = []\n    current_depth = 0\n\n    for c in paren_string:\n        if c == '(':\n            current_depth += 1\n            current_string.append(c)\n        elif c == ')':\n            current_depth -= 1\n            current_string.append(c)\n\n            if current_depth == 0:\n                result.append(''.join(current_string))\n                current_string.clear()\n\n    return result\n", "test": "\n\nMETADATA = {\n    'author': 'jt',\n    'dataset': 'test'\n}\n\n\ndef check(candidate):\n    assert candidate('(()()) ((())) () ((())()())') == [\n        '(()())', '((()))', '()', '((())()())'\n    ]\n    assert candidate('() (()) ((())) (((())))') == [\n        '()', '(())', '((()))', '(((())))'\n    ]\n    assert candidate('(()(())((())))') == [\n        '(()(())((())))'\n    ]\n    assert candidate('( ) (( )) (( )( ))') == ['()', '(())', '(()())']\n"}
{"task_id": "HumanEval/2", "prompt": "\n\ndef truncate_number(number: float) -> float:\n    \"\"\" Given a positive floating point number, it can be decomposed into\n    and integer part (largest integer smaller than given number) and decimals\n    (leftover part always smaller than 1).\n\n    Return the decimal part of the number.\n    >>> truncate_number(3.5)\n    0.5\n    \"\"\"\n", "entry_point": "truncate_number", "canonical_solution": "    return number % 1.0\n", "test": "\n\nMETADATA = {\n    'author': 'jt',\n    'dataset': 'test'\n}\n\n\ndef check(candidate):\n    assert candidate(3.5) == 0.5\n    assert abs(candidate(1.33) - 0.33) < 1e-6\n    assert abs(candidate(123.456) - 0.456) < 1e-6\n"}
"""

format_instructions = """
Ensure that the data you provide is consistent with the reference data format, and that all test cases included in the data are correct.
Ensure that the generated data is different from the provided reference data.
Return the data in the same Json format as the reference data and wrapped the data with [Start] and [End].
"""

def GEN_ANSWER(prompt):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": task_describe},
            {"role": "user", "content": information + prompt + format_instructions}
        ],
        max_tokens=2000
    )
    return response.choices[0].message.content, response.usage.total_tokens

def extract_wrapped_content(text):
    match = re.search(r'\[Start\]\s*\n(.*?)\n\[End\]', text, re.DOTALL)
    if not match:
        return None
    content = match.group(1).strip()

    task_id_match = re.search(r'"task_id"\s*:\s*"([^"]+)"', content)
    task_id = task_id_match.group(1) if task_id_match else None

    prompt_match = re.search(r'"prompt"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
    prompt = prompt_match.group(1).replace('\n', '\\n') if prompt_match else None

    entry_point_match = re.search(r'"entry_point"\s*:\s*"([^"]+)"', content)
    entry_point = entry_point_match.group(1) if entry_point_match else None

    canonical_solution_match = re.search(r'"canonical_solution"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
    canonical_solution = canonical_solution_match.group(1).replace('\n', '\\n') if canonical_solution_match else None

    test_match = re.search(r'"test"\s*:\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
    test = test_match.group(1).replace('\n', '\\n') if test_match else None

    if task_id and prompt and entry_point and canonical_solution and test:
        extracted_data = {
            "task_id": task_id,
            "prompt": prompt,
            "entry_point": entry_point,
            "canonical_solution": canonical_solution,
            "test": test
        }
        return extracted_data
    return None

def process_task(task_id, prompt):
    total_tokens = 0
    while True:
        completion, tokens_used = GEN_ANSWER(prompt)
        total_tokens += tokens_used
        json_content = extract_wrapped_content(completion)
        if json_content:
            return json_content, total_tokens
        else:
            print(f"No valid Json data found for task {task_id}. Retrying...")

def main(output_path):
    samples = []
    total_tokens_used = 0
    problems = {i: {"prompt": prompt_template} for i in range(10)}  # Create 10 tasks

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_task, task_id, problem["prompt"]) for task_id, problem in problems.items()]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing tasks"):
            result, tokens_used = future.result()
            if result:
                samples.append(result)
                total_tokens_used += tokens_used

    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir) and output_dir:
        os.makedirs(output_dir)

    with open(output_path, 'w') as f:
        for sample in samples:
            f.write(json.dumps(sample) + '\n')

    print(f"Total tokens used: {total_tokens_used}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate data and save it to a specified output path.")
    parser.add_argument('--output_path', type=str, required=True, help="The output path for the generated data.")
    args = parser.parse_args()

    main(args.output_path)
