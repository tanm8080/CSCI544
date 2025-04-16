# main.py
from architect_agent import ArchitectAgent
from developer_agent import DeveloperAgent
from tester_agent import TesterAgent
import dspy
from dotenv import load_dotenv
import prompt
import os
from utils import Candidate, GeneratedFunction
from colorama import init, Fore, Style

def main():
    # Configure Language Model
    load_dotenv()
    api_key = os.environ.get('API_KEY')
    lm = dspy.LM('openai/gpt-4o-mini', api_key=api_key)
    dspy.configure(lm=lm)
    # Init colorama
    init()

    requirements_text: str = None # a multi-line string which describes the requirement of the task

    # Hyperparameters:
    candidate_num: int
    test_case_num: int
    selector_type: int # 0 for basic selector, 1 for advanced selector
    cluster_num: int
    error_threshold: int = 2

    # Read Hyperparameters from stdin:
    while True:
        try:
            candidate_num = int(input(Fore.YELLOW + Style.BRIGHT + "Please input candidate_num(int):" + Style.RESET_ALL))
            assert(candidate_num > 0)
            break
        except ValueError:
            print(Fore.YELLOW + Style.BRIGHT + "Input Error, please try again!" + Style.RESET_ALL)
    
    while True:
        try:
            test_case_num = int(input(Fore.YELLOW + Style.BRIGHT + "Please input test_case_num(int):" + Style.RESET_ALL))
            assert(test_case_num > 0)
            break
        except ValueError:
            print(Fore.YELLOW + Style.BRIGHT + "Input Error, please try again!" + Style.RESET_ALL)

    while True:
        try:
            selector_type = int(input(Fore.YELLOW + Style.BRIGHT + "Please input selector_type(0 basic selector; 1 advanced selector):" + Style.RESET_ALL))
            assert(selector_type == 1 or selector_type == 0)
            break
        except ValueError:
            print(Fore.YELLOW + Style.BRIGHT + "Input Error, please try again!" + Style.RESET_ALL)
    
    while True:
        try:
            cluster_num = int(input(Fore.YELLOW + Style.BRIGHT + "Please input cluster_num(>= 2, int):" + Style.RESET_ALL))
            assert(cluster_num >= 2)
            break
        except ValueError:
            print(Fore.YELLOW + Style.BRIGHT + "Input Error, please try again!" + Style.RESET_ALL)
    
    # Read requirement text from stdin:
    print(Fore.YELLOW + Style.BRIGHT + "Please input the requirements text. End with a line:'END' " + Style.RESET_ALL)
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    requirements_text = "\n".join(lines)
    print(Fore.YELLOW + Style.BRIGHT + "The requirements text is:" + Style.RESET_ALL)
    print(requirements_text)

    # Ask user to confirm
    print(Fore.YELLOW + Style.BRIGHT + "Enter Y to start all agents for code generation, enter N to halt." + Style.RESET_ALL)
    input_command = input()
    if input_command != "Y":
        print(Fore.YELLOW + Style.BRIGHT + "System halted." + Style.RESET_ALL)
        return

    # Architect agent
    architect_agent = ArchitectAgent(llm=lm,
                                        analysis_prompt_template=prompt.analysis_prompt_template,
                                        generation_prompt_template=prompt.generation_prompt_template)
    # Developer agent
    developer_agent = DeveloperAgent(llm=lm,
                                        task_description=prompt.developer_agent_prompt,
                                        main_func_task_description=prompt.main_func_task_description,
                                        n=candidate_num) 
    # Tester agent
    tester_agent = TesterAgent(llm=lm,
                                    tester_program_prompt=prompt.tester_program_prompt,
                                    sample_test_data_prompt=prompt.sample_test_data_prompt,
                                    test_data_gen_prompt=prompt.test_data_gen_prompt,
                                    main_test_data_gen_prompt=prompt.main_test_data_gen_prompt)
    

    final_result = ""

    # Step 1: Architect agent
    print(Fore.GREEN + Style.BRIGHT + "Step1: architect agent analysizes the architecture and designs interfaces" + Style.RESET_ALL)
    generated_auxiliary_functions: list[GeneratedFunction] = None
    generated_main_functions: list[GeneratedFunction] = None

    analysis_text, generated_auxiliary_functions, generated_main_functions = architect_agent.architect(requirements_text)

    # Step 2: Developer agent develop auxiliary functions
    print(Fore.GREEN + Style.BRIGHT + "Step 2: developer agent starts to develop auxiliary functions " + Style.RESET_ALL)
    developer_agent.auxiliary_developer(generated_auxiliary_functions, analysis_text, error_threshold)

    # step 3: tester agent test auxiliary functions and selector the best one
    print(Fore.GREEN + Style.BRIGHT + "Step 3: tester agent starts to test auxiliary functions and choose the final candidate " + Style.RESET_ALL)
    if selector_type == 0:
        tester_agent.test_and_select(generated_auxiliary_functions, test_case_num)
    else:
        # TODO: advance selector
        pass

    # Step 4: concatenate auxiliary functions
    print(Fore.GREEN + Style.BRIGHT + "Step 4: concatenate auxiliary functions" + Style.RESET_ALL)
    for generated_auxiliary_function in generated_auxiliary_functions:
        final_result += generated_auxiliary_function.final_candidate.candidate_code + "\n\n"
    
    # Step 5: Developer agent develop the main function
    print(Fore.GREEN + Style.BRIGHT + "Step 5: developer agent develops the main function" + Style.RESET_ALL)
    generated_main_function = generated_main_functions[0]
    generated_main_function.requirements_text = requirements_text
    generated_main_function.auxiliary_functions_code = final_result
    developer_agent.main_developer(generated_main_function, analysis_text, auxiliary_functions_code=final_result, error_threshold=error_threshold)

    # Step 6: tester agent test main function and choose the best one
    print(Fore.GREEN + Style.BRIGHT + "Step 6:  tester agent test main function and choose the best one" + Style.RESET_ALL)
    if selector_type == 0:
        tester_agent.test_and_select([generated_main_function], test_case_num)
    else:
        pass
        # TODO: advance selector

    # Step 7: print the final result
    final_result += generated_main_function.final_candidate.candidate_code
    final_result = generated_main_function.program_import_fields + '\n' + final_result
    print(Fore.GREEN + Style.BRIGHT + "\nFinal Result:(it is also saved in final_result.py)" + Style.RESET_ALL)
    print("_" * 100)
    print(final_result)
    # save the final result
    with open("final_result.py", "w") as f:
        f.write(final_result)


if __name__ == "__main__":
    main()

