import os
import subprocess
import json
from threading import Timer
from tqdm import tqdm
import concurrent.futures

def run_python_script(python_file, testcases_dir):
    """Runs a Python file with its test cases."""
    base_name = os.path.basename(python_file).replace('.py', '')
    test_cases = []

    # Collect all matching test case files
    for root, _, files in os.walk(testcases_dir):
        for file in files:
            if file.startswith(base_name) and file.endswith('.in'):
                test_cases.append(file)

    compile_info = ""
    passed = True
    compile_success = True
    total_test_cases = len(test_cases)
    passed_test_cases = 0

    if not test_cases:
        compile_info += f"No test cases found for {python_file}. Skipping test case validation.\n"
        return {
            "file_id": os.path.basename(python_file),
            "compile_info": compile_info,
            "passed": False,
            "compile_success": False,
            "total_test_cases": total_test_cases,
            "passed_test_cases": passed_test_cases
        }

    for test_case in test_cases:
        input_file = os.path.join(testcases_dir, test_case)
        output_file = input_file.replace('.in', '.out')

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

                    if program_output_lines == expected_output_lines:
                        compile_info += f"Ran {python_file} with test case {input_file} successfully and passed the test case.\n"
                        passed_test_cases += 1
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

    return {
        "file_id": os.path.basename(python_file),
        "compile_info": compile_info,
        "passed": passed,
        "compile_success": compile_success,
        "total_test_cases": total_test_cases,
        "passed_test_cases": passed_test_cases
    }

def calculate_pass_percentage(file_name):
    """Calculate the pass percentage from the results file."""
    with open(file_name, 'r') as f:
        results = [json.loads(line) for line in f]

    total_files = len(results)
    passed_files = sum(result['passed'] for result in results)
    compiled_files = sum(result['compile_success'] for result in results)
    total_test_cases = sum(result['total_test_cases'] for result in results)
    passed_test_cases = sum(result['passed_test_cases'] for result in results)

    file_pass_percentage = (passed_files / total_files) * 100 if total_files > 0 else 0
    compile_percentage = (compiled_files / total_files) * 100 if total_files > 0 else 0
    test_case_pass_percentage = (passed_test_cases / total_test_cases) * 100 if total_test_cases > 0 else 0

    print(f"Total files: {total_files}")
    print(f"Compiled files: {compiled_files}")
    print(f"Compile success percentage: {compile_percentage:.2f}%")
    print(f"Passed files: {passed_files}")
    print(f"File pass percentage: {file_pass_percentage:.2f}%")
    print(f"Total test cases: {total_test_cases}")
    print(f"Passed test cases: {passed_test_cases}")
    print(f"Test case pass percentage: {test_case_pass_percentage:.2f}%")

    return total_files, passed_files, file_pass_percentage, compile_percentage, total_test_cases, passed_test_cases, test_case_pass_percentage

def main():
    # TODO: change the following parameters
    # path to the code
    code_dir = ''

    # path to the testcases
    testcases_dir = ''

    # output path
    results_dir = ''

    # Ensure the results directory exists
    os.makedirs(results_dir, exist_ok=True)

    # output file in jsonl
    file_name = os.path.join(results_dir, '/output/file/name.jsonl')

    results = []

    if os.path.exists(file_name):
        print(f"Results file {file_name} already exists. Calculating pass percentage from existing file.")
        calculate_pass_percentage(file_name)
        return

    # Get list of Python files
    python_files = [os.path.join(code_dir, file) for file in os.listdir(code_dir) if file.endswith('.py')]

    if not python_files:
        print(f"No Python files found in {code_dir}")
        return

    print(f"Found {len(python_files)} Python files in {code_dir}")

    # Run all Python files in the directory with progress bar using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(run_python_script, python_file, testcases_dir): python_file for python_file in python_files}

        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Processing Python files"):
            results.append(future.result())

    # Save results to a jsonl file
    with open(file_name, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + "\n")

    print("Finished processing all files.")
    calculate_pass_percentage(file_name)

if __name__ == '__main__':
    main()