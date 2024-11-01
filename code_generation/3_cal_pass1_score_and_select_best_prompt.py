import os
import subprocess
import re
import json

# Absolute path of the current script file
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define folder path and base command
# TODO: change the following parameters
folder_path = os.path.join(script_dir, "/path/to/code/folder")
problem_file_path = os.path.join("/path/to/trainset", "/trainset/file/name")
base_command = "evaluate_functional_correctness {jsonl_file} --problem_file=" + problem_file_path

# Define directory path to save the best prompts
prompts_file_path = '/path/to/prompt/file'
best_prompt_output_path = '/output/path/of/best/prompt'

# Initialize the highest pass@1 value and the corresponding prompt_id list
max_pass_at_1 = -1
best_prompt_ids = []

# Iterate over all jsonl files in the folder
for filename in os.listdir(folder_path):
    if filename.endswith(".jsonl") and not filename.endswith("_results.jsonl"):
        jsonl_file_path = os.path.join(folder_path, filename)
        result_file_path = jsonl_file_path + "_results.jsonl"

        if os.path.exists(result_file_path):
            # Read the results file and calculate the pass@1 value
            total_count = 0
            passed_count = 0
            with open(result_file_path, 'r') as result_file:
                for line in result_file:
                    total_count += 1
                    result_data = json.loads(line)
                    if result_data.get('passed') == True:
                        passed_count += 1

            if total_count > 0:
                pass_at_1_value = passed_count / total_count
                print(f"File: {filename}, pass@1: {pass_at_1_value} (from results file)")
            else:
                print(f"File: {filename}, no valid results found in results file")
                pass_at_1_value = 0
        else:
            # Execute the command and capture the output
            command = base_command.format(jsonl_file=jsonl_file_path)
            try:
                result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
                output = result.stdout + result.stderr

                # Extract the pass@1 value
                match = re.search(r"'pass@1': ([\d\.]+)", output)
                if match:
                    pass_at_1_value = float(match.group(1))
                    print(f"File: {filename}, pass@1: {pass_at_1_value}")
                else:
                    print(f"File: {filename}, pass@1: Not found")
                    pass_at_1_value = 0
            except subprocess.CalledProcessError as e:
                print(f"Command failed: {e}\n{e.output}")
                pass_at_1_value = 0

        # Update the highest pass@1 value and the corresponding prompt_id list
        try:
            prompt_id = int(re.search(r'_(\d+)\.jsonl', filename).group(1))
        except (IndexError, ValueError, AttributeError):
            print(f"Error extracting prompt_id from filename: {filename}")
            continue  # Skip this file

        if pass_at_1_value > max_pass_at_1:
            max_pass_at_1 = pass_at_1_value
            best_prompt_ids = [prompt_id]  # Reset the list, keeping only the prompt_id with the highest value
        elif pass_at_1_value == max_pass_at_1:
            best_prompt_ids.append(prompt_id)  # Add prompt_id with the same highest value

# Extract the corresponding prompt from the mutated_prompt file and save it
if best_prompt_ids:
    with open(prompts_file_path, 'r') as prompts_file:
        with open(best_prompt_output_path, 'w') as best_prompt_file:
            for line in prompts_file:
                prompt_data = json.loads(line)
                if prompt_data.get('prompt_id') in best_prompt_ids:
                    best_prompt_file.write(json.dumps(prompt_data) + '\n')

print(f'Best prompts saved to {best_prompt_output_path} with prompt_ids: {best_prompt_ids}')