# tester_agent.py
import dspy
import prompt
import os
import ast
from dotenv import load_dotenv
import subprocess
from architect_agent import ArchitectAgent
from developer_agent import DeveloperAgent
import numpy as np
from kmodes.kmodes import KModes
from utils import GeneratedFunction, Candidate
from colorama import Fore, Style
import json
import ast
import re

class TestProgGenerationSignature(dspy.Signature):
    task_description: str =  dspy.InputField(desc="The description of your task.")
    function_interface: str = dspy.InputField(desc="The interface(a function head and docstrings) of the target function.")
    sample_test_data: str = dspy.InputField(desc="The sample test case in JSON format.")
    provided_import_fields: str = dspy.InputField(desc="The provided import fields which you can use.")
    test_program: str = dspy.OutputField(desc="The generated test program for testing multiple test cases.")
    additional_import_parts: str = dspy.OutputField(desc="The additional but necessary import statements required for the test program, code only.")

class SampleCaseGenerationSignature(dspy.Signature):
    task_description: str =  dspy.InputField(desc="The description of your task.")
    function_interface: str = dspy.InputField(desc="The provided interface(a function head and docstrings) of the test function.")
    sample_test_case: str = dspy.OutputField(desc="The generated sample test case.")

class TestCaseGenerationSignature(dspy.Signature):
    task_description: str =  dspy.InputField(desc="The description of your task.")
    test_program: str = dspy.InputField(desc="The provided Python test program.")
    sample_test_case: str = dspy.InputField(desc="The sample test case.")
    test_cases: list[str] = dspy.OutputField(desc="The list of generated test cases in JSON format.")

class MainTestCaseGenerationSignature(dspy.Signature):
    task_description: str =  dspy.InputField(desc="The description of your task.")
    requirements_text: str = dspy.InputField(desc="The description of the main task of the entire program.")
    test_program: str = dspy.InputField(desc="The provided Python program.")
    sample_test_case: str = dspy.InputField(desc="The sample test case.")
    test_cases: list[str] = dspy.OutputField(desc="The list of generated test cases in JSON format.")

class TesterAgent(dspy.Module):
    """
    Tester Agent:
    - Receives a completed function from the Developer Agent.
    - Generate a test program for the function.
    - Generate multiple test cases in json format.
    - Run the test program with the test cases.
    """
    def __init__(self, llm, tester_program_prompt, sample_test_data_prompt, test_data_gen_prompt, main_test_data_gen_prompt):
        # test_cases is a dict mapping function names to a list of test cases
        self.llm = llm
        self.tester_program_prompt = tester_program_prompt
        self.sample_test_data_prompt = sample_test_data_prompt
        self.test_data_gen_prompt = test_data_gen_prompt
        self.main_test_data_gen_prompt = main_test_data_gen_prompt
        self.test_prog_gen_cot = dspy.ChainOfThought(TestProgGenerationSignature)
        self.sample_test_gen_cot = dspy.ChainOfThought(SampleCaseGenerationSignature)
        self.test_cases_gen_cot = dspy.ChainOfThought(TestCaseGenerationSignature)
        self.main_test_cases_gen_cot = dspy.ChainOfThought(MainTestCaseGenerationSignature)
    def generate_test_program(self, function_interface, sample_test_data, provided_import_fields, error_threshold=2):
        """
        Generate the test program and import parts for the given function interface.
        The test program will be able to handle multiple test cases at once.
        """
        error_count = 0
        while error_count < error_threshold:
            result = self.test_prog_gen_cot(task_description=self.tester_program_prompt,
                                            function_interface=function_interface,
                                            sample_test_data=sample_test_data,
                                            provided_import_fields=provided_import_fields,
                                            )
            test_program = result.test_program
            additional_import_parts = result.additional_import_parts
            # Use ast to find whether the generated code has syntax errors
            try:
                ast.parse((provided_import_fields + '\n' + additional_import_parts + "\n" + test_program))
                return test_program, additional_import_parts
            except SyntaxError as e:
                print(Fore.RED + "Tester agent: generated test program Syntax Error!" + Style.RESET_ALL, e)
                error_count += 1

        print(Fore.RED + "Tester agent: failed to generate a valid test program under error threshold." + Style.RESET_ALL)
        return test_program, additional_import_parts
    

    def generate_sample_case(self, function_interface):
        """
        Generate a sample test case for the given test program.
        """
        result = self.sample_test_gen_cot(task_description=self.sample_test_data_prompt,
                                           function_interface=function_interface)
        return result.sample_test_case
    
    
    def validate_sample_test_data(self, sample_test_data, candidate_code, error_threshold=2):
        """
        Validate and fix the sample test data to ensure it corresponds to the first candidate function.
        Uses the AST package to analyze the function signature and ensure the test data matches.
        
        Args:
            sample_test_data (str): The sample test data in JSON format
            candidate_code (str): The code of the first candidate function
            error_threshold (int): Maximum number of attempts to fix the sample test data
            
        Returns:
            str: The validated and potentially fixed sample test data
        """   
        # Parse the candidate code to extract function signature
        try:
            tree = ast.parse(candidate_code)
            function_def = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    function_def = node
                    break
            
            if not function_def:
                print(Fore.RED + "Tester agent: Could not find function definition in candidate code" + Style.RESET_ALL)
                return sample_test_data
            
            # Extract parameter names from function signature
            param_names = [arg.arg for arg in function_def.args.args]
            
            # Try to parse the sample test data as JSON
            try:
                test_data = json.loads(sample_test_data)
            except json.JSONDecodeError as e:
                print(Fore.RED + f"Tester agent: Invalid JSON in sample test data: {e}" + Style.RESET_ALL)
                # Try to fix common JSON issues
                error_count = 0
                while error_count < error_threshold:
                    # Try to fix common JSON issues
                    fixed_data = sample_test_data
                    # Fix missing quotes around keys
                    fixed_data = re.sub(r'(\w+):', r'"\1":', fixed_data)
                    # Fix missing quotes around string values
                    fixed_data = re.sub(r':\s*([^"\d\[\]{},\s][^,\[\]{}\s]*)\s*([,}])', r': "\1"\2', fixed_data)
                    
                    try:
                        test_data = json.loads(fixed_data)
                        print(Fore.GREEN + "Tester agent: Successfully fixed JSON format" + Style.RESET_ALL)
                        return fixed_data
                    except json.JSONDecodeError:
                        error_count += 1
                
                print(Fore.RED + "Tester agent: Failed to fix JSON format after multiple attempts" + Style.RESET_ALL)
                return sample_test_data
            
            # Check if all required parameters are in the test data
            missing_params = [param for param in param_names if param not in test_data]
            if missing_params:
                print(Fore.YELLOW + f"Tester agent: Missing parameters in sample test data: {missing_params}" + Style.RESET_ALL)
                
                # Try to add missing parameters with default values
                for param in missing_params:
                    # Find the parameter in the function definition to get its default value
                    for arg in function_def.args.args:
                        if arg.arg == param and hasattr(arg, 'annotation'):
                            # Use a reasonable default based on the type annotation
                            if isinstance(arg.annotation, ast.Name):
                                if arg.annotation.id == 'int':
                                    test_data[param] = 0
                                elif arg.annotation.id == 'float':
                                    test_data[param] = 0.0
                                elif arg.annotation.id == 'str':
                                    test_data[param] = ""
                                elif arg.annotation.id == 'bool':
                                    test_data[param] = False
                                elif arg.annotation.id == 'list':
                                    test_data[param] = []
                                elif arg.annotation.id == 'dict':
                                    test_data[param] = {}
                                else:
                                    test_data[param] = None
                            else:
                                test_data[param] = None
            
            # Check for extra parameters that are not in the function signature
            extra_params = [param for param in test_data.keys() if param not in param_names and not param.startswith('output_')]
            if extra_params:
                print(Fore.YELLOW + f"Tester agent: Extra parameters in sample test data: {extra_params}" + Style.RESET_ALL)
                # Remove extra parameters
                for param in extra_params:
                    del test_data[param]
            
            # Check if there's an expected output, if not, add a placeholder(Basic Method)
            expected_output_keys = [key for key in test_data.keys() if key.startswith('output_')]
            if not expected_output_keys:
                print(Fore.YELLOW + "Tester agent: No expected output in sample test data" + Style.RESET_ALL)
                # Add a placeholder expected output
                test_data['output_result'] = None
            
            return json.dumps(test_data)
            
        except Exception as e:
            print(Fore.RED + f"Tester agent: Error validating sample test data: {e}" + Style.RESET_ALL)
            return sample_test_data
        
    
    def generate_test_cases(self, test_program, sample_test_data, num_test_cases, requirements_text=None):
        """
        Generate test cases for the given test program.
        """
        if requirements_text is not None:
            test_gen_prompt = self.main_test_data_gen_prompt.format(num_test_cases=num_test_cases)
            result = self.main_test_cases_gen_cot(task_description=test_gen_prompt,
                                                  requirements_text=requirements_text,
                                                  test_program=test_program,
                                                  sample_test_case=sample_test_data)
        else:
            test_gen_prompt = self.test_data_gen_prompt.format(num_test_cases=num_test_cases)
            result = self.test_cases_gen_cot(task_description=test_gen_prompt,
                                            test_program=test_program,
                                            sample_test_case=sample_test_data)
        return result.test_cases
    

    def main_test_func(self, generated_function: GeneratedFunction, num_test_cases: int, error_threshold=3):
        """
        Test the given function with the generated test cases.
        return a list of test results. Each element is 0 or 1:
        - 0 means passed
        - 1 means failed
        - -1 means the test program execution failed
        The length of the list is equal to the number of test cases.

        return:
        - None: If the sample test program execution failed.
        - A list of test results: If the sample test program execution passed.
        """
        print (Fore.BLUE + "Tester agent: test function:\n" + Style.RESET_ALL, generated_function.interface)
        generated_function.test_cases_num = num_test_cases

        # step 1: generate the sample test data
        sample_test_data = self.generate_sample_case(generated_function.interface)
        
        # Validate and fix the sample test data using AST
        print(Fore.BLUE + "Tester agent: validating sample test data..." + Style.RESET_ALL)
        sample_test_data = self.validate_sample_test_data(sample_test_data, generated_function.candidates[0].candidate_code)
        # Parse each test case to ensure they are valid JSON
        try:
            sample_test_case = json.loads(sample_test_data)
        except json.JSONDecodeError as e:
            print(Fore.RED + "Tester agent: failed to parse sample test data to json!" + Style.RESET_ALL)
            print(e)
            sample_test_case = {}
        sample_test_data = json.dumps(sample_test_case)
        generated_function.sample_test_case = sample_test_data

        # step 2: generate the test program
        test_program_main, additional_import_parts= self.generate_test_program(generated_function.interface, sample_test_data, generated_function.program_import_fields)
        generated_function.function_tester_main = test_program_main
        generated_function.function_tester_imports = additional_import_parts
        # Synthesize import_parts
        import_parts = generated_function.program_import_fields + '\n' + additional_import_parts
        # Use the first candidate function to make a complete test program
        test_program = generated_function.candidates[0].candidate_code + '\n' + test_program_main
        # if the generated function is a main function, add the auxiliary functions code to the test program
        if generated_function.type == "main":
            test_program = generated_function.auxiliary_functions_code + '\n' + test_program
        # Add import parts
        test_program = import_parts + '\n' + test_program
        print(Fore.BLUE + "Tester agent: test program:\n" + Style.RESET_ALL)
        print(test_program)
        print(Fore.BLUE + "Tester agent: sample test case:\n" + Style.RESET_ALL)
        print(sample_test_data)

        # Save and run the test program
        with open("test_program.py", "w") as f:
            f.write(test_program)
        
        result = subprocess.run(
            ['python', 'test_program.py'],
            input="[" + sample_test_data + "]",
            capture_output=True,
            text=True)

        if result.returncode == -1 or result.stderr != "":
            print(Fore.RED + "Tester agent: sample test program execution failed or JSON parsing failed!" + Style.RESET_ALL)
            print(Fore.RED + "Tester agent: sample test data:" + Style.RESET_ALL)
            print(sample_test_data)
            print(result.stderr)
            print(result.returncode)
            # TODO: find out the reason why the test program failed, and improve the test program and the sample test data
            # return None
        if result.returncode == 1:
            pass
            print(Fore.BLUE + "Tester agent: sample test case failed!" + Style.RESET_ALL)

        # Make sure the sample test program and the sample test data are valid here
        # step 3: generate the test cases
        test_cases = None
        if generated_function.type == "main":
            test_cases = self.generate_test_cases(test_program, sample_test_data, num_test_cases, generated_function.requirements_text)
        else:
            test_cases = self.generate_test_cases(test_program, sample_test_data, num_test_cases)
        generated_function.test_cases = test_cases

        if len(test_cases) != num_test_cases:
            print(Fore.RED + "Tester agent: failed to generate the required number of test cases!" + Style.RESET_ALL)
            # Try to fix this issue by generating more test cases or trimming the list
            max_attempts = error_threshold
            attempt = 0
            
            while len(test_cases) != num_test_cases and attempt < max_attempts:
                attempt += 1
                print(Fore.YELLOW + f"Tester agent: Attempt {attempt}/{max_attempts} to fix test case count" + Style.RESET_ALL)
                if len(test_cases) < num_test_cases:
                    # Generate additional test cases
                    additional_cases_needed = num_test_cases - len(test_cases)
                    print(Fore.YELLOW + f"Tester agent: Generating {additional_cases_needed} more test cases" + Style.RESET_ALL)
                    if generated_function.type == "main":
                        additional_cases = self.generate_test_cases(
                            test_program, sample_test_data, additional_cases_needed, 
                            generated_function.requirements_text
                        )
                    else:
                        additional_cases = self.generate_test_cases(
                            test_program, sample_test_data, additional_cases_needed
                        )
                    # Add the new test cases to the existing ones
                    test_cases.extend(additional_cases)
                elif len(test_cases) > num_test_cases:
                    # Trim the list to the required number
                    print(Fore.YELLOW + f"Tester agent: Trimming test cases from {len(test_cases)} to {num_test_cases}" + Style.RESET_ALL)
                    test_cases = test_cases[:num_test_cases]
            
            # If we still don't have the right number after multiple attempts, trim the list if we have more test cases, add sample test cases if we have less test cases
            while len(test_cases) < num_test_cases:
                test_cases.append(sample_test_case)
            if len(test_cases) > num_test_cases:
                test_cases = test_cases[:num_test_cases]

        # Parse each test case to ensure they are valid JSON
        parsed_test_cases = []
        for test_case in test_cases:
            # Parse the test case string into a Python dict
            try:
                parsed_case = json.loads(test_case)
                parsed_test_cases.append(parsed_case)
            except json.JSONDecodeError as e:
                print(Fore.RED + f"Tester agent: failed to parse test case: {test_case}, use the sample test case instead!" + Style.RESET_ALL)
                print(e)
                parsed_test_cases.append(sample_test_case)
        test_cases = parsed_test_cases

        # Make sure the test cases are valid here
        print(Fore.BLUE + "Tester agent: test cases:\n" + Style.RESET_ALL)
        # Create a JSON array of all test cases
        all_test_cases_json = json.dumps(test_cases)
        print(all_test_cases_json)

        print(Fore.BLUE + "Tester agent: start testing each candidates with the test cases" + Style.RESET_ALL)
        # step 4: Testing each function candidates and record the results
        test_results = []

        for candidate in generated_function.candidates:
            test_result = []
            if generated_function.type == "main":
                test_program = import_parts + '\n' + generated_function.auxiliary_functions_code + '\n' + candidate.candidate_code + '\n' + test_program_main
            else:
                test_program = import_parts + '\n' + candidate.candidate_code + '\n' + test_program_main
            # record the test program for each candidate
            candidate.candidate_tester = test_program
            # Save and run the test program
            with open("test_program.py", "w") as f:
                f.write(test_program)
            
            # Run the test program with all test cases at once
            result = subprocess.run(
                ['python', 'test_program.py'],
                input=all_test_cases_json,
                capture_output=True,
                text=True)
                
            if result.returncode == -1 or result.stderr != "":
                print(Fore.RED + f"Tester agent: test program execution failed for candidate {candidate.candidate_index}!" + Style.RESET_ALL)
                print(result.stderr)
                # If the test program execution failed, mark all test cases as failed
                test_result = [-1] * len(test_cases)
            else:
                # Parse the test results from the output
                try:
                    # The test program should output a JSON array of test results
                    test_result = json.loads(result.stdout)
                    if not isinstance(test_result, list) or len(test_result) != len(test_cases):
                        print(Fore.RED + f"Tester agent: invalid test results format for candidate {candidate.candidate_index}!" + Style.RESET_ALL)
                        test_result = [-1] * len(test_cases)
                except json.JSONDecodeError:
                    print(Fore.RED + f"Tester agent: failed to parse test results for candidate {candidate.candidate_index}!" + Style.RESET_ALL)
                    test_result = [-1] * len(test_cases)
            
            test_results.append(test_result)

            # record the test result for each candidate
            candidate.candidate_test_result = test_result
            # calculate the score for each candidate
            candidate.candidate_score = 0
            for i in range(len(test_result)):
                if test_result[i] == 0:
                    candidate.candidate_score += 1
            
        # record the test results for the generated function
        print(Fore.BLUE + "Tester agent: The Test Result:" + Style.RESET_ALL)
        print(test_results)
        generated_function.test_results = test_results
    
    
    def cluster_test_results(self, generated_function: GeneratedFunction, cluster_num: int):
        """
        Cluster the test results into cluster_num clusters.
        """
        # Convert the test results to a numpy array
        test_results = np.array(generated_function.test_results)

        # Use KModes to cluster the test results
        km = KModes(n_clusters=cluster_num, init='Cao', n_init=5)
        clusters = km.fit_predict(test_results)

        # Record the cluster results for the generated function
        generated_function.cluster_num = cluster_num
        generated_function.cluster_results = clusters
        # Record the cluster id for each candidate
        for candidate in generated_function.candidates:
            candidate.cluster_id = clusters[candidate.candidate_index]


    def filter_candidates(self, generated_function: GeneratedFunction):

        # TODO: filter the candidates based on the clusters and the test results
        # Filter candidates based on clusters and test results
        cluster_results = generated_function.cluster_results
        filtered_candidates = []

        # Group candidates by their cluster ID
        cluster_groups = {}
        for candidate in generated_function.candidates:
            cluster_id = candidate.cluster_id
            if cluster_id not in cluster_groups:
                cluster_groups[cluster_id] = []
            cluster_groups[cluster_id].append(candidate)

        # Select the best candidate from each cluster based on the score
        for cluster_id, candidates in cluster_groups.items():
            best_candidate = max(candidates, key=lambda c: c.candidate_score)
            filtered_candidates.append(best_candidate)

        # Update the generated function with the filtered candidates
        generated_function.filtered_candidates = filtered_candidates
        pass
        


    def basic_selector(self, generated_function: GeneratedFunction):
        """
        Select the best candidate based on the score.
        """
        best_candidate: Candidate = None
        best_score = -1
        for candidate in generated_function.candidates:
            if candidate.candidate_score > best_score:
                best_score = candidate.candidate_score
                best_candidate = candidate
        generated_function.final_candidate = best_candidate
        return best_candidate


    def test_and_select(self, generated_functions: list[GeneratedFunction], num_test_cases: int):
        """
        Test each generated function and choose the best candidate for each function.
        """
        for generated_function in generated_functions:
            self.main_test_func(generated_function, num_test_cases)
            best_candidate = self.basic_selector(generated_function)
            print(Fore.BLUE + "best candidate:\n" + Style.RESET_ALL, best_candidate.candidate_code)


if __name__ == "__main__":
    # Configure Language Model
    load_dotenv()
    api_key = os.environ.get('API_KEY')
    lm = dspy.LM('openai/gpt-4o-mini', api_key=api_key)
    dspy.configure(lm=lm)

    # Architect agent
    test_architect_agent = ArchitectAgent(llm=lm,
                                        analysis_prompt_template=prompt.analysis_prompt_template,
                                        generation_prompt_template=prompt.generation_prompt_template)
    
    # Developer agent
    test_developer_agent = DeveloperAgent(llm=lm,
                                        task_description=prompt.developer_agent_prompt,
                                        n=5)
    
    # Tester agent
    test_tester_agent = TesterAgent(llm=lm,
                                    tester_program_prompt=prompt.tester_program_prompt,
                                    sample_test_data_prompt=prompt.sample_test_data_prompt,
                                    test_data_gen_prompt=prompt.test_data_gen_prompt)
    
    requirements_text = (
        "Develop a modular calculator that supports addition, subtraction, multiplication, and division. "
        "The system should be divided into smaller functions to handle basic operations independently, "
        "and a main function to integrate these operations."
    )

    # Step 1: Architect agent
    analysis_text, generated_auxiliary_functions, generated_main_functions = test_architect_agent.architect(requirements_text)

    # Step 2: Developer agent
    test_developer_agent.auxiliary_developer(generated_auxiliary_functions, analysis_text, error_threshold=2)

    # step 3: tester agent test
    for generated_function in generated_auxiliary_functions:
        test_tester_agent.main_test_func(generated_function, num_test_cases=10)
        best_candidate = test_tester_agent.basic_selector(generated_function)
        print("Best candidate:\n", best_candidate.candidate_code)
   