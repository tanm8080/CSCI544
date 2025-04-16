# developer_agent.py
import dspy
from dotenv import load_dotenv
from architect_agent import ArchitectAgent
import prompt
import os
import ast
from utils import Candidate, GeneratedFunction
from colorama import Fore, Style


class DeveloperSignature(dspy.Signature):
    task_description: str =  dspy.InputField(desc="The description of your task.")
    architecture_analysis: str = dspy.InputField(desc="Detailed analysis of the program architecture.")
    function_interface: str = dspy.InputField(desc="The interface(function head and docstrings) of the incomplete function.")
    generate_function: str = dspy.OutputField(desc="The complete function code based on the function interface.")


class MainDeveloperSignature(dspy.Signature):
    task_description: str =  dspy.InputField(desc="The description of your task.")
    architecture_analysis: str = dspy.InputField(desc="Detailed analysis of the program architecture.")
    auxiliary_functions_code: str = dspy.InputField(desc="The code of completed and tested auxiliary functions.")
    function_interface: str = dspy.InputField(desc="The interface(function head and docstrings) of the incomplete main function.")
    generate_function: str = dspy.OutputField(desc="The complete main function code.")


class DeveloperAgent(dspy.Module):
    """
    Developer Agent:
    - Receives function interfaces from the Architect Agent.
    - Generates multiple candidate implementations for each function.
    - Uses dspy's Chain-of-Thought to interact with the LLM for code generation.
    """
    def __init__(self, llm, task_description, main_func_task_description, n):
        self.llm = llm
        self.task_description = task_description
        self.main_func_task_description = main_func_task_description
        # number of candidates
        self.n = n
        # Initialize chain-of-thought modules for coding reasoning
        self.developer_cot = dspy.ChainOfThought(DeveloperSignature)
        self.main_developer_cot = dspy.ChainOfThought(MainDeveloperSignature)


    def generate_candidates(self, generated_function: GeneratedFunction, architecture_analysis: str, error_threshold: int):
        """
        This function is only used to generate candidates for auxiliary functions.
        Generate multiple candidate implementations for a given function interface.
        Test the generated code has syntax errors or not.
        - If has syntax errors, try again until reaching the number of error_threshold.
        """
        candidates = []
        # Generate multiple candidates
        count = 0
        error_count = 0
        while count < self.n:
            result = self.developer_cot(task_description=self.task_description,
                                      architecture_analysis=architecture_analysis,
                                      function_interface=generated_function.interface,
                                      temperature=0.8)
            candidate = result.generate_function
            
            # Use ast to find whether the generated code has syntax errors
            try:
                ast.parse(candidate)
            except SyntaxError as e:
                print(Fore.RED + "Developer agent: generated function Syntax Error!" + Style.RESET_ALL, e)
                error_count += 1
                if error_count < error_threshold:
                    continue
                    
            count += 1
            candidates.append(candidate)
            # clean the error_count
            error_count = 0
        
        # create a list of Candidate objects
        candidate_objs = []
        for i, candidate_code in enumerate(candidates):
            candidate_objs.append(Candidate(candidate_index=i, candidate_code=candidate_code))
        
        assert len(candidate_objs) == self.n, "The number of candidates is not equal to n."
        generated_function.candidate_num = self.n
        generated_function.candidates = candidate_objs
    
    
    def auxiliary_developer(self, generated_auxiliary_functions: list[GeneratedFunction], architecture_analysis: str, error_threshold=2):
        """
        Generate multiple candidate implementations for auxiliary functions.
        """
        for generated_function in generated_auxiliary_functions:
            self.generate_candidates(generated_function, architecture_analysis, error_threshold)

    
    def main_developer(self, generated_main_function: GeneratedFunction, architecture_analysis: str, auxiliary_functions_code: str, error_threshold=2):
        """
        Generate multiple candidate implementations for the main function.
        """
        candidates = []
        # Generate multiple candidates
        count = 0
        error_count = 0
        while count < self.n:
            result = self.main_developer_cot(task_description=self.main_func_task_description,
                                      architecture_analysis=architecture_analysis,
                                      auxiliary_functions_code=auxiliary_functions_code,
                                      function_interface=generated_main_function.interface,
                                      temperature=0.8)
            candidate = result.generate_function
            
            # Use ast to find whether the generated code has syntax errors
            try:
                ast.parse(candidate)
            except SyntaxError as e:
                print("Generated function Syntax Error!", e)
                error_count += 1
                if error_count < error_threshold:
                    continue
                    
            count += 1
            candidates.append(candidate)
            # clean the error_count
            error_count = 0
        
        # create a list of Candidate objects
        candidate_objs = []
        for i, candidate_code in enumerate(candidates):
            candidate_objs.append(Candidate(candidate_index=i, candidate_code=candidate_code))
        
        assert len(candidate_objs) == self.n, "The number of candidates is not equal to n."
        generated_main_function.candidate_num = self.n
        generated_main_function.candidates = candidate_objs  


if __name__ == "__main__":
    # Configure Language Model
    load_dotenv()
    api_key = os.environ.get('API_KEY')
    lm = dspy.LM('openai/gpt-4o-mini', api_key=api_key)
    dspy.configure(lm=lm)

    # each function has 5 candidates
    n = 5

    # Example requirements text
    requirements_text = (
        "Develop a modular calculator that supports addition, subtraction, multiplication, and division. "
        "The system should be divided into smaller functions to handle basic operations independently, "
        "and a main function to integrate these operations."
    )

    # Architect agent
    test_architect_agent = ArchitectAgent(llm=lm,
                                           analysis_prompt_template=prompt.analysis_prompt_template,
                                            generation_prompt_template=prompt.generation_prompt_template)
    
    
    analysis_text, generated_auxiliary_functions, generated_main_functions = test_architect_agent.architect(requirements_text)

    # Developer agent
    test_developer_agent = DeveloperAgent(llm=lm,
                                          task_description=prompt.developer_agent_prompt,
                                          main_func_task_description=prompt.main_func_task_description,
                                          n=n)
    test_developer_agent.auxiliary_developer(generated_auxiliary_functions, analysis_text, error_threshold=2)
    
    # print
    print("——————————————————————————————————————————————————————————————————————————————————————————————")
    for generated_auxiliary_function in generated_auxiliary_functions:
        print(generated_auxiliary_function.candidates[0].candidate_code)