import os
import subprocess
import json
from threading import Timer
from tqdm import tqdm
import concurrent.futures
import re

def run_python_script(python_file, testcases_dir):
    """Runs a Python file with its test cases."""
    base_name = os.path.basename(python_file).replace('.py', '')
    test_cases = []

    # Collect all matching test case files
    for root, _, files in os.walk(testcases_dir):
        for file in files:
            if file.startswith(base_name) and file.endswith('_in.txt'):
                test_cases.append(file)

    compile_info = ""
    passed = True
    compile_success = True

    if not test_cases:
        compile_info += f"No test cases found for {python_file}. Skipping test case validation.\n"
        return {"file_id": os.path.basename(python_file), "compile_info": compile_info, "passed": False, "compile_success": False}

    task_correct_counts = {}

    for test_case in test_cases:
        input_file = os.path.join(testcases_dir, test_case)
        output_file = input_file.replace('_in.txt', '_out.txt')

        if not os.path.exists(output_file):
            compile_info += f"Expected output file {output_file} not found. Skipping this test case.\n"
            passed = False
            continue

        with open(output_file, 'r') as file:
            expected_output_lines = file.read().strip().split('\n')

        try:
            with open(input_file, 'r') as file:
                proc = subprocess.Popen(
                    ['python', python_file],
                    stdin=file,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                timer = Timer(10, proc.kill)

                try:
                    timer.start()
                    stdout, stderr = proc.communicate()
                    timer.cancel()  # Cancel the timer if the process completes before timeout
                    if stdout:
                        compile_info += stdout.decode() + "\n"
                    if stderr:
                        compile_info += stderr.decode() + "\n"

                    # Compare the program output with the expected output
                    program_output_lines = stdout.decode().strip().split('\n')

                    task_id = test_case.replace('_in.txt', '')
                    if program_output_lines == expected_output_lines:
                        task_correct_counts[task_id] = task_correct_counts.get(task_id, 0) + 1
                        compile_info += f"Ran {python_file} with test case {input_file} successfully and passed the test case.\n"
                    else:
                        compile_info += f"Ran {python_file} with test case {input_file} but failed the test case.\n"
                        compile_info += f"Expected output:\n{expected_output_lines}\n"
                        compile_info += f"Program output:\n{program_output_lines}\n"
                        passed = False
                finally:
                    if timer.is_alive():
                        timer.cancel()
        except subprocess.CalledProcessError as e:
            compile_info += f"Failed to run {python_file} with test case {input_file}. Error: {e}\n"
            passed = False
            compile_success = False

    total_tasks = sum(task_correct_counts.values())
    task_weights = {task_id: total_tasks / count for task_id, count in task_correct_counts.items()}
    weighted_score = sum(task_weights.get(task_id, 0) for task_id in task_correct_counts)

    return {
        "file_id": os.path.basename(python_file),
        "compile_info": compile_info,
        "passed": passed,
        "compile_success": compile_success,
        "weighted_score": weighted_score
    }

def calculate_pass_percentage(file_name):
    """Calculate the pass percentage and weighted scores from the results file."""
    with open(file_name, 'r') as f:
        results = [json.loads(line) for line in f]

    total = len(results)
    passed = sum(result['passed'] for result in results)
    compiled = sum(result['compile_success'] for result in results)
    total_weighted_score = sum(result.get('weighted_score', 0) for result in results)

    pass_percentage = (passed / total) * 100 if total > 0 else 0
    compile_percentage = (compiled / total) * 100 if total > 0 else 0

    return total, passed, pass_percentage, compile_percentage, total_weighted_score

def process_files_in_directory(code_dir, testcases_dir, results_file):
    results = []

    # Get list of Python files
    python_files = [os.path.join(code_dir, file) for file in os.listdir(code_dir) if file.endswith('.py')]

    if not python_files:
        print(f"No Python files found in {code_dir}")
        return

    print(f"Found {len(python_files)} Python files in {code_dir}")

    # Run all Python files in the directory with progress bar using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(run_python_script, python_file, testcases_dir): python_file for python_file in python_files}

        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc=f"Processing {os.path.basename(code_dir)}"):
            results.append(future.result())

    # Save results to a jsonl file in the respective subdirectory
    with open(results_file, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + "\n")

    print(f"Finished processing all files in {code_dir}.")
    total, passed, pass_percentage, compile_percentage, total_weighted_score = calculate_pass_percentage(results_file)
    print(f"Results for {code_dir} - Pass percentage: {pass_percentage:.2f}%, Weighted Score: {total_weighted_score}")

    return pass_percentage, total_weighted_score, code_dir

def extract_best_prompts(best_prompt_ids, source_file, output_file):
    best_prompts = []

    with open(source_file, 'r') as f:
        for line in f:
            data = json.loads(line)
            if str(data['prompt_id']) in best_prompt_ids:
                best_prompts.append(data)

    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Save best prompts to the output file
    with open(output_file, 'w') as f:
        for prompt in best_prompts:
            f.write(json.dumps(prompt) + "\n")

def main():
    # TODO: change the following parameters
    # Root directory containing the Python files to evaluate
    base_dir = ''

    # Directory containing the test cases
    testcases_dir = ''

    # Source prompt file
    source_prompt_file = ''

    # Output file for the best prompts
    output_best_prompt_file = ''

    best_pass_percentage = 0
    best_weighted_score = 0
    best_prompt_ids = []

    for subdir in os.listdir(base_dir):
        code_dir = os.path.join(base_dir, subdir)
        if os.path.isdir(code_dir):
            results_file = os.path.join(code_dir, f'run_python_results_{subdir}.jsonl')
            if os.path.exists(results_file):
                print(f"Results file {results_file} already exists. Calculating pass percentage and weighted score from existing file.")
                _, _, pass_percentage, _, weighted_score = calculate_pass_percentage(results_file)
            else:
                pass_percentage, weighted_score, _ = process_files_in_directory(code_dir, testcases_dir, results_file)

            if weighted_score > best_weighted_score:
                best_weighted_score = weighted_score
                best_prompt_ids = [subdir]
            elif weighted_score == best_weighted_score:
                best_prompt_ids.append(subdir)

    print(f"\nBest prompt_id(s) with weighted score: {best_weighted_score:.2f}")
    for prompt_id in best_prompt_ids:
        print(prompt_id)

    extract_best_prompts(best_prompt_ids, source_prompt_file, output_best_prompt_file)

if __name__ == '__main__':
    main()
