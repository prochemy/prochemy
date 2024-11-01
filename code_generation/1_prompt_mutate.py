import os
import json
import re
import httpx
import concurrent.futures
from tqdm import tqdm
from openai import OpenAI
import argparse
import random
from evalplus.data import write_jsonl
from dotenv import load_dotenv

load_dotenv()

# Set API Key
client = OpenAI(
    base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

task_describe = """
You are an expert prompt engineer.
"""

information = """
Please help me improve the given prompt to get a more helpful and harmless response.
Suppose I need to generate a Python program based on natural language descriptions.
The generated Python program should be able to complete the tasks described in natural language and pass any test cases specific to those tasks.\n
"""

format = """
You may add any information you think will help improve the task's effectiveness during the prompt optimization process.
If you find certain expressions and wording in the original prompt inappropriate, you can also modify these usages.
Ensure that the optimized prompt includes a detailed task description and clear process guidance added to the original prompt.
Wrap the optimized prompt in {{}}.
"""


def GEN_ANSWER(prompt, model):
    response = client.chat.completions.create(
        model=model,  # Use the specified model type
        messages=[
            {"role": "system", "content": task_describe},
            {"role": "user", "content": information + prompt + format}
        ],
        max_tokens=500,  # Set the maximum length of the generated result, adjustable as needed
    )
    tokens_used = response.usage.total_tokens  # Get the total token usage
    return response.choices[0].message.content, tokens_used


def extract_wrapped_content(text):
    match = re.search(r'\{\{(.*?)\}\}', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        return None


def process_task(task_id, prompt, model):
    total_tokens = 0
    while True:
        completion, tokens_used = GEN_ANSWER(prompt, model)
        total_tokens += tokens_used
        wrapped_content = extract_wrapped_content(completion)
        if wrapped_content:
            return dict(prompt_id=task_id, mutated_prompt=wrapped_content), total_tokens
        else:
            print(f"Task {task_id}: No wrapped content found. Retrying...")


def read_jsonl(file_path):
    with open(file_path, 'r') as file:
        return [json.loads(line) for line in file]  # Read all lines and parse them as JSON objects


def main(model, prompt_path, output_path):
    # Read the content of the jsonl file and randomly select one entry
    data = read_jsonl(prompt_path)
    random_entry = random.choice(data)

    if 'mutated_prompt' not in random_entry:
        print(f"No 'mutated_prompt' field found in the selected entry. Exiting...")
        return

    prompt = random_entry['mutated_prompt']  # Use the randomly selected 'mutated_prompt' field as the prompt

    samples = []
    total_tokens = 0
    problems = {i: {"prompt": prompt} for i in range(10)}  # Create 10 tasks

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_task, task_id, problem["prompt"], model) for task_id, problem in
                   problems.items()]

        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing tasks"):
            result, tokens_used = future.result()
            samples.append(result)
            total_tokens += tokens_used

    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir) and output_dir != '':
        os.makedirs(output_dir)

    write_jsonl(output_path, samples)
    print(f"Total tokens used: {total_tokens}")


if __name__ == "__main__":
    # Set command line arguments
    parser = argparse.ArgumentParser(description="Mutate prompts and save the results.")
    parser.add_argument('--model', type=str, required=True,
                        help="The model to use for prompt generation (e.g., 'gpt-3.5-turbo').")
    parser.add_argument('--prompt_path', type=str, required=True,
                        help="The file path for the prompt (.jsonl file) to be processed.")
    parser.add_argument('--output_path', type=str, required=True,
                        help="The file path where the output JSONL will be saved.")

    # Parse command line arguments
    args = parser.parse_args()

    # Run the main logic
    main(args.model, args.prompt_path, args.output_path)