from dataclasses import dataclass

@dataclass
class Candidate:
    """
    A class to represent a candidate.
    """
    candidate_index: int
    candidate_code: str
    candidate_tester: str = None
    candidate_test_result: list[int] = None
    candidate_score: int = None
    cluster_id: int = None
    score: int = None


@dataclass
class GeneratedFunction:
    """
    A class to represent a generated function.
    """
    # These properties are filled by the architect agent
    type: str # Type of the function (e.g., "main", "auxiliary")
    interface: str # The function interface (signature and docstring)
    program_import_fields: str

    # These properties are filled by the developer agent
    candidate_num: int = 0
    candidates: list[Candidate] = None

    # These properties are filled by the tester agent
    auxiliary_functions_code: str = None # Only used for main function
    requirements_text: str = None # Only used for main function
    sample_test_case: str = None # A sample test case for the function
    function_tester_main: str = None
    additional_tester_imports: str = None
    test_cases_num: int = 0
    test_cases: list[str] = None
    test_results: list[list[int]] = None
    cluster_num: int = 0
    cluster_results: list[int] = None
    filtered_candidates: list[Candidate] = None
    final_candidate: Candidate = None