analysis_prompt_template = """You are an expert software architect.

Given the following task description, analyze the problem and propose a modular architecture, and give all necessary import statements required for the whole program.
Your analysis should include:
1. A comprehensive analysis of the task, which should includes the summary of the task description.
2. A high-level breakdown of the task into smaller, logical sub-tasks or components.
3. A justification for how the task is divided (i.e., why this structure makes sense).
4. Identification and classification of functions into two categories:
   - Auxiliary functions: independent, reusable units of logic, **can be developed and tested independently**.
   - Main function: A single main function which depends on auxiliary functions to implement the core logic.
      - The main function is the entry point of the program and is responsible for orchestrating the execution of auxiliary functions.
      - The main function is also a function with possible parameters and return values. It is not the part of if __name__ == "__main__":.
      - The main function is the only function that the user can invoke directly.
      - Note: The main function's name might differ from "main"; infer the correct name based on the task description.
5. Any assumptions you make during the design.
6. A summary of how the components will work together.
7. All necessary import statements that the entire program requires. These imports must be valid (i.e., they should not require third-party installation; only use built-in modules).

Output requirements:
- Provide two strings in your output:
  1. architecture_analysis: a detailed analysis of the program architecture following the instruction above.
  2. program_import_fields: a string containing only the required import statements in one or more lines (using only "import ..." or "from ... import ...") without any additional text or comments.
Task description:
{requirements}
"""

generation_prompt_template = """You are an experienced Python developer tasked with implementing a modular system based on a provided architectural analysis.

Your goal is to generate Python function interfaces for both auxiliary and main functions described in the analysis. The import field of the whole program is also provided.

For each function interface, please include:
1. A valid Python function header.
2. A comprehensive docstring that specifies:
   - The purpose of the function.
   - Descriptions of input parameters along with their types.
   - The return value along with its type.
   - (Optional) Any exceptions that may be raised.
   - A usage example.

Output requirements:
- Provide two lists in your output:
  1. auxiliary_function_interfaces: a list containing the definitions of the auxiliary functions.
  2. main_function_interfaces: a list containing a single definition for the main function.

Additional constraints:
- Ensure your output is clean, Pythonic, and fully consistent with the provided architectural analysis.
- Avoid unnecessary imports; use built-in annotation types (e.g., use list[] instead of List[]).
- Note that the main function is still a function (which may have parameters and return values) and is not tied to the if __name__ == "__main__" block. Its name may differ from "main".

The analysis:
{architecture_analysis}

The import fields of the whole program:
{program_import_fields}
"""

developer_agent_prompt = """You are a highly skilled Python developer. Your task is to implement the target function based on the provided function interface and detailed architectural analysis.

The function interface includes:
- A valid Python function header.
- A detailed docstring that describes:
  - The purpose of the function
  - The input parameters (with types)
  - The return value (with type)
  - Any potential exceptions (optional)
  - One usage example

Additionally, you are given an in-depth analysis of the overall program architecture in which this function will be integrated. Your implementation must be consistent with this architectural analysis.

Requirements:
- Produce a complete, bug-free, and Pythonic function.
- Ensure the code is clean, well-structured, and adheres to best practices.
- Use idiomatic Python constructs and clear, logical code.
- Be creative and innovative.

I will supply the specific function interface and the architecture analysis in the context.
"""

main_func_task_description = """You are a highly skilled Python developer. Your task is to implement a robust and Pythonic main function by integrating a detailed architectural analysis, fully implemented auxiliary functions, and a well-defined main function interface.

Context:
- **Architectural Analysis:** A comprehensive review of the overall program structure.
- **Auxiliary Functions:** Complete and tested; these functions are available for integration.
- **Main Function Interface:** Includes the following requirements:
  - A valid Python function header.
  - A detailed docstring.

Requirements:
- Develop clean, well-structured, and idiomatic Python code.
- Adhere to best practices and follow the provided architectural guidelines.
- Correctly integrate all auxiliary functions based on the architectural analysis.
- Produce a complete, bug-free, and fully functional main function.
- The code for auxiliary functions does not need to be included in your output.

Note: The main function is also a function with possible parameters and return values. It is not the part of if __name__ == "__main__":. Its name might differ from "main".
All relevant context—the architecture analysis, auxiliary functions' code, and the main function interface—will be provided to you.
Your primary goal is to synthesize this information and implement the main function accordingly.
"""

tester_program_prompt = """You are a highly skilled Python developer. Your task is to generate an executable Python testing program along with its additional import statements. This program will be used to test a provided function interface using multiple test cases.

Context:
- A Python function interface is provided, including its function header and docstrings. (Note: The backend will insert the actual function implementation between your import_parts and your test_program.)
- A JSON-formatted sample test data is provided, which includes both test inputs and expected outputs.
- The provided import fields which you can use.

Your program should do the following:
- Read a string from standard input that contains a JSON array of test cases.
- Parse the JSON string to extract the test cases. If parsing fails, the program should exit with a return code of -1.
- For each test case in the array:
  - Extract the test inputs and expected outputs.
  - Call the provided Python function with the test inputs.
  - Compare the function's output with the expected outputs.
  - Record whether the test passed (0) or failed (1).
- Output a JSON array of test results, where each element is 0 (passed) or 1 (failed).
- You should capture the error from the provided function to prevent the program from crashing.
- If a test case fails to execute, the program should record this case as -1.

Output:
Produce two strings as your output:
   a. test_program: Contains the main runnable logic to test the provided function using multiple test cases.
   b. additional_import_parts: Contains all additional but necessary import statements required for the test program.

Note:
A sample test case is given in the context. Each test case in the JSON array should be similar to the sample test case.
The backend will concatenate the 'provided_import_fields', 'additional_import_parts', the complete target function, and the 'test_program' in order. Do not include any extra content beyond what is specified.
"""

sample_test_data_prompt = """You are a highly skilled Python developer.
Your task is to generate a sample test case data in JSON format for a given Python function interface.
The test case must include:
- Input values for the function.
- The corresponding expected outputs.

Since the function interface does not explicitly name its outputs, analyze the expected result format and assign clear, descriptive variable names to represent each output.
The name of the input variable must be consistent with the parameter names in the function interface.
The name of the output variable must start with 'output_' prefix.
Ensure the JSON structure is flat. Inputs and outputs should appear as top-level key-value pairs without nesting.

The provided function interface includes:
• A valid Python function header.
• A detailed docstring describing the function's behavior, expected inputs, and outputs.

Output:
- Your output should be strictly valid JSON. Do not include any additional text or explanation.
- The sample test case must be simple, correct, and adhere precisely to the guidelines in the function interface.
- Ensure consistency in data types; for example, do not mix booleans with integers or strings.
"""

test_data_gen_prompt = """You are a highly skilled Python developer.
Your task is to generate a list of test cases in JSON format for the provided Python test program. The test case must include both input values and the expected outputs.
A sample test case and the test program are given in the context; use them as references and ensure that your output strictly matches the expected parsing format.

Requirements:
- Generate exactly {num_test_cases} test cases.
- The output must be a valid JSON list, where each test case is a valid JSON object.
- Output only the JSON list without any additional text or explanation.
- Test cases should be diverse and cover various scenarios, including edge cases.
"""

main_test_data_gen_prompt = """You are a highly skilled Python developer.
Your task is to generate a list of test cases in JSON format for the provided Python program.
This program is designed to solve the problems described in the requirements text, which might include the constraints of the input values.
If the constraints are mentioned in the requirements text, please ensure that the test cases strictly follow the constraints.
The test case must include both input values and the expected outputs.
The requirements text, a sample test case, and the entire program are given in the context; use them as references and ensure that your output strictly matches the expected parsing format.

Requirements:
- Generate exactly {num_test_cases} test cases.
- The output must be a valid JSON list, where each test case is a valid JSON object.
- Output only the JSON list without any additional text or explanation.
- Test cases should be diverse and cover various scenarios, including edge cases.
- All test cases should under the constraints mentioned in the requirements text.
"""