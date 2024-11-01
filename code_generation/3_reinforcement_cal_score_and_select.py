import os
import subprocess
import re
import json
import argparse

# Define a function to evaluate functional correctness
def evaluate_functional_correctness(evaluate_path, problem_file_path, prompts_file_path, best_prompt_output_path):
    # Used to store the correct result count for each task_id
    task_correct_counts = {}

    # Initialize the highest weighted score and the corresponding prompt_id list
    max_weighted_score = -1
    best_prompt_ids = []

    # Iterate over all jsonl files in the folder
    for filename in os.listdir(evaluate_path):
        if filename.endswith(".jsonl") and not filename.endswith("_results.jsonl"):
            jsonl_file_path = os.path.join(evaluate_path, filename)
            result_file_path = jsonl_file_path + "_results.jsonl"

            # Check if results.jsonl file exists, if not, run the script to generate it
            if not os.path.exists(result_file_path):
                base_command = f"evaluate_functional_correctness {jsonl_file_path} --problem_file={problem_file_path}"
                try:
                    print(f"Generating results for {filename}...")
                    subprocess.run(base_command, shell=True, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Command failed: {e}\n{e.output}")
                    continue  # Skip this file if generation fails

            # Read the generated results.jsonl file and calculate correct counts for each task_id
            if os.path.exists(result_file_path):
                with open(result_file_path, 'r') as result_file:
                    for line in result_file:
                        line = line.strip()  # Remove trailing whitespace
                        if not line:
                            print(f"Warning: Empty line encountered in {result_file_path}")
                            continue  # Skip empty lines

                        try:
                            result_data = json.loads(line)
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON in file {result_file_path}, line content: {line}")
                            continue  # Skip lines with parsing errors

                        task_id = result_data.get('task_id')
                        if result_data.get('passed'):
                            task_correct_counts[task_id] = task_correct_counts.get(task_id, 0) + 1

    # Calculate the weighted score for each task_id
    total_tasks = sum(task_correct_counts.values())
    task_weights = {task_id: total_tasks / count for task_id, count in task_correct_counts.items()}

    # Recalculate the weighted and original score for each file
    prompt_scores = {}

    for filename in os.listdir(evaluate_path):
        if filename.endswith(".jsonl") and not filename.endswith("_results.jsonl"):
            jsonl_file_path = os.path.join(evaluate_path, filename)
            result_file_path = jsonl_file_path + "_results.jsonl"

            weighted_score = 0
            total_count = 0
            passed_count = 0

            if os.path.exists(result_file_path):
                with open(result_file_path, 'r') as result_file:
                    for line in result_file:
                        line = line.strip()  # Remove trailing whitespace
                        if not line:
                            print(f"Warning: Empty line encountered in {result_file_path}")
                            continue  # Skip empty lines

                        try:
                            result_data = json.loads(line)
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON in file {result_file_path}, line content: {line}")
                            continue  # Skip lines with parsing errors

                        task_id = result_data.get('task_id')
                        total_count += 1
                        if result_data.get('passed'):
                            passed_count += 1
                            weighted_score += task_weights.get(task_id, 0)

            original_score = passed_count / total_count if total_count > 0 else 0

            # Extract prompt_id from the filename
            try:
                prompt_id = int(re.search(r'_(\d+)\.jsonl', filename).group(1))
            except (IndexError, ValueError, AttributeError):
                print(f"Error extracting prompt_id from filename: {filename}")
                continue  # Skip this file

            prompt_scores[prompt_id] = {'original_score': original_score, 'weighted_score': weighted_score}

            # Update the highest weighted score and the corresponding prompt_id list
            if weighted_score > max_weighted_score:
                max_weighted_score = weighted_score
                best_prompt_ids = [prompt_id]  # Reset the list
            elif weighted_score == max_weighted_score:
                best_prompt_ids.append(prompt_id)

    # Print the original and weighted scores for each prompt_id
    for prompt_id, scores in prompt_scores.items():
        print(f"Prompt ID: {prompt_id}, Original Score: {scores['original_score']}, Weighted Score: {scores['weighted_score']}")

    # Extract the corresponding prompt from the mutated_prompt file and save it
    if best_prompt_ids:
        with open(prompts_file_path, 'r') as prompts_file:
            with open(best_prompt_output_path, 'w') as best_prompt_file:
                for line in prompts_file:
                    prompt_data = json.loads(line)
                    if prompt_data.get('prompt_id') in best_prompt_ids:
                        best_prompt_file.write(json.dumps(prompt_data) + '\n')

    print(f'Best prompts saved to {best_prompt_output_path} with prompt_ids: {best_prompt_ids} and max weighted score: {max_weighted_score}')


if __name__ == "__main__":
    # Set command-line argument parsing
    parser = argparse.ArgumentParser(description="Evaluate functional correctness and select the best prompts.")
    parser.add_argument('--evaluate_path', type=str, required=True, help="Folder path to evaluate JSONL files.")
    parser.add_argument('--testset_path', type=str, required=True, help="Path to the problem test set JSONL file.")
    parser.add_argument('--origin_prompt', type=str, required=True, help="Path to the mutated prompt JSONL file.")
    parser.add_argument('--best_prompt', type=str, required=True, help="Path to save the best prompt JSONL file.")

    # Parse command-line arguments
    args = parser.parse_args()

    # Call the main function to evaluate
    evaluate_functional_correctness(args.evaluate_path, args.testset_path, args.origin_prompt, args.best_prompt)