import os
import subprocess
import shutil
import json
from threading import Timer
from tqdm import tqdm
import re

def compile_and_run_java(java_file, testcases_dir, results, task_correct_counts):
    """Compiles and runs a Java file with its test cases."""
    with open(java_file, 'r') as file:
        lines = file.readlines()

    class_name = None
    for line in lines:
        if line.strip().startswith('public class'):
            class_name = line.split()[2]
            break

    if not class_name:
        compile_info = f"No public class found in {java_file}. Skipping."
        print(compile_info)
        results.append({"file_id": os.path.basename(java_file), "compile_info": compile_info, "passed": False, "compile_success": False})
        return

    temp_dir = os.path.join('./temp', class_name)
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # Copy the java file to temp directory with the correct class name
    temp_java_file = os.path.join(temp_dir, f'{class_name}.java')
    shutil.copy(java_file, temp_java_file)

    compile_info = ""
    passed = True
    compile_success = True

    try:
        # Compile the Java file
        subprocess.run(['javac', '--release', '8', temp_java_file], check=True)
        compile_info += f"Compiled {java_file} successfully.\n"

        # Match test case files
        base_name = os.path.basename(java_file).replace('.java', '')
        input_file = os.path.join(testcases_dir, f'{base_name}_in.txt')
        expected_output_file = os.path.join(testcases_dir, f'{base_name}_out.txt')

        if os.path.exists(input_file) and os.path.exists(expected_output_file):
            # Read the expected output
            with open(expected_output_file, 'r') as file:
                expected_output_lines = file.read().strip().split('\n')

            # Run the compiled Java class with the input file
            with open(input_file, 'r') as file:
                proc = subprocess.Popen(
                    ['java', '-cp', temp_dir, class_name],
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

                    task_id = base_name  # Use base name as task identifier
                    if program_output_lines == expected_output_lines:
                        task_correct_counts[task_id] = task_correct_counts.get(task_id, 0) + 1
                        compile_info += f"Ran {class_name} successfully and passed the test cases.\n"
                    else:
                        compile_info += f"Ran {class_name} but failed the test cases.\n"
                        compile_info += f"Expected output:\n{expected_output_lines}\n"
                        compile_info += f"Program output:\n{program_output_lines}\n"
                        passed = False
                finally:
                    if timer.is_alive():
                        timer.cancel()
        else:
            compile_info += f"Test case files for {java_file} not found. Skipping test case validation.\n"
            passed = False
    except subprocess.CalledProcessError as e:
        compile_info += f"Failed to compile or run {java_file}. Error: {e}\n"
        passed = False
        compile_success = False
    finally:
        # Clean up the temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        results.append({
            "file_id": os.path.basename(java_file), 
            "compile_info": compile_info, 
            "passed": passed, 
            "compile_success": compile_success
        })
        print(compile_info)

def calculate_pass_percentage(file_name, task_weights):
    """Calculate the pass percentage and weighted scores from the results file."""
    with open(file_name, 'r') as f:
        results = [json.loads(line) for line in f]

    total = len(results)
    passed = sum(result['passed'] for result in results)
    compiled = sum(result['compile_success'] for result in results)
    total_weighted_score = sum(task_weights.get(result['file_id'].replace('.java', ''), 0) for result in results if result['passed'])

    pass_percentage = (passed / total) * 100 if total > 0 else 0
    compile_percentage = (compiled / total) * 100 if total > 0 else 0

    return total, passed, pass_percentage, compile_percentage, total_weighted_score

def process_files_in_directory(code_dir, testcases_dir, results_file):
    results = []
    task_correct_counts = {}

    # Get list of Java files
    java_files = [os.path.join(code_dir, file) for file in os.listdir(code_dir) if file.endswith('.java')]

    if not java_files:
        print(f"No Java files found in {code_dir}")
        return

    print(f"Found {len(java_files)} Java files in {code_dir}")

    # Compile and run all Java files in the directory with progress bar
    for java_file in tqdm(java_files, desc=f"Processing {os.path.basename(code_dir)}"):
        compile_and_run_java(java_file, testcases_dir, results, task_correct_counts)

    # Calculate task weights
    total_tasks = sum(task_correct_counts.values())
    task_weights = {task_id: total_tasks / count for task_id, count in task_correct_counts.items()}

    # Save results to a jsonl file in the respective subdirectory
    with open(results_file, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + "\n")

    print(f"Finished processing all files in {code_dir}.")
    total, passed, pass_percentage, compile_percentage, total_weighted_score = calculate_pass_percentage(results_file, task_weights)
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
    # Root directory containing the Java files to evaluate
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
            results_file = os.path.join(code_dir, f'run_java_results_{subdir}.jsonl')
            if os.path.exists(results_file):
                print(f"Results file {results_file} already exists. Calculating pass percentage and weighted score from existing file.")
                _, _, pass_percentage, _, weighted_score = calculate_pass_percentage(results_file, {})
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
