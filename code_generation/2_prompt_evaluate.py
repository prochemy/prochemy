import json
import os
import re
import concurrent.futures
from tqdm import tqdm
from evalplus.data import write_jsonl
from openai import OpenAI
import argparse
from dotenv import load_dotenv

load_dotenv()

# Set API Key
client = OpenAI(
    base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
    api_key=os.getenv("OPENAI_API_KEY"),
)


def GEN_SOLUTION(task_describe, prompt, model, client):
    attempts = 0
    total_tokens_used = 0  # Initialize token counter

    while attempts < 5:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": task_describe},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.0
        )

        # Add token usage for this request
        total_tokens_used += response.usage.total_tokens

        # Use regular expression to match content starting with ```python and ending with ```
        match = re.search(r'```python(.*?)```', response.choices[0].message.content, re.DOTALL)
        if match:
            return match.group(1).strip(), total_tokens_used  # Return Python code and token usage
        attempts += 1

    # If no result after 5 attempts, return an empty string and total token count
    print(f"Failed to extract valid Python code after 5 attempts for prompt: {prompt}")
    return "", total_tokens_used


def process_task(task_id, task_describe, prompt, model, client):
    completion, tokens_used = GEN_SOLUTION(task_describe, prompt, model, client)
    return dict(task_id=task_id, completion=completion), tokens_used


def read_jsonl(file_path):
    with open(file_path, 'r') as file:
        for line in file:
            yield json.loads(line)


def main(model, testset_path, mutated_prompt_path, output_path):
    os.makedirs(output_path, exist_ok=True)

    # Read mutated prompt file
    mutated_prompts = {task["prompt_id"]: task["mutated_prompt"] for task in read_jsonl(mutated_prompt_path)}

    total_tokens = 0  # Initialize total tokens counter

    for prompt_id, task_describe in mutated_prompts.items():
        samples = []

        # Use multithreading to speed up task processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    process_task,
                    task["task_id"],
                    task_describe,
                    task["prompt"],
                    model,
                    client
                )
                for task in read_jsonl(testset_path)
            ]

            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures),
                               desc=f"Processing tasks for prompt_id {prompt_id}"):
                result, tokens_used = future.result()
                total_tokens += tokens_used  # Accumulate total tokens
                if result['completion']:
                    samples.append(result)
                else:
                    print(f"No valid completion for task_id: {result['task_id']} with prompt_id: {prompt_id}")

        output_file = os.path.join(output_path, f"train_set_{model}_{prompt_id}.jsonl")
        write_jsonl(output_file, samples)

    print(f"Total tokens used: {total_tokens}")


if __name__ == "__main__":
    # Set command-line arguments
    parser = argparse.ArgumentParser(description="Run prompt evaluation using OpenAI API.")
    parser.add_argument('--model', type=str, required=True, help="The model to use (e.g., 'gpt-3.5-turbo').")
    parser.add_argument('--trainset_path', type=str, required=True, help="Path to the train set JSONL file.")
    parser.add_argument('--mutated_prompt_path', type=str, required=True, help="Path to the mutated prompt JSONL file.")
    parser.add_argument('--output_path', type=str, required=True, help="Directory to save the output files.")

    # Parse command-line arguments
    args = parser.parse_args()

    main(args.model, args.trainset_path, args.mutated_prompt_path, args.output_path)