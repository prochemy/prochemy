import json

def merge_jsonl_files(file1_path, file2_path, output_path):
    # Read the first file
    with open(file1_path, 'r', encoding='utf-8') as file1:
        data1 = [json.loads(line) for line in file1]

    # Read the second file
    with open(file2_path, 'r', encoding='utf-8') as file2:
        data2 = [json.loads(line) for line in file2]

    # Convert the data from the first file to a dictionary for easy lookup
    data1_dict = {item['task_id']: item for item in data1}

    # Process the data from the second file
    merged_data = []
    count = 0
    for item in data2:
        task_id = item['task_id']
        if 'completion' in item and item['completion'] == "":
            if task_id in data1_dict:
                print(f"Found matching task_id: {task_id} with completion from file1: {data1_dict[task_id]['completion']}")
                item['completion'] = data1_dict[task_id]['completion']
                count += 1
            else:
                print(f"No matching task_id: {task_id} found in file1")
        merged_data.append(item)

    # Write the merged data to the output file
    with open(output_path, 'w', encoding='utf-8') as output_file:
        for item in merged_data:
            output_file.write(json.dumps(item, ensure_ascii=False) + '\n')
            print(f"Writing task_id: {item['task_id']} with completion: {item['completion']} to output file")

    # Print the total number of added data entries
    print(f"Total added completions: {count}")

# TODO: change the following parameters
dataset = ""
model = ""
type = ""

# File paths
# file1_path = dataset + "_samples_prompt_"+ model + "_" + type + "-sanitized.jsonl"
# file2_path = dataset + "_samples_prompt_"+ model + "_" + type + "-sanitized-mod.jsonl"
# output_path = dataset + "_merged_samples_"+ model + "_"+ type + ".jsonl"

file1_path = dataset + "_" + model + "_" + type + "-sanitized.jsonl"
file2_path = dataset + "_" + model + "_" + type + "-sanitized-mod.jsonl"
output_path = dataset + "_merged"+ "_" + model + "_"+ type + ".jsonl"

# Call the merge function
merge_jsonl_files(file1_path, file2_path, output_path)