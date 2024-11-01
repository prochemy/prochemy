import os
import re
import json
import random
import subprocess
import concurrent.futures
from tqdm import tqdm
from evalplus.data import write_jsonl
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Set API Key
client = OpenAI(
    base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

# Task description and information used for generating optimized prompts
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

# Generate task solution
def GEN_SOLUTION(task_describe, prompt):
    attempts = 0
    while attempts < 3:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": task_describe},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.0
        )
        # Use regex to match content starting with ```python and ending with ```
        match = re.search(r'```python(.*?)```', response.choices[0].message.content, re.DOTALL)
        if match:
            return match.group(1).strip()  # Return the matched Python code part and strip extra whitespace
        attempts += 1

    # If no result after 3 attempts, return an empty string
    print(f"Failed to extract valid Python code after 3 attempts for prompt: {prompt}")
    return ""

# Process task
def process_task(task_id, task_describe, prompt):
    completion = GEN_SOLUTION(task_describe, prompt)
    return dict(task_id=task_id, completion=completion)

# Read JSONL file
def read_jsonl(file_path):
    with open(file_path, 'r') as file:
        for line in file:
            yield json.loads(line)

# Generate solutions and save to the specified directory
def generate_solutions(test_set_path, mutated_prompt_path, output_directory):
    os.makedirs(output_directory, exist_ok=True)

    mutated_prompts = {task["prompt_id"]: task["mutated_prompt"] for task in read_jsonl(mutated_prompt_path)}

    for prompt_id, task_describe in mutated_prompts.items():
        samples = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    process_task,
                    task["task_id"],
                    task_describe,
                    task["prompt"]
                )
                for task in read_jsonl(test_set_path)
            ]

            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures),
                               desc=f"Processing tasks for prompt_id {prompt_id}"):
                result = future.result()
                if result['completion']:
                    samples.append(result)
                else:
                    print(f"No valid completion for task_id: {result['task_id']} with prompt_id: {prompt_id}")

        # Train set name
        output_file = os.path.join(output_directory, f"train_set_gpt3.5turbo_{prompt_id}.jsonl")
        write_jsonl(output_file, samples)

# Evaluate the generated solutions and select the best prompts
def evaluate_and_select_best_prompts(folder_path, problem_file_path, prompts_file_path, best_prompt_output_path):
    base_command = f"evaluate_functional_correctness {{jsonl_file}} --problem_file=/home/ysx/python-project/prompt_optimization_method/code_generation/partial_humaneval_testset.jsonl"

    # Used to store the correct result count for each task_id
    task_correct_counts = {}
    max_weighted_score = -1
    best_prompt_ids = []

    # Iterate over all jsonl files in the folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".jsonl") and not filename.endswith("_results.jsonl"):
            jsonl_file_path = os.path.join(folder_path, filename)
            result_file_path = jsonl_file_path + "_results.jsonl"

            # Check if results.jsonl file exists, if not, run the script to generate it
            if not os.path.exists(result_file_path):
                command = base_command.format(jsonl_file=jsonl_file_path)
                try:
                    print(f"Generating results for {filename}...")
                    subprocess.run(command, shell=True, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Command failed: {e}\n{e.output}")
                    continue  # Skip this file if generation fails

            # Read the generated results.jsonl file and calculate correct counts for each task_id
            if os.path.exists(result_file_path):
                with open(result_file_path, 'r') as result_file:
                    for line in result_file:
                        line = line.strip()  # Strip trailing whitespace
                        if not line:
                            print(f"Warning: Empty line encountered in {result_file_path}")
                            continue  # Skip empty lines

                        try:
                            result_data = json.loads(line)
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON in file {result_file_path}, line content: {line}")
                            continue  # Skip lines with JSON decoding errors

                        task_id = result_data.get('task_id')
                        if result_data.get('passed'):
                            task_correct_counts[task_id] = task_correct_counts.get(task_id, 0) + 1

    # Calculate weighted score for each task_id
    total_tasks = sum(task_correct_counts.values())
    task_weights = {task_id: total_tasks / count for task_id, count in task_correct_counts.items()}

    # Recalculate weighted score and original score for each file
    prompt_scores = {}

    for filename in os.listdir(folder_path):
        if filename.endswith(".jsonl") and not filename.endswith("_results.jsonl"):
            jsonl_file_path = os.path.join(folder_path, filename)
            result_file_path = jsonl_file_path + "_results.jsonl"

            weighted_score = 0
            total_count = 0
            passed_count = 0

            if os.path.exists(result_file_path):
                with open(result_file_path, 'r') as result_file:
                    for line in result_file:
                        line = line.strip()  # Strip trailing whitespace
                        if not line:
                            print(f"Warning: Empty line encountered in {result_file_path}")
                            continue  # Skip empty lines

                        try:
                            result_data = json.loads(line)
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON in file {result_file_path}, line content: {line}")
                            continue  # Skip lines with JSON decoding errors

                        task_id = result_data.get('task_id')
                        total_count += 1
                        if result_data.get('passed'):
                            passed_count += 1
                            weighted_score += task_weights.get(task_id, 0)

            original_score = passed_count / total_count if total_count > 0 else 0

            # Extract prompt_id from filename
            try:
                prompt_id = int(re.search(r'_(\d+)\.jsonl', filename).group(1))
            except (IndexError, ValueError, AttributeError):
                print(f"Error extracting prompt_id from filename: {filename}")
                continue  # Skip this file

            prompt_scores[prompt_id] = {'original_score': original_score, 'weighted_score': weighted_score}

            # Update highest weighted score and corresponding prompt_id list
            if weighted_score > max_weighted_score:
                max_weighted_score = weighted_score
                best_prompt_ids = [prompt_id]  # Reset the list
            elif weighted_score == max_weighted_score:
                best_prompt_ids.append(prompt_id)

    # Print the original and weighted scores for each prompt_id
    for prompt_id, scores in prompt_scores.items():
        print(
            f"Prompt ID: {prompt_id}, Original Score: {scores['original_score']}, Weighted Score: {scores['weighted_score']}")

    # Extract the corresponding prompt from the mutated_prompt file and save
    if best_prompt_ids:
        with open(prompts_file_path, 'r') as prompts_file:
            with open(best_prompt_output_path, 'w') as best_prompt_file:
                for line in prompts_file:
                    prompt_data = json.loads(line)
                    if prompt_data.get('prompt_id') in best_prompt_ids:
                        best_prompt_file.write(json.dumps(prompt_data) + '\n')

    print(
        f'Best prompts saved to {best_prompt_output_path} with prompt_ids: {best_prompt_ids} and max weighted score: {max_weighted_score}')

# Generate optimized prompts
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
        return ""

def process_optimization_task(task_id, prompt):
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
            futures.append(executor.submit(process_optimization_task, task_id, formatted_prompt))

        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing tasks"):
            new_prompts.append(future.result())

    return new_prompts

def optimize_prompts(input_file, output_file):
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

    new_prompts = [prompt for prompt in new_prompts if prompt['prompt_id'] <= 9]

    combined_prompts = prompts + new_prompts
    with open(output_file, 'w') as out_file:
        for prompt in combined_prompts:
            json.dump(prompt, out_file)
            out_file.write('\n')

    print(f"New prompts saved to {output_file}")

# Main program entry point
if __name__ == "__main__":

    # TODO: change the following parameters
    # Generate solutions
    test_set_path = "code_generation_training_set.jsonl"
    mutated_prompt_path = "/path/to/mutated_prompt"
    output_directory = "/output/path"
    generate_solutions(test_set_path, mutated_prompt_path, output_directory)

    # Evaluate solutions and select the best prompts
    folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "/output/path")
    # Train Set Path
    problem_file_path = os.path.join("/path/to/train/set",
                                     "/train/set/file")
    prompts_file_path = '/path/to/prompt/file'
    best_prompt_output_path = '/best/prompt/output/path'
    evaluate_and_select_best_prompts(folder_path, problem_file_path, prompts_file_path, best_prompt_output_path)

    # Generate optimized prompts
    optimize_input_file = best_prompt_output_path
    optimize_output_file = "/updated/prompt/output/path"
    optimize_prompts(optimize_input_file, optimize_output_file)