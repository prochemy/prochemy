import os
import subprocess
import shutil
import json
from threading import Timer
from tqdm import tqdm

def compile_and_run_java(java_file, testcases_dir, results):
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
        results.append({"file_id": os.path.basename(java_file), "compile_info": compile_info, "compile_success": False, "passed": False})
        return

    temp_dir = os.path.join('./temp', class_name)
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # Copy the java file to temp directory with the correct class name
    temp_java_file = os.path.join(temp_dir, f'{class_name}.java')
    shutil.copy(java_file, temp_java_file)

    compile_info = ""
    passed = True
    compile_success = False
    total_test_cases = 0
    passed_test_cases = 0

    try:
        # Compile the Java file
        # subprocess.run(['javac', temp_java_file], check=True)
        subprocess.run(['javac', '--release', '8', temp_java_file], check=True)
        compile_success = True
        compile_info += f"Compiled {java_file} successfully.\n"

        # Match test case files
        base_name = os.path.basename(java_file).replace('.java', '')
        test_cases = [(os.path.join(testcases_dir, file), os.path.join(testcases_dir, file.replace('.in', '.out')))
                      for file in os.listdir(testcases_dir)
                      if file.startswith(base_name) and file.endswith('.in')]

        if test_cases:
            for input_file, expected_output_file in test_cases:
                total_test_cases += 1
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
                    timer = Timer(1, proc.kill)

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
                            compile_info += f"Ran {class_name} with test case {input_file} successfully and passed the test case.\n"
                            passed_test_cases += 1
                        else:
                            compile_info += f"Ran {class_name} with test case {input_file} but failed the test case.\n"
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
    finally:
        # Clean up the temp directory
        shutil.rmtree(temp_dir)
        results.append({
            "file_id": os.path.basename(java_file),
            "compile_info": compile_info,
            "compile_success": compile_success,
            "passed": passed,
            "total_test_cases": total_test_cases,
            "passed_test_cases": passed_test_cases
        })
        # Print compile info
        print(compile_info)

def calculate_pass_percentage(file_name):
    total_files = 0
    passed_files = 0
    compile_success_files = 0
    total_test_cases = 0
    passed_test_cases = 0

    with open(file_name, 'r') as f:
        for line in f:
            total_files += 1
            result = json.loads(line)
            total_test_cases += result.get("total_test_cases", 0)
            passed_test_cases += result.get("passed_test_cases", 0)
            if result["passed"]:
                passed_files += 1
            if result["compile_success"]:
                compile_success_files += 1

    pass_percentage = (passed_files / total_files) * 100 if total_files > 0 else 0
    compile_success_percentage = (compile_success_files / total_files) * 100 if total_files > 0 else 0
    test_case_pass_percentage = (passed_test_cases / total_test_cases) * 100 if total_test_cases > 0 else 0
    return total_files, passed_files, pass_percentage, compile_success_files, compile_success_percentage, total_test_cases, passed_test_cases, test_case_pass_percentage


def main():
    # TODO: change the following parameters
    # path to the code
    code_dir = ''

    # path to the testcases
    testcases_dir = ''

    # Set the results directory and ensure it exists
    results_dir = ''

    if not os.path.exists(results_dir):
        os.makedirs(results_dir)

    # output file in jsonl
    file_name = os.path.join(results_dir, '/output/file/name.jsonl')

    if os.path.exists(file_name):
        print(f"Results file {file_name} already exists. Calculating pass percentage from existing file.")
        total_files, passed_files, pass_percentage, compile_success_files, compile_success_percentage, total_test_cases, passed_test_cases, test_case_pass_percentage = calculate_pass_percentage(
            file_name)
        print(f"Total files: {total_files}")
        print(f"Compile success files: {compile_success_files}")
        print(f"Compile success percentage: {compile_success_percentage:.2f}%")
        print(f"Passed files: {passed_files}")
        print(f"Pass percentage: {pass_percentage:.2f}%")
        print(f"Total test cases: {total_test_cases}")
        print(f"Passed test cases: {passed_test_cases}")
        print(f"Test case pass percentage: {test_case_pass_percentage:.2f}%")

    else:
        # Ensure the temporary directory exists
        if not os.path.exists('./temp'):
            os.makedirs('./temp')

        results = []

        # Get list of Java files
        java_files = [os.path.join(code_dir, file) for file in os.listdir(code_dir) if file.endswith('.java')]

        # Compile and run all Java files in the directory with progress bar
        for java_file in tqdm(java_files, desc="Processing Java files"):
            compile_and_run_java(java_file, testcases_dir, results)

        # Save results to a jsonl file
        with open(file_name, 'w') as f:
            for result in results:
                f.write(json.dumps(result) + "\n")

        # Calculate and print pass percentage
        total_files, passed_files, pass_percentage, compile_success_files, compile_success_percentage, total_test_cases, passed_test_cases, test_case_pass_percentage = calculate_pass_percentage(
            file_name)
        print(f"Total files: {total_files}")
        print(f"Compile success files: {compile_success_files}")
        print(f"Compile success percentage: {compile_success_percentage:.2f}%")
        print(f"Passed files: {passed_files}")
        print(f"Pass percentage: {pass_percentage:.2f}%")
        print(f"Total test cases: {total_test_cases}")
        print(f"Passed test cases: {passed_test_cases}")
        print(f"Test case pass percentage: {test_case_pass_percentage:.2f}%")

if __name__ == '__main__':
    main()