import os
import json
import glob
import argparse

def clean_output(output: str) -> str:
    """
    Clean expected output by removing extraneous text and formatting.
    
    Args:
        output: Raw expected output string
        
    Returns:
        Cleaned expected output string
    """
    # If the expected output contains newlines, only take the first part
    if "\n" in output:
        output = output.split("\n")[0].strip()
    
    # If it looks like an array, make sure we only keep the array part
    if output.startswith("[") and "]" in output:
        output = output[:output.find("]")+1]
    
    # Remove quotes
    output = output.replace('"', '')
    
    return output.strip()

def fix_structured_test_cases(problem_file: str) -> bool:
    """
    Fix structured test cases in a problem file by cleaning expected outputs
    
    Args:
        problem_file: Path to the problem file
        
    Returns:
        True if file was fixed, False otherwise
    """
    try:
        with open(problem_file, 'r', encoding='utf-8') as f:
            problem_data = json.load(f)
        
        if 'structured_test_cases' not in problem_data:
            return False
        
        modified = False
        for test_case in problem_data['structured_test_cases']:
            if 'expected' in test_case:
                original = test_case['expected']
                cleaned = clean_output(original)
                
                if original != cleaned:
                    test_case['expected'] = cleaned
                    modified = True
                    print(f"Fixed: {original} -> {cleaned}")
        
        if modified:
            # Save the fixed problem
            with open(problem_file, 'w', encoding='utf-8') as f:
                json.dump(problem_data, f, ensure_ascii=False, indent=2)
            print(f"Fixed and saved: {os.path.basename(problem_file)}")
            return True
        
        return False
    except Exception as e:
        print(f"Error processing {problem_file}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Fix LeetCode dataset files")
    parser.add_argument("--dataset", type=str, default="leetcode_dataset",
                       help="Path to the dataset directory")
    
    args = parser.parse_args()
    
    dataset_dir = args.dataset
    if not os.path.exists(dataset_dir):
        print(f"Dataset directory not found: {dataset_dir}")
        return
    
    # Get all JSON files
    json_files = glob.glob(os.path.join(dataset_dir, "*.json"))
    if not json_files:
        print(f"No JSON files found in {dataset_dir}")
        return
    
    fixed_count = 0
    for file_path in json_files:
        if fix_structured_test_cases(file_path):
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} out of {len(json_files)} files")

if __name__ == "__main__":
    main()
