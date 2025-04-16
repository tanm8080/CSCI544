# architect_agent.py
import dspy
from dotenv import load_dotenv
import os
import prompt
from utils import Candidate, GeneratedFunction
from colorama import Fore, Style

class ArchitectAnalysisSignature(dspy.Signature):
    task_description: str = dspy.InputField(desc="The description of your task.")
    architecture_analysis: str = dspy.OutputField(desc="Detailed analysis of the program architecture.")
    program_import_fields: str = dspy.OutputField(desc="All necessary import statements required for the whole program, code only.")

class InterfaceGenerationSignature(dspy.Signature):
    task_description: str = dspy.InputField(desc="The description of your task.")
    generation_prompt: str = dspy.InputField(desc="Detailed analysis of your task and the program architecture.")
    auxiliary_function_interfaces: list[str] = dspy.OutputField(desc="The list of auxiliary function interfaces which includes the function header and docstring.")
    main_function_interfaces: list[str] = dspy.OutputField(desc="The list of main function interfaces which includes the function header and docstring.")

class ArchitectAgent(dspy.Module):
    """
     Architect Agent:
    1. Analyzes user requirements and produces an architecture analysis text.
       This analysis explains key design decisions and decomposes the overall task.
       The resulting analysis text can be shared with other agents to reinforce their understanding.
    2. Generates function interfaces based on the analysis text for both auxiliary and main functions.
        Each interface includes a function signature and detailed comments(docstrings) adhere to standard python conventions.
    """

    def __init__(self, llm, analysis_prompt_template, generation_prompt_template):
        """
        Initialize the Architect Agent with:
          - llm: An instance of the language model to be used.
          - analysis_prompt_template: Template to generate an analysis text from requirements.
          - generation_prompt_template: Template to generate function headers and docstrings based on the analysis.
        """
        self.llm = llm
        self.analysis_prompt_template = analysis_prompt_template
        self.generation_prompt_template = generation_prompt_template
        # Create Chain-of-Thought modules for each step
        self.analysis_cot = dspy.ChainOfThought(ArchitectAnalysisSignature)
        self.generate_cot = dspy.ChainOfThought(InterfaceGenerationSignature)


    def generate_architecture_analysis(self, user_requirements):
        """
        Generate a detailed analysis text from the given user requirements.
        """
        # Format the prompt with the given requirements
        prompt = self.analysis_prompt_template.format(requirements=user_requirements)
        # Use the LLM to generate the analysis text via dspy's Chain-of-Thought
        analysize = self.analysis_cot(task_description=prompt)
        architecture_analysis = analysize.architecture_analysis
        program_import_fields = analysize.program_import_fields
        return architecture_analysis, program_import_fields
    

    def generate_function_interfaces(self, task_description, architecture_analysis, program_import_fields):
        """
        Generate function interfaces for both auxiliary and main functions with detailed comments.
        The interfaces are based on the architecture analysis text produced earlier.
        
        Parameters:
            architecture_analysis (str): The architecture analysis text.
            program_import_fields (str)
        
        Returns:
            auxiliary_function_interfaces (list[str]): The generated list of auxiliary function interfaces
            main_function_interface (list[str]): The generated list of main function interfaces
        """
        # Generate the function interfaces using the LLM
        generation_prompt = self.generation_prompt_template.format(architecture_analysis=architecture_analysis, program_import_fields=program_import_fields)
        generate = self.generate_cot(task_description=task_description, generation_prompt=generation_prompt)
        auxiliary_function_interfaces = generate.auxiliary_function_interfaces
        main_function_interfaces =  generate.main_function_interfaces
        return  auxiliary_function_interfaces, main_function_interfaces
    
    def architect(self, requirements):
        """
        Main method to run the architecting process.
        Steps:
          1. Generate the architecture analysis text from requirements.
          2. Generate detailed function interfaces based on the analysis.
        
        Parameters:
            requirements (str): The user-provided requirements text.
        
        Returns:
            analysis_text (str): The generated analysis text.
            auxiliary_function_interfaces (list[str]): The generated list of auxiliary function interfaces
            main_function_interface (list[str]): The generated list of main function interfaces
        """
        # Step 1: Generate architecture analysis text
        print(Fore.BLUE + "Architect-agent: start analysis the architecture of the program" + Style.RESET_ALL)
        analysis_text, program_import_fields = self.generate_architecture_analysis(requirements)
        print(Fore.BLUE + "Architect-agent: the result of the analysis:" + Style.RESET_ALL)
        print(analysis_text)
        print(Fore.BLUE + "Architect-agent: the program import fields:" + Style.RESET_ALL)
        print(program_import_fields)
        print(Fore.BLUE + "Architect-agent: the result of the analysis is saved in analysis_text.txt" + Style.RESET_ALL)
        with open("analysis_text.txt", "w") as f:
            f.write(analysis_text)

        # Step 2: Generate function interfaces with detailed comments
        print(Fore.BLUE + "Architect-agent: start generate the function interfaces" + Style.RESET_ALL)
        auxiliary_function_interfaces, main_function_interfaces = self.generate_function_interfaces(requirements, analysis_text, program_import_fields)
        print(Fore.BLUE + "Architect-agent: auxiliary function interfaces:" + Style.RESET_ALL)
        print(auxiliary_function_interfaces)
        print(Fore.BLUE + "Architect-agent: main function interfaces:" + Style.RESET_ALL)
        print(main_function_interfaces)

        # put results into GeneratedFunction
        generated_auxiliary_functions = []
        for auxiliary_function_interface in auxiliary_function_interfaces:
            generated_auxiliary_functions.append(GeneratedFunction(type="auxiliary", interface=auxiliary_function_interface, program_import_fields=program_import_fields))

        generated_main_functions = []
        for main_function_interface in main_function_interfaces:
            generated_main_functions.append(GeneratedFunction(type="main", interface=main_function_interface, program_import_fields=program_import_fields))

        return analysis_text, generated_auxiliary_functions, generated_main_functions


# Example usage (if run as a script)
if __name__ == "__main__":
    load_dotenv()
    api_key = os.environ.get('API_KEY')
    
    # Initialize a LLM instance
    lm = dspy.LM('openai/gpt-4o-mini', api_key=api_key)
    dspy.configure(lm=lm)
    
    # Create the Architect Agent
    architect_agent = ArchitectAgent(
        llm=lm,
        analysis_prompt_template=prompt.analysis_prompt_template,
        generation_prompt_template=prompt.generation_prompt_template
    )
    
    # Example requirements text
    requirements_text = (
        "Develop a modular calculator that supports addition, subtraction, multiplication, and division. "
        "The system should be divided into smaller functions to handle basic operations independently, "
        "and a main function to integrate these operations."
    )

    architect_agent.architect(requirements_text)