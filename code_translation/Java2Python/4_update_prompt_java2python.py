import os
import json
import re
import random
import subprocess
from tqdm import tqdm
import concurrent.futures
from evalplus.data import write_jsonl
from openai import OpenAI
import httpx
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
I need to translate Java code into Python code while maintaining the same functionality.
Maintaining the same functionality means that the translated Python code should pass all the test cases that the original Java code could pass.
I have a prompt written for this task. Based on the previous description, revise and optimize this prompt so that it can better guide the model to complete the code translation task effectively.
"""

format = """
You may add any information you think will help improve the task's effectiveness during the prompt optimization process.
If you find certain expressions and wording in the original prompt inappropriate, you can also modify these usages.
Ensure that the optimized prompt includes a detailed task description and clear process guidance added to the original prompt.
Wrap the optimized prompt in {{}}.
"""


def GEN_ANSWER(prompt):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": task_describe},
            {"role": "user", "content": information + prompt + format}
        ],
        max_tokens=500,
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


def generate_new_prompts(existing_prompts):
    new_prompts = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for task_id in range(10):
            random_prompt = random.choice(existing_prompts)
            prompt_text = random_prompt['mutated_prompt']
            formatted_prompt = f"The prompt ready to be optimized are as follows and wrapped in []:\n[{prompt_text}]\n"
            futures.append(executor.submit(process_task, task_id, formatted_prompt))

        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing tasks"):
            new_prompts.append(future.result())

    return new_prompts


def main():
    # TODO: change the following parameters
    # The best_prompt file from the previous round
    input_file = ""

    # The updated prompt file
    output_file = ""

    if not os.path.exists(input_file):
        print(f"Input file {input_file} does not exist.")
        return

    with open(input_file, 'r') as file:
        prompts = [json.loads(line) for line in file]

    new_prompts = generate_new_prompts(prompts)

    existing_ids = {prompt['prompt_id'] for prompt in prompts}
    new_id = 0
    for new_prompt in new_prompts:
        while new_id in existing_ids:
            new_id += 1
        new_prompt['prompt_id'] = new_id
        existing_ids.add(new_id)

    # Ensure prompt_id does not exceed 9
    new_prompts = [prompt for prompt in new_prompts if prompt['prompt_id'] <= 9]

    # Keep the original data from prompts and add newly generated data
    combined_prompts = prompts + new_prompts
    with open(output_file, 'w') as out_file:
        for prompt in combined_prompts:
            json.dump(prompt, out_file)
            out_file.write('\n')

    print(f"New prompts saved to {output_file}")


if __name__ == "__main__":
    main()