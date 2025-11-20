# 544
LiveCodeBench Testing Framework User Manual
Running Tests
Basic Command
python run_livecodebench_test.py --use-official --output-dir results --candidate-num 5 --test-case-num 10 --platform 0
Parameter Description
Dataset Options (Choose One)
--use-official: Use the official LiveCodeBench dataset
--dataset-path PATH: Use a custom dataset file path
Dataset Configuration
--release-version VERSION: Specify LiveCodeBench dataset version (default: "release_v1")
--platform {0,1,2,3}: Filter by platform (0: LeetCode, 1: CodeForces, 2: AtCoder, 3: All platforms, default: 3)
Test Configuration
--output-dir DIR: Output directory for test results (default: "livecodebench_results")
--candidate-num NUM: Number of candidate implementations to generate for each function (default: 5)
--test-case-num NUM: Number of test cases for each function (default: 10)
--selector-type {0,1}: Selector type (0: Basic selector, 1: Advanced selector, default: 0)
--cluster-num NUM: Number of clusters (default: 3)
Control Options
--problem-timeout SECONDS: Timeout in seconds for each problem (default: 600)
--no-resume: Do not resume from previous run, restart all tests
--skip-problems IDs: Comma-separated list of problem IDs to skip
--max-problems NUM: Maximum number of problems to test
--difficulty {easy,medium,hard}: Filter problems by difficulty
--evaluate-only: Only evaluate existing generated code without regenerating
--force-evaluation: Force re-evaluation of problems even if they were already processed
Output Structure
After testing is complete, the output directory will contain:

output_dir/
├── all_results.json         # Overview of all test results
├── problem_errors.json      # List of problem processing errors (if any)
└── problem_{id}/           # Subdirectory for each problem
    ├── problem.txt          # Problem description
    ├── final_result.py      # Generated code
    ├── analysis_text.txt    # Architecture analysis (if available)
    ├── execution_stdout.txt # Execution output log
    └── execution_stderr.txt # Execution error log (if any)
Result Interpretation
Test results are saved in the all_results.json file, containing the following information:

ID and title of each problem
Whether code generation was successful
Test evaluation results
If using an external evaluator: Contains the complete results returned by the evaluator
If using the built-in evaluator: Contains test execution status, output, and return code
The success rate is displayed in the console, calculated as: number of successful problems / total number of problems.

Checkpoint Recovery
The testing framework includes automatic checkpoint recovery functionality:

If a test run is interrupted (by Ctrl+C, system crash, or timeout), you can simply restart the command.
The framework will automatically detect previously processed problems by reading the all_results.json file.
Already completed problems will be skipped with a message: "Skipping problem [ID]: [Title] (already processed)".
This allows for efficient continuation of long test sessions without duplicating work.
To force reprocessing of all problems (ignoring previous results), use the --no-resume flag:

python run_livecodebench_test.py --use-official --output-dir results --no-resume
Example Commands
# Test LeetCode problems with 15-minute timeout per problem, skipping problem 2837
python run_livecodebench_test.py --use-official --output-dir leetcode_results --platform 0 --problem-timeout 900 --skip-problems 2837

# Test 5 of the hardest AtCoder problems
python run_livecodebench_test.py --use-official --output-dir atcoder_hard --platform 2 --difficulty hard --max-problems 5

# Only evaluate existing generated code without regenerating
python run_livecodebench_test.py --use-official --output-dir leetcode_results --platform 0 --evaluate-only

# Force re-evaluation of all problems even if they were already processed
python run_livecodebench_test.py --use-official --output-dir leetcode_results --platform 0 --evaluate-only --force-evaluation
