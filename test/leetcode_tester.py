import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
import dspy
from typing import Dict, List, Tuple, Any, Optional, Union
import argparse
import tempfile
import subprocess
import glob
import random

class LeetCodeScraper:
    """
    Component responsible for scraping problem information from the LeetCode website.
    """
    
    def __init__(self, cache_dir: str = "leetcode_cache"):
        """
        Initialize the LeetCode scraper.
        
        Args:
            cache_dir: Directory to store scraped problems
        """
        self.cache_dir = cache_dir
        self.base_url = "https://leetcode.com/problems/"
        self.api_url = "https://leetcode.com/graphql"
        
        # Create cache directory
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    def get_problem_list(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get a list of problems from LeetCode.
        
        Args:
            limit: Maximum number of problems to retrieve
            
        Returns:
            List of problem information including id, title, and slug
        """
        print(f"Retrieving list of up to {limit} LeetCode problems...")
        
        # Cache file for problem list
        cache_file = os.path.join(self.cache_dir, "problem_list.json")
        
        # Check if cache exists
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                if len(cached_data) >= limit:
                    print(f"Using cached problem list with {len(cached_data)} problems")
                    return cached_data[:limit]
        
        # First try: Use GraphQL API
        try:
            problems = self._get_problems_via_graphql(limit)
            if problems:
                return problems
        except Exception as e:
            print(f"GraphQL API approach failed: {e}")
            print("Trying alternative approach...")
        
        # Second try: Use REST API
        try:
            problems = self._get_problems_via_rest(limit)
            if problems:
                return problems
        except Exception as e:
            print(f"REST API approach failed: {e}")
            print("Trying alternative approach...")
        
        # Third try: Scrape the problem list page
        try:
            problems = self._get_problems_via_scraping(limit)
            if problems:
                return problems
        except Exception as e:
            print(f"Web scraping approach failed: {e}")
        
        # If we have a problem list cache but it's smaller than requested
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                print(f"Using partial cached problem list with {len(cached_data)} problems")
                return cached_data
        
        # Use static fallback list of common problems
        return self._get_static_problem_list(limit)
    
    def _get_problems_via_graphql(self, limit: int) -> List[Dict[str, Any]]:
        """
        Get problem list using GraphQL API.
        """
        # GraphQL query to get problem list
        query = """
        query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
            problemsetQuestionList(
                categorySlug: $categorySlug
                limit: $limit
                skip: $skip
                filters: $filters
            ) {
                total
                questions {
                    questionId
                    questionFrontendId
                    title
                    titleSlug
                    difficulty
                }
            }
        }
        """
        
        variables = {
            "categorySlug": "",
            "limit": limit,
            "skip": 0,
            "filters": {}
        }
        
        # Add headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Content-Type': 'application/json',
            'Referer': 'https://leetcode.com/problemset/all/',
            'Origin': 'https://leetcode.com'
        }
        
        # Send request
        response = requests.post(
            self.api_url,
            json={'query': query, 'variables': variables},
            headers=headers
        )
        
        # Print response for debugging
        print(f"GraphQL API Status Code: {response.status_code}")
        
        data = response.json()
        
        # Debug output
        if 'errors' in data:
            print(f"GraphQL API Errors: {data['errors']}")
        
        if 'data' in data and 'problemsetQuestionList' in data['data'] and 'questions' in data['data']['problemsetQuestionList']:
            questions = data['data']['problemsetQuestionList']['questions']
            
            # Sort questions by ID
            questions.sort(key=lambda q: int(q['questionFrontendId']))
            
            # Save to cache
            cache_file = os.path.join(self.cache_dir, "problem_list.json")
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(questions, f)
            
            print(f"Retrieved {len(questions)} problems via GraphQL API")
            return questions[:limit]
        
        return []
    
    def _get_problems_via_rest(self, limit: int) -> List[Dict[str, Any]]:
        """
        Get problem list using alternative REST API.
        """
        # Use the problemset/all API endpoint
        url = "https://leetcode.com/api/problems/all/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Referer': 'https://leetcode.com/problemset/all/',
        }
        
        response = requests.get(url, headers=headers)
        print(f"REST API Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if 'stat_status_pairs' in data:
                problems = []
                
                for problem in data['stat_status_pairs']:
                    if 'stat' in problem and 'question__title_slug' in problem['stat']:
                        problems.append({
                            'questionId': str(problem['stat']['question_id']),
                            'questionFrontendId': str(problem['stat']['frontend_question_id']),
                            'title': problem['stat']['question__title'],
                            'titleSlug': problem['stat']['question__title_slug'],
                            'difficulty': ['Easy', 'Medium', 'Hard'][problem['difficulty']['level'] - 1]
                        })
                
                # Sort problems by ID
                problems.sort(key=lambda p: int(p['questionFrontendId']))
                
                # Save to cache
                cache_file = os.path.join(self.cache_dir, "problem_list.json")
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(problems, f)
                
                print(f"Retrieved {len(problems)} problems via REST API")
                return problems[:limit]
        
        return []
    
    def _get_problems_via_scraping(self, limit: int) -> List[Dict[str, Any]]:
        """
        Get problem list by scraping the website.
        """
        url = "https://leetcode.com/problemset/all/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
        }
        
        response = requests.get(url, headers=headers)
        print(f"Web Scraping Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            script_tags = soup.find_all('script')
            
            # Look for the script tag containing problem data
            problems = []
            for script in script_tags:
                text = script.get_text()
                if 'problemsetQuestionList' in text:
                    # Extract JSON data
                    match = re.search(r'{"problemsetQuestionList":.*?}]}', text)
                    if match:
                        try:
                            json_data = json.loads(match.group(0))
                            if 'problemsetQuestionList' in json_data and 'questions' in json_data['problemsetQuestionList']:
                                questions = json_data['problemsetQuestionList']['questions']
                                
                                # Format problem data
                                for question in questions:
                                    if 'questionFrontendId' in question and 'titleSlug' in question:
                                        problems.append({
                                            'questionId': question.get('questionId', ''),
                                            'questionFrontendId': question['questionFrontendId'],
                                            'title': question.get('title', ''),
                                            'titleSlug': question['titleSlug'],
                                            'difficulty': question.get('difficulty', '')
                                        })
                                
                                # Sort problems by ID
                                problems.sort(key=lambda p: int(p['questionFrontendId']) if p['questionFrontendId'].isdigit() else 9999)
                                
                                # Save to cache
                                cache_file = os.path.join(self.cache_dir, "problem_list.json")
                                with open(cache_file, 'w', encoding='utf-8') as f:
                                    json.dump(problems, f)
                                
                                print(f"Retrieved {len(problems)} problems via web scraping")
                                return problems[:limit]
                        except Exception as e:
                            print(f"Error parsing JSON from script tag: {e}")
        
        return []
    
    def _get_static_problem_list(self, limit: int) -> List[Dict[str, Any]]:
        """
        Return a static list of popular LeetCode problems as a fallback.
        """
        # Static list of popular LeetCode problems
        static_problems = [
            {"questionId": "1", "questionFrontendId": "1", "title": "Two Sum", "titleSlug": "two-sum", "difficulty": "Easy"},
            {"questionId": "2", "questionFrontendId": "2", "title": "Add Two Numbers", "titleSlug": "add-two-numbers", "difficulty": "Medium"},
            {"questionId": "3", "questionFrontendId": "3", "title": "Longest Substring Without Repeating Characters", "titleSlug": "longest-substring-without-repeating-characters", "difficulty": "Medium"},
            {"questionId": "4", "questionFrontendId": "4", "title": "Median of Two Sorted Arrays", "titleSlug": "median-of-two-sorted-arrays", "difficulty": "Hard"},
            {"questionId": "5", "questionFrontendId": "5", "title": "Longest Palindromic Substring", "titleSlug": "longest-palindromic-substring", "difficulty": "Medium"},
            {"questionId": "15", "questionFrontendId": "15", "title": "3Sum", "titleSlug": "3sum", "difficulty": "Medium"},
            {"questionId": "20", "questionFrontendId": "20", "title": "Valid Parentheses", "titleSlug": "valid-parentheses", "difficulty": "Easy"},
            {"questionId": "21", "questionFrontendId": "21", "title": "Merge Two Sorted Lists", "titleSlug": "merge-two-sorted-lists", "difficulty": "Easy"},
            {"questionId": "23", "questionFrontendId": "23", "title": "Merge k Sorted Lists", "titleSlug": "merge-k-sorted-lists", "difficulty": "Hard"},
            {"questionId": "42", "questionFrontendId": "42", "title": "Trapping Rain Water", "titleSlug": "trapping-rain-water", "difficulty": "Hard"},
            {"questionId": "53", "questionFrontendId": "53", "title": "Maximum Subarray", "titleSlug": "maximum-subarray", "difficulty": "Easy"},
            {"questionId": "70", "questionFrontendId": "70", "title": "Climbing Stairs", "titleSlug": "climbing-stairs", "difficulty": "Easy"},
            {"questionId": "101", "questionFrontendId": "101", "title": "Symmetric Tree", "titleSlug": "symmetric-tree", "difficulty": "Easy"},
            {"questionId": "121", "questionFrontendId": "121", "title": "Best Time to Buy and Sell Stock", "titleSlug": "best-time-to-buy-and-sell-stock", "difficulty": "Easy"},
            {"questionId": "141", "questionFrontendId": "141", "title": "Linked List Cycle", "titleSlug": "linked-list-cycle", "difficulty": "Easy"},
            {"questionId": "146", "questionFrontendId": "146", "title": "LRU Cache", "titleSlug": "lru-cache", "difficulty": "Medium"},
            {"questionId": "200", "questionFrontendId": "200", "title": "Number of Islands", "titleSlug": "number-of-islands", "difficulty": "Medium"},
            {"questionId": "206", "questionFrontendId": "206", "title": "Reverse Linked List", "titleSlug": "reverse-linked-list", "difficulty": "Easy"},
            {"questionId": "217", "questionFrontendId": "217", "title": "Contains Duplicate", "titleSlug": "contains-duplicate", "difficulty": "Easy"},
            {"questionId": "238", "questionFrontendId": "238", "title": "Product of Array Except Self", "titleSlug": "product-of-array-except-self", "difficulty": "Medium"}
        ]
        
        print(f"Using static problem list with {len(static_problems)} problems as a fallback")
        
        # Save to cache
        cache_file = os.path.join(self.cache_dir, "problem_list.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(static_problems, f)
        
        return static_problems[:limit]
    
    def get_problem_by_slug(self, slug: str) -> Dict[str, Any]:
        """
        Get problem details by its slug.
        
        Args:
            slug: The unique identifier in the problem URL, e.g., "two-sum"
        
        Returns:
            Dictionary containing problem details
        """
        # Check cache
        cache_file = os.path.join(self.cache_dir, f"{slug}.json")
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # First try: GraphQL API
        try:
            data = self._get_problem_via_graphql(slug)
            if data:
                # Save to cache
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return data
        except Exception as e:
            print(f"GraphQL API approach failed for problem {slug}: {e}")
            print("Trying alternative approach...")
        
        # Second try: Direct HTML scraping
        try:
            data = self._get_problem_via_scraping(slug)
            if data:
                # Save to cache
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return data
        except Exception as e:
            print(f"Web scraping approach failed for problem {slug}: {e}")
        
        # If we get here, both approaches failed
        raise Exception(f"Unable to retrieve problem: {slug}")
    
    def _get_problem_via_graphql(self, slug: str) -> Dict[str, Any]:
        """
        Get problem details using GraphQL API.
        """
        # Build GraphQL query to get more comprehensive problem data
        query = """
        query questionData($titleSlug: String!) {
            question(titleSlug: $titleSlug) {
                questionId
                questionFrontendId
                title
                content
                difficulty
                exampleTestcases
                exampleTestcaseList
                sampleTestCase
                metaData
                codeSnippets {
                    lang
                    langSlug
                    code
                }
                hints
            }
        }
        """
        
        # Add headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Content-Type': 'application/json',
            'Referer': f'https://leetcode.com/problems/{slug}/',
            'Origin': 'https://leetcode.com'
        }
        
        # Send request
        response = requests.post(
            self.api_url,
            json={'query': query, 'variables': {'titleSlug': slug}},
            headers=headers,
            timeout=10
        )
        
        print(f"GraphQL API Status Code for {slug}: {response.status_code}")
        
        data = response.json()
        
        # Debug output
        if 'errors' in data:
            print(f"GraphQL API Errors for {slug}: {data['errors']}")
            return None
        
        if 'data' in data and data['data']['question']:
            return data['data']['question']
        
        return None
    
    def _get_problem_via_scraping(self, slug: str) -> Dict[str, Any]:
        """
        Get problem details by scraping the problem page directly.
        """
        url = f"{self.base_url}{slug}/"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Web Scraping Status Code for {slug}: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract problem ID and title
            title_elem = soup.find('title')
            title = title_elem.text.split(' - ')[0] if title_elem else slug.replace('-', ' ').title()
            
            # Find question ID from the title (not always reliable)
            question_id = ''
            question_frontend_id = ''
            match = re.search(r'\d+\.\s+', title)
            if match:
                question_frontend_id = match.group(0).strip('. ')
                question_id = question_frontend_id  # Approximation
            
            # Try to extract difficulty
            difficulty = ''
            difficulty_elem = soup.find('div', string=lambda t: t and t in ['Easy', 'Medium', 'Hard'])
            if difficulty_elem:
                difficulty = difficulty_elem.text
            
            # Try to get problem content
            content = ''
            problem_div = soup.find('div', {'class': 'question-content'}) or soup.find('div', {'class': 'content__1Y2H'})
            if problem_div:
                content = str(problem_div)
            else:
                # Fallback: get everything in the main content area
                main_content = soup.find('div', {'id': 'app'}) or soup.find('main')
                if main_content:
                    content = str(main_content)
            
            # Try to find code snippets
            code_snippets = []
            script_tags = soup.find_all('script')
            for script in script_tags:
                text = script.get_text()
                if '"codeSnippets":' in text:
                    snippets_match = re.search(r'"codeSnippets":\s*(\[.*?\])', text, re.DOTALL)
                    if snippets_match:
                        try:
                            snippets_json = snippets_match.group(1)
                            # Clean up potential JS syntax that's not valid JSON
                            snippets_json = re.sub(r',\s*}', '}', snippets_json)
                            snippets_json = re.sub(r',\s*]', ']', snippets_json)
                            code_snippets = json.loads(snippets_json)
                        except json.JSONDecodeError:
                            pass
            
            # Get example test cases - improve extraction of input/output examples
            example_testcases = []
            example_inputs = []
            example_outputs = []
            
            # Try to find input/output examples with improved parsing
            example_sections = soup.find_all('div', {'class': 'example'}) or soup.find_all('pre')
            
            for section in example_sections:
                text = section.get_text().strip()
                # More robust extraction for input parts
                input_match = re.search(r'Input:\s*(.*?)(?=Output:)', text, re.DOTALL)
                if input_match:
                    input_text = input_match.group(1).strip()
                    example_inputs.append(input_text)
                
                # More robust extraction for output parts
                output_match = re.search(r'Output:\s*(.*?)(?=Explanation:|$)', text, re.DOTALL)
                if output_match:
                    example_outputs.append(output_match.group(1).strip())
                
                # Save complete example
                example_testcases.append(text)
            
            # Better parsing of example cases from description text
            if not example_inputs or not example_outputs:
                description_text = soup.get_text()
                example_blocks = re.finditer(r'Example\s+\d+:.*?Input:\s*(.*?)Output:\s*(.*?)(?=Example\s+\d+:|Constraints:|$)', 
                                       description_text, re.DOTALL)
                
                for match in example_blocks:
                    input_text = match.group(1).strip()
                    output_text = match.group(2).strip()
                    example_inputs.append(input_text)
                    example_outputs.append(output_text)
            
            # Construct problem data
            problem_data = {
                'questionId': question_id,
                'questionFrontendId': question_frontend_id,
                'title': title,
                'content': content,
                'difficulty': difficulty,
                'exampleTestcases': '\n'.join(example_testcases),
                'codeSnippets': code_snippets,
                'structuredExamples': {
                    'inputs': example_inputs,
                    'outputs': example_outputs
                }
            }
            
            return problem_data
        
        return None
    
    def format_problem(self, problem_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format problem data into a more usable structure.
        
        Args:
            problem_data: Raw problem data from API
            
        Returns:
            Formatted problem data
        """
        # Clean HTML content
        soup = BeautifulSoup(problem_data['content'], 'html.parser')
        description = soup.get_text()
        
        # Get Python code snippet
        python_snippet = next(
            (s['code'] for s in problem_data['codeSnippets'] if s['langSlug'] == 'python3'),
            None
        )
        
        # Extract problem metadata to help analyze test case format
        meta_data = {}
        if 'metaData' in problem_data and problem_data['metaData']:
            try:
                meta_data = json.loads(problem_data['metaData'])
            except:
                pass
        
        # Precisely parse test cases
        structured_test_cases = self.parse_test_cases(
            description,
            problem_data.get('exampleTestcases', '').split('\n'),
            meta_data,
            problem_data.get('structuredExamples', {})
        )
        
        return {
            'id': problem_data['questionId'],
            'frontend_id': problem_data.get('questionFrontendId', ''),
            'title': problem_data['title'],
            'description': description,
            'difficulty': problem_data['difficulty'],
            'examples': problem_data['exampleTestcases'].split('\n'),
            'structured_test_cases': structured_test_cases,
            'python_starter': python_snippet,
            'hints': problem_data.get('hints', []),
            'meta_data': meta_data
        }
    
    def parse_test_cases(self, description: str, examples: List[str], meta_data: Dict[str, Any], 
                        structured_examples: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """
        Parse test cases, extract input parameters and expected output
        
        Args:
            description: Problem description
            examples: Original example list
            meta_data: Problem metadata
            structured_examples: Already structured examples (if available)
            
        Returns:
            List of test cases, each containing input parameters and expected output
        """
        test_cases = []
        
        # Extract examples from problem description more accurately
        example_pattern = r'Example\s+\d+:\s*\n+Input:\s*(.*?)\n+Output:\s*(.*?)(?:\n+Explanation:|$)'
        example_matches = re.finditer(example_pattern, description, re.DOTALL)
        
        # If structured examples are available
        if structured_examples and 'inputs' in structured_examples and 'outputs' in structured_examples:
            inputs = structured_examples['inputs']
            outputs = structured_examples['outputs']
            
            # Better processing of structured examples
            for i in range(min(len(inputs), len(outputs))):
                # Fix the issue of incomplete input parsing
                input_text = inputs[i]
                
                # Better extraction of parameters from input text
                param_dict = {}
                param_names = self.get_param_names_from_meta(meta_data)
                
                # For linked list cases, properly parse l1, l2, etc.
                if 'l1 =' in input_text or 'l1=' in input_text or 'l1 = ' in input_text:
                    # Extract l1, l2, etc. parameters with proper bracket content
                    list_params = re.findall(r'(l\d+)\s*=\s*(\[.*?\])', input_text, re.DOTALL)
                    if list_params:
                        for param_name, param_value in list_params:
                            param_dict[param_name] = param_value
                else:
                    # Try to match parameter patterns for different formats
                    # Check for comma-separated parameters with equals
                    param_matches = re.findall(r'(\w+)\s*=\s*([^,]+)(?:,|$)', input_text)
                    if param_matches:
                        for param_name, param_value in param_matches:
                            param_dict[param_name] = param_value.strip()
                    else:
                        # Try to identify parameters based on format and metadata
                        if meta_data and param_names:
                            # Extract values that might be inside brackets
                            list_values = re.findall(r'\[(.*?)\]', input_text)
                            single_values = re.findall(r'(?<!\[)([-+]?\d+|"[^"]*")(?!\])', input_text)
                            
                            if len(list_values) == len(param_names):
                                for i, name in enumerate(param_names):
                                    param_dict[name] = f"[{list_values[i]}]"
                            elif len(single_values) == len(param_names):
                                for i, name in enumerate(param_names):
                                    param_dict[name] = single_values[i]
                            else:
                                # If both approaches fail, use the default parsing
                                param_dict = self.parse_input_params(input_text, meta_data)
                        else:
                            # Fallback to default parsing
                            param_dict = self.parse_input_params(input_text, meta_data)
                
                if not param_dict:
                    # If no parameters were extracted, try the default method
                    param_dict = self.parse_input_params(input_text, meta_data)
                
                test_cases.append({
                    'input': param_dict,
                    'expected': self.clean_output(outputs[i])
                })
            
            if test_cases:
                return test_cases
        
        # If the above method didn't produce results, try extracting from regex matches
        for match in example_matches:
            input_text = match.group(1).strip()
            output_text = match.group(2).strip()
            
            test_cases.append({
                'input': self.parse_input_params(input_text, meta_data),
                'expected': self.clean_output(output_text)
            })
        
        # If still no test cases, try extracting examples according to rules
        if not test_cases and examples:
            param_count = self.get_param_count_from_meta(meta_data)
            
            # If parameter count is known, organize test cases
            if param_count > 0:
                for i in range(0, len(examples), param_count + 1):
                    if i + param_count < len(examples):
                        inputs = examples[i:i+param_count]
                        expected = examples[i+param_count]
                        
                        test_cases.append({
                            'input': self.format_inputs(inputs, meta_data),
                            'expected': self.clean_output(expected)
                        })
        
        return test_cases
    
    def parse_input_params(self, input_text: str, meta_data: Dict[str, Any]) -> Dict[str, str]:
        """Parse input parameter text into dictionary more robustly"""
        # Better handling of newlines and spaces
        input_text = input_text.replace('\n', ' ').strip()
        
        # Improved parameter extraction
        params = {}
        
        # Enhanced pattern matching for parameters
        # Check if there's a named parameter format (param=value)
        param_pattern = r'(\w+)\s*=\s*(\[[^\]]*\]|\{[^\}]*\}|"[^"]*"|-?\d+|\w+)'
        param_matches = re.findall(param_pattern, input_text)
        
        if param_matches:
            for param_name, param_value in param_matches:
                params[param_name] = param_value.strip()
            return params
        
        # Try to get parameter names from metadata
        param_names = self.get_param_names_from_meta(meta_data)
        
        # Handle arrays properly by finding complete bracket contents
        if '[' in input_text:
            array_matches = re.findall(r'\[(.*?)\]', input_text)
            if array_matches:
                if param_names and len(param_names) == len(array_matches):
                    return {param_names[i]: f"[{array_match}]" for i, array_match in enumerate(array_matches)}
                else:
                    return {f"param{i}": f"[{array_match}]" for i, array_match in enumerate(array_matches)}
        
        # If input format is comma-separated values without brackets
        if ',' in input_text and '[' not in input_text:
            values = input_text.split(',')
            values = [v.strip() for v in values]
            if param_names and len(param_names) == len(values):
                return {param_names[i]: values[i] for i in range(len(values))}
            else:
                return {f"param{i}": value for i, value in enumerate(values)}
        
        # Single parameter case
        if param_names and len(param_names) > 0:
            return {param_names[0]: input_text.strip()}
        else:
            return {"param0": input_text.strip()}
    
    def format_inputs(self, inputs: List[str], meta_data: Dict[str, Any]) -> Dict[str, str]:
        """Format input parameter list as dictionary"""
        param_names = self.get_param_names_from_meta(meta_data)
        
        if param_names and len(param_names) == len(inputs):
            return {param_names[i]: inputs[i].strip().replace('"', '') for i in range(len(inputs))}
        else:
            # Use default parameter names
            return {f"param{i}": input.strip().replace('"', '') for i, input in enumerate(inputs)}
    
    def get_param_names_from_meta(self, meta_data: Dict[str, Any]) -> List[str]:
        """Get parameter names from metadata"""
        if 'params' in meta_data:
            try:
                params = json.loads(meta_data['params'])
                return [p.get('name', f"param{i}") for i, p in enumerate(params)]
            except:
                pass
        return []
    
    def get_param_count_from_meta(self, meta_data: Dict[str, Any]) -> int:
        """Get parameter count from metadata"""
        if 'params' in meta_data:
            try:
                params = json.loads(meta_data['params'])
                return len(params)
            except:
                pass
        return 0
    
    def clean_output(self, output: str) -> str:
        """
        Clean output text and ensure it doesn't have problematic characters or additional content.
        
        Args:
            output: Raw output string
            
        Returns:
            Cleaned output string
        """
        # Remove quotes, newlines and other problematic characters
        # Also extract just the first part if there's additional content
        if "\n" in output:
            # Only take the first line of output if it contains newlines
            output = output.split("\n")[0].strip()
        
        # Handle common output patterns
        if output.startswith("[") and "]" in output:
            # Extract just the array part if present
            output = output[:output.find("]")+1]
        
        # Remove any remaining quotes
        cleaned = output.strip().replace('"', '')
        return cleaned

    def get_formatted_problem(self, slug: str) -> Dict[str, Any]:
        """
        Get and format problem data.
        
        Args:
            slug: Problem slug
            
        Returns:
            Formatted problem data
        """
        raw_data = self.get_problem_by_slug(slug)
        return self.format_problem(raw_data)
    
    def batch_download_problems(self, limit: int = 1000) -> Dict[str, Dict[str, Any]]:
        """
        Download multiple problems from LeetCode.
        
        Args:
            limit: Maximum number of problems to download
            
        Returns:
            Dictionary mapping problem slugs to problem data
        """
        problems = {}
        problem_list = self.get_problem_list(limit)
        
        print(f"Downloading {len(problem_list)} problems...")
        
        for i, problem_info in enumerate(problem_list):
            slug = problem_info['titleSlug']
            problem_id = problem_info['questionFrontendId']
            
            # Skip if we already have this problem cached
            cache_file = os.path.join(self.cache_dir, f"{slug}.json")
            if os.path.exists(cache_file):
                print(f"Using cached problem {problem_id}: {problem_info['title']} ({i+1}/{len(problem_list)})")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    problem_data = json.load(f)
                formatted_problem = self.format_problem(problem_data)
                problems[slug] = formatted_problem
                continue
            
            # Try to download with retries
            max_retries = 3
            for retry in range(max_retries):
                try:
                    print(f"Downloading problem {problem_id}: {problem_info['title']} ({i+1}/{len(problem_list)}) - Attempt {retry+1}/{max_retries}")
                    problem_data = self.get_formatted_problem(slug)
                    problems[slug] = problem_data
                    
                    # Success - break retry loop
                    break
                except Exception as e:
                    print(f"Error downloading problem {slug} (Attempt {retry+1}/{max_retries}): {e}")
                    if retry < max_retries - 1:
                        # Exponential backoff: 2, 4, 8 seconds...
                        wait_time = 2 ** (retry + 1)
                        print(f"Waiting {wait_time} seconds before retrying...")
                        time.sleep(wait_time)
                    else:
                        print(f"Failed to download problem {slug} after {max_retries} attempts")
            
            # Sleep between requests to avoid rate limiting
            # Use a variable delay based on position to avoid detection patterns
            if i < len(problem_list) - 1:
                sleep_time = 2 + (i % 3)  # Varies between 2-4 seconds
                print(f"Waiting {sleep_time} seconds before next request...")
                time.sleep(sleep_time)
        
        print(f"Downloaded {len(problems)} problems successfully")
        return problems


class SolutionGeneratorSignature(dspy.Signature):
    """DSPy signature for generating LeetCode solutions."""
    problem_description: str = dspy.InputField(desc="Description of the LeetCode problem, including input/output requirements")
    problem_examples: str = dspy.InputField(desc="Example inputs and expected outputs for the problem")
    function_signature: str = dspy.InputField(desc="Function signature to implement")
    solution_code: str = dspy.OutputField(desc="Complete Python solution code, including function implementation and comments")
    explanation: str = dspy.OutputField(desc="Detailed explanation of the solution, including time and space complexity analysis")


class SolutionGenerator(dspy.Module):
    """
    Uses DSPy and GPT-4o-mini to generate solutions for LeetCode problems.
    """
    
    def __init__(self, llm):
        """
        Initialize the solution generator.
        
        Args:
            llm: DSPy language model instance
        """
        self.generator = dspy.ChainOfThought(SolutionGeneratorSignature)
    
    def clean_code(self, code: str) -> str:
        """
        Clean the generated code by removing markdown code block markers.
        
        Args:
            code: Raw generated code
            
        Returns:
            Cleaned code
        """
        # Remove markdown code block markers
        code = re.sub(r'```python\n?', '', code)
        code = re.sub(r'```\n?', '', code)
        return code.strip()
    
    def generate_solution(self, 
                          problem: Dict[str, Any], 
                          max_retries: int = 3) -> Dict[str, str]:
        """
        Generate a solution for a LeetCode problem.
        
        Args:
            problem: Formatted problem data
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary containing solution code and explanation
        """
        # Build description
        description = f"# {problem['title']}\n\n{problem['description']}"
        
        # Build examples
        examples = "\n\n# Examples:\n" + "\n".join(problem['examples'])
        
        # Get function signature
        function_signature = problem['python_starter'] or "# No function signature provided"
        
        # Try to generate solution
        for attempt in range(max_retries):
            try:
                result = self.generator(
                    problem_description=description,
                    problem_examples=examples,
                    function_signature=function_signature
                )
                
                # Clean the generated code
                cleaned_code = self.clean_code(result.solution_code)
                
                return {
                    'code': cleaned_code,
                    'explanation': result.explanation
                }
            except Exception as e:
                print(f"Error generating solution (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2)  # Wait before retrying


class TestExecutor:
    """
    Executes generated code and validates results.
    """
    
    def __init__(self, 
                 timeout: int = 10, 
                 dataset_dir: str = "leetcode_dataset", 
                 results_dir: str = "results_openai_gpt_4o_mini"):
        """
        Initialize the test executor.
        
        Args:
            timeout: Maximum time to execute a single test (seconds)
            dataset_dir: Dataset directory path
            results_dir: Results folder path
        """
        self.timeout = timeout
        self.dataset_dir = dataset_dir
        self.results_dir = results_dir
        
        # Create results directory if it doesn't exist
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
    
    def clean_output(self, output: str) -> str:
        """
        Clean output text and ensure it doesn't have problematic characters or additional content.
        
        Args:
            output: Raw output string
            
        Returns:
            Cleaned output string
        """
        # Remove quotes, newlines and other problematic characters
        # Also extract just the first part if there's additional content
        if "\n" in output:
            # Only take the first line of output if it contains newlines
            output = output.split("\n")[0].strip()
        
        # Handle common output patterns
        if output.startswith("[") and "]" in output:
            # Extract just the array part if present
            output = output[:output.find("]")+1]
        
        # Remove any remaining quotes
        cleaned = output.strip().replace('"', '')
        return cleaned
    
    def analyze_function_signature(self, code: str) -> Tuple[str, int, str]:
        """
        Analyze function signature to get method name, parameter count and class name
        
        Args:
            code: Solution code
            
        Returns:
            (method_name, param_count (excluding self), class_name)
        """
        if not code:
            return None, 0, None
        
        # Find class name
        class_match = re.search(r'class\s+(\w+)', code)
        class_name = class_match.group(1) if class_match else "Solution"
        
        # Find method definition
        method_match = re.search(r'def\s+(\w+)\s*\(([^)]*)\)', code)
        if not method_match:
            return None, 0, class_name
        
        method_name = method_match.group(1)
        params_str = method_match.group(2)
        
        # Analyze parameters
        params = [p.strip() for p in params_str.split(',') if p.strip()]
        
        # Exclude self parameter
        if params and params[0] == 'self':
            return method_name, len(params) - 1, class_name
        
        return method_name, len(params), class_name
    
    def prepare_test_code(self, solution_code: str, examples: List[str], structured_test_cases: List[Dict[str, Any]] = None) -> str:
        """
        Prepare test code with accurate validation, avoiding string parsing issues
        
        Args:
            solution_code: Solution code
            examples: Original example list
            structured_test_cases: Structured test cases
            
        Returns:
            Test code
        """
        # Analyze function signature
        method_name, param_count, class_name = self.analyze_function_signature(solution_code)
        
        if not method_name:
            raise ValueError(f"Cannot determine method name from code")
        
        # Check for special types
        needs_listnode = 'ListNode' in solution_code
        needs_treenode = 'TreeNode' in solution_code
        
        # Build test code
        test_code = "# Auto-generated LeetCode test with validation\n"
        test_code += "import json\nimport re\nimport sys\nfrom typing import List, Optional, Dict, Tuple, Any, Union\n\n"
        
        # Add solution code
        test_code += solution_code + "\n\n"
        
        # Add common data structure definitions
        if needs_listnode:
            test_code += """
# Definition for singly-linked list
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next
    
    def __str__(self):
        values = []
        current = self
        while current:
            values.append(str(current.val))
            current = current.next
        return "->".join(values)
    
    def __eq__(self, other):
        if not isinstance(other, ListNode):
            return False
        a, b = self, other
        while a and b:
            if a.val != b.val:
                return False
            a, b = a.next, b.next
        return a is None and b is None

def create_linked_list(values):
    if not values:
        return None
    head = ListNode(values[0])
    current = head
    for val in values[1:]:
        current.next = ListNode(val)
        current = current.next
    return head

def linked_list_to_list(head):
    values = []
    current = head
    while current:
        values.append(current.val)
        current = current.next
    return values
"""

        if needs_treenode:
            test_code += """
# Definition for a binary tree node
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
    
    def __eq__(self, other):
        if not isinstance(other, TreeNode):
            return False
        if self.val != other.val:
            return False
        return (self.left == other.left) and (self.right == other.right)

def create_binary_tree(values):
    if not values:
        return None
    root = TreeNode(values[0])
    queue = [root]
    i = 1
    while queue and i < len(values):
        node = queue.pop(0)
        if i < len(values) and values[i] is not None:
            node.left = TreeNode(values[i])
            queue.append(node.left)
        i += 1
        if i < len(values) and values[i] is not None:
            node.right = TreeNode(values[i])
            queue.append(node.right)
        i += 1
    return root

def binary_tree_to_list(root):
    if not root:
        return []
    result = []
    queue = [root]
    while queue:
        node = queue.pop(0)
        if node:
            result.append(node.val)
            queue.append(node.left)
            queue.append(node.right)
        else:
            result.append(None)
    # Remove trailing None values
    while result and result[-1] is None:
        result.pop()
    return result
"""

        # Add utility function for comparing results
        test_code += """
def compare_results(actual, expected):
    # Compare actual results with expected results in a direct manner
    # Convert expected value to appropriate type if needed
    if isinstance(expected, str):
        # Handle common numeric strings
        if expected.isdigit() or (expected.startswith('-') and expected[1:].isdigit()):
            expected = int(expected)
        elif expected.lower() == 'true':
            expected = True
        elif expected.lower() == 'false':
            expected = False
            
    # Handle lists comparison
    if isinstance(actual, list) and isinstance(expected, list):
        return actual == expected
    # Handle simple types
    return actual == expected
"""

        # Create solution instance and initialize test result tracking
        test_code += "# Create solution instance\n"
        test_code += f"solution = {class_name}()\n\n"
        test_code += "# Test results\n"
        test_code += "all_tests_passed = True\n"

        # If structured test cases are available, use them for precise testing
        if structured_test_cases:
            test_code += f"\n# Using structured test cases\n"
            
            for i, test_case in enumerate(structured_test_cases):
                test_code += f"\nprint('Test case {i+1}:')\n"
                test_code += f"try:\n"
                
                # Process input parameters
                inputs = test_case['input']
                expected_output = test_case['expected']
                
                # Clean expected output before using it
                expected_output = self.clean_output(expected_output)
                
                # Prepare input parameters more safely
                input_vars = []
                for j, (key, value) in enumerate(inputs.items()):
                    var_name = f"input_{i}_{j}"
                    input_vars.append(var_name)
                    
                    # Directly parse value without using eval
                    if value.startswith('[') and value.endswith(']'):
                        # Handle list input
                        try:
                            # Clean up the input to handle lists properly
                            clean_value = value.replace('\\n', '').replace('\\r', '')
                            test_code += f"    {var_name} = {clean_value}\n"
                        except:
                            test_code += f"    # Failed to parse list, using raw value\n"
                            test_code += f"    {var_name} = {repr(value)}\n"
                    elif value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                        # Handle integer
                        test_code += f"    {var_name} = {value}\n"
                    elif value.lower() in ('true', 'false'):
                        # Handle boolean
                        test_code += f"    {var_name} = {value.lower()}\n"
                    else:
                        # String or other
                        test_code += f"    {var_name} = {repr(value)}\n"
                    
                    # Handle special data types
                    if needs_listnode and j < param_count:
                        test_code += f"    if isinstance({var_name}, list):\n"
                        test_code += f"        {var_name} = create_linked_list({var_name})\n"
                    elif needs_treenode and j < param_count:
                        test_code += f"    if isinstance({var_name}, list):\n"
                        test_code += f"        {var_name} = create_binary_tree({var_name})\n"
                
                # Call method
                test_code += f"    result_{i} = solution.{method_name}({', '.join(input_vars)})\n"
                
                # Process result
                if needs_listnode:
                    test_code += f"    if isinstance(result_{i}, ListNode):\n"
                    test_code += f"        result_{i} = linked_list_to_list(result_{i})\n"
                elif needs_treenode:
                    test_code += f"    if isinstance(result_{i}, TreeNode):\n"
                    test_code += f"        result_{i} = binary_tree_to_list(result_{i})\n"
                
                # Prepare expected output more carefully
                if expected_output.isdigit() or (expected_output.startswith('-') and expected_output[1:].isdigit()):
                    # Simple integer
                    test_code += f"    expected_{i} = {expected_output}\n"
                elif expected_output.startswith('[') and expected_output.endswith(']'):
                    # List
                    try:
                        # Clean up the expected output
                        clean_expected = expected_output.replace('\\n', '').replace('\\r', '')
                        test_code += f"    expected_{i} = {clean_expected}\n"
                    except:
                        test_code += f"    # Failed to parse expected list\n"
                        test_code += f"    expected_{i} = {repr(expected_output)}\n"
                else:
                    # String or other
                    test_code += f"    expected_{i} = {repr(expected_output)}\n"
                
                # Simple comparison with appropriate message
                test_code += f"    if compare_results(result_{i}, expected_{i}):\n"
                test_code += f"        print(f'[PASS] Test passed: {{result_{i}}}')\n"
                test_code += f"    else:\n"
                test_code += f"        all_tests_passed = False\n"
                test_code += f"        print(f'[FAIL] Test failed!')\n"
                test_code += f"        print(f'  Expected: {{expected_{i}}}')\n"
                test_code += f"        print(f'  Got: {{result_{i}}}')\n"
                
                # Exception handling
                test_code += f"except Exception as e:\n"
                test_code += f"    all_tests_passed = False\n"
                test_code += f"    print(f'[ERROR] Error: {{e}}')\n"
        
        # If no structured test cases, use original examples more carefully
        else:
            # Basic execution to check if code runs
            for i, example in enumerate(examples):
                test_code += f"\n# Test example {i+1}\n"
                
                # Process input parameters and expected output
                try:
                    # Parse inputs
                    inputs = []
                    for j in range(param_count):
                        if i*param_count + j < len(examples):
                            inputs.append(f"safe_eval('{examples[i*param_count + j]}')")
                        else:
                            break
                    
                    # Expected output
                    expected = f"safe_eval('{examples[i*param_count + param_count]}')" if i*param_count + param_count < len(examples) else None
                    
                    if len(inputs) == param_count and expected:
                        test_code += f"print('Test example {i+1}:')\n"
                        
                        # Build input parameters
                        input_vars = []
                        for j, input_expr in enumerate(inputs):
                            input_vars.append(f"input_{i}_{j}")
                            test_code += f"{input_vars[-1]} = {input_expr}\n"
                        
                        # Handle special data types
                        if param_count == 1:
                            if needs_listnode:
                                test_code += f"if isinstance({input_vars[0]}, list):\n"
                                test_code += f"    {input_vars[0]} = create_linked_list({input_vars[0]})\n"
                            elif needs_treenode:
                                test_code += f"if isinstance({input_vars[0]}, list):\n"
                                test_code += f"    {input_vars[0]} = create_binary_tree({input_vars[0]})\n"
                        
                        # Call method
                        call_expr = f"solution.{method_name}({', '.join(input_vars)})"
                        test_code += f"result_{i} = {call_expr}\n"
                        
                        # Process result
                        if needs_listnode:
                            test_code += f"if isinstance(result_{i}, ListNode):\n"
                            test_code += f"    result_{i} = linked_list_to_list(result_{i})\n"
                        elif needs_treenode:
                            test_code += f"if isinstance(result_{i}, TreeNode):\n"
                            test_code += f"    result_{i} = binary_tree_to_list(result_{i})\n"
                        
                        # Validate result - Using ASCII symbols instead of Unicode
                        test_code += f"expected_{i} = {expected}\n"
                        test_code += f"if compare_results(result_{i}, expected_{i}):\n"
                        test_code += f"    print(f'[PASS] Test passed: {{result_{i}}}')\n"
                        test_code += f"else:\n"
                        test_code += f"    all_tests_passed = False\n"
                        test_code += f"    print(f'[FAIL] Test failed!')\n"
                        test_code += f"    print(f'  Expected: {{expected_{i}}}')\n"
                        test_code += f"    print(f'  Got: {{result_{i}}}')\n"
                except Exception as e:
                    test_code += f"# Error processing example: {str(e)}\n\n"
        
        # Add final result output
        test_code += "\n# Output final result\n"
        test_code += "if all_tests_passed:\n"
        test_code += "    print('\\n[PASS] All tests passed!')\n"
        test_code += "    sys.exit(0)\n"
        test_code += "else:\n"
        test_code += "    print('\\n[FAIL] Some tests failed!')\n"
        test_code += "    sys.exit(1)\n"
        
        return test_code
    
    def execute_test(self, test_code: str) -> Tuple[bool, str]:
        """
        Execute test code
        
        Args:
            test_code: Test code
            
        Returns:
            (success flag, output log)
        """
        # Create temporary file to store test code
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            f.write(test_code.encode('utf-8'))
            temp_filename = f.name
        
        try:
            # Execute test code
            result = subprocess.run(
                ['python', temp_filename],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # Check execution result
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"Execution error:\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return False, f"Execution timeout (>{self.timeout} seconds)"
        except Exception as e:
            return False, f"Execution exception: {str(e)}"
        finally:
            # Delete temporary file
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)
    
    def test_result_file(self, result_file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Test solution in result file
        
        Args:
            result_file_path: Result file path
            
        Returns:
            (success flag, updated result data)
        """
        try:
            # Read result file
            with open(result_file_path, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
            
            # Check file format
            if not all(key in result_data for key in ['problem', 'solution', 'test_result']):
                print(f"Invalid result file format: {result_file_path}")
                return False, result_data
            
            # Get solution code
            solution_code = result_data['solution']['code']
            
            # Get problem examples
            examples = result_data['problem']['examples']
            
            # Get structured test cases
            structured_test_cases = result_data['problem'].get('structured_test_cases', None)
            
            # Prepare test code
            test_code = self.prepare_test_code(solution_code, examples, structured_test_cases)
            
            # Execute test
            success, output = self.execute_test(test_code)
            
            # Update test result
            result_data['test_result'] = {
                'success': success,
                'output': output,
                'retested': True,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Save updated result
            with open(result_file_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            return success, result_data
        except Exception as e:
            print(f"Error testing result file {result_file_path}: {e}")
            return False, {'error': str(e)}
    
    def test_multiple_problems(self, file_pattern: str = None, max_attempts: int = 2) -> Dict[str, Any]:
        """
        Test multiple problems with retry mechanism
        
        Args:
            file_pattern: File match pattern (e.g. "00*.json")
            max_attempts: Maximum attempts per problem
            
        Returns:
            Summary of test results
        """
        # Determine files to test
        if file_pattern:
            result_files = glob.glob(os.path.join(self.results_dir, file_pattern))
        else:
            result_files = glob.glob(os.path.join(self.results_dir, "*.json"))
        
        # Exclude summary and metrics files
        result_files = [f for f in result_files if not os.path.basename(f).startswith('summary_') 
                        and not os.path.basename(f).startswith('metrics_')
                        and not os.path.basename(f).startswith('retest_')]
        
        if not result_files:
            print(f"No matching result files found")
            return {"error": "No matching result files found"}
        
        # Sort files by problem ID
        result_files.sort(key=lambda f: os.path.basename(f))
        
        results = {}
        summary = {
            'total': len(result_files),
            'success': 0,
            'failed': 0,
            'error': 0,
            'success_rate': 0.0,
            'model': os.path.basename(self.results_dir),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"Starting batch test of {len(result_files)} problems...")
        
        for idx, file_path in enumerate(result_files):
            file_name = os.path.basename(file_path)
            problem_id = file_name.split('_')[0]
            problem_slug = file_name.replace('.json', '').split('_', 1)[1] if '_' in file_name else file_name
            
            print(f"[{idx+1}/{len(result_files)}] Testing problem {problem_id}: {problem_slug}")
            
            success = False
            result = None
            
            # Try testing up to max_attempts times
            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        print(f"  Retrying problem {problem_slug} (attempt {attempt+1}/{max_attempts})")
                    
                    success, result = self.test_result_file(file_path)
                    
                    if success:
                        print(f"  Successfully tested problem {problem_slug}")
                        break
                    else:
                        if isinstance(result, dict) and 'error' in result:
                            print(f"  Error: {result['error']}")
                        else:
                            print(f"  Failed to test problem {problem_slug}")
                except Exception as e:
                    print(f"  Error processing problem {problem_slug} (attempt {attempt+1}): {e}")
                    result = {'error': str(e)}
            
            # Record final result
            results[problem_slug] = {
                'success': success,
                'problem_id': problem_id,
                'error': result.get('error', None) if isinstance(result, dict) else None
            }
            
            # Update summary
            if success:
                summary['success'] += 1
            elif result and isinstance(result, dict) and 'error' in result:
                summary['error'] += 1
            else:
                summary['failed'] += 1
        
        # Calculate success rate
        if summary['total'] > 0:
            summary['success_rate'] = summary['success'] / summary['total']
        
        timestamp = int(time.time())
        
        # Save detailed summary
        summary_result = {
            'summary': summary,
            'results': results,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        summary_file = os.path.join(self.results_dir, f"summary_{timestamp}.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_result, f, ensure_ascii=False, indent=2)
        
        # Save metrics summary
        metrics = {
            'model': summary['model'],
            'total_problems': summary['total'],
            'success_count': summary['success'],
            'failed_count': summary['failed'],
            'error_count': summary['error'],
            'success_rate': summary['success_rate'],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        metrics_file = os.path.join(self.results_dir, f"metrics_{timestamp}.json")
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        
        print(f"\nTesting complete!")
        print(f"Success rate: {summary['success_rate']:.2%} ({summary['success']}/{summary['total']})")
        print(f"Failed: {summary['failed']} | Errors: {summary['error']}")
        print(f"Detailed results saved to: {summary_file}")
        print(f"Metrics summary saved to: {metrics_file}")
        
        return summary_result
    
    def run_batch_test(self, num_problems: int = None, random_seed: int = 42):
        """
        Run a batch test on dataset problems
        
        Args:
            num_problems: Number of problems to test (None = all)
            random_seed: Random seed for reproducibility
        """
        # Get all result files
        result_files = glob.glob(os.path.join(self.results_dir, "*.json"))
        
        # Exclude summary and metrics files
        result_files = [f for f in result_files if not os.path.basename(f).startswith('summary_') 
                       and not os.path.basename(f).startswith('metrics_')
                       and not os.path.basename(f).startswith('retest_')]
        
        # Extract problem slugs
        problem_slugs = []
        for file_path in result_files:
            file_name = os.path.basename(file_path)
            if '_' in file_name:
                problem_slug = file_name.replace('.json', '').split('_', 1)[1]
                problem_slugs.append(problem_slug)
        
        print(f"Found {len(problem_slugs)} problems in results folder")
        
        if len(problem_slugs) == 0:
            print("No problems found in results folder.")
            return
        
        # Select problems
        if num_problems is not None and num_problems < len(problem_slugs):
            random.seed(random_seed)
            selected_problems = random.sample(problem_slugs, num_problems)
            print(f"Randomly selected {len(selected_problems)} problems for testing")
            
            # Convert to file pattern
            pattern = '|'.join(selected_problems)
            pattern = f"*_({pattern}).json"
        else:
            selected_problems = problem_slugs
            pattern = None
            print(f"Testing all {len(selected_problems)} available problems")
        
        # Run tests
        return self.test_multiple_problems(pattern, max_attempts=2)


class LeetCodeTester:
    """
    Main class that combines all components for testing LeetCode solutions.
    """
    
    def __init__(self, api_key: str, model_name: str = "openai/gpt-4o-mini"):
        """
        Initialize the LeetCode testing system.
        
        Args:
            api_key: OpenAI API key
            model_name: Name of the model to use
        """
        # Initialize language model
        self.lm = dspy.LM(model_name, api_key=api_key)
        dspy.configure(lm=self.lm)
        
        # Set model name
        self.model_name = model_name.replace('/', '_').replace('-', '_')
        
        # Initialize components
        self.scraper = LeetCodeScraper()
        self.generator = SolutionGenerator(self.lm)
        self.executor = TestExecutor(
            results_dir=f"results_{self.model_name}",
            dataset_dir="leetcode_dataset"
        )
        
        # Create dataset directory for storing LeetCode problems
        self.dataset_dir = "leetcode_dataset"
        if not os.path.exists(self.dataset_dir):
            os.makedirs(self.dataset_dir)
        
        # Create results directory for storing test results
        self.results_dir = f"results_{self.model_name}"
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
    
    def test_problem(self, problem_slug: str) -> Dict[str, Any]:
        """
        Test a specific LeetCode problem.
        
        Args:
            problem_slug: Problem slug
            
        Returns:
            Test results and statistics
        """
        print(f"Starting to process problem: {problem_slug}")
        
        # 1. Scrape problem
        print("Retrieving problem...")
        problem = self.scraper.get_formatted_problem(problem_slug)
        
        # 2. Generate solution
        print("Generating solution...")
        solution = self.generator.generate_solution(problem)
        
        # 3. Execute tests
        print("Executing tests...")
        if 'structured_test_cases' in problem:
            test_code = self.executor.prepare_test_code(
                solution['code'], 
                problem['examples'], 
                problem['structured_test_cases']
            )
        else:
            test_code = self.executor.prepare_test_code(solution['code'], problem['examples'])
            
        success, output = self.executor.execute_test(test_code)
        
        # 4. Save results
        result = {
            'problem': problem,
            'solution': solution,
            'test_result': {
                'success': success,
                'output': output
            },
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Save results to file with problem number in filename
        result_file = os.path.join(self.results_dir, f"{problem['frontend_id'].zfill(4)}_{problem_slug}.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"Test {'successful' if success else 'failed'}, results saved to {result_file}")
        return result
    
    def test_multiple_problems(self, problem_slugs: List[str], max_attempts: int = 2) -> Dict[str, Any]:
        """
        Test multiple LeetCode problems with retry mechanism.
        
        Args:
            problem_slugs: List of problem slugs
            max_attempts: Maximum number of attempts per problem
            
        Returns:
            Summary results for all tests
        """
        results = {}
        summary = {
            'total': len(problem_slugs),
            'success': 0,
            'failed': 0,
            'error': 0,
            'success_rate': 0.0,
            'model': self.model_name,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        for idx, slug in enumerate(problem_slugs):
            print(f"\nTesting problem {idx+1}/{len(problem_slugs)}: {slug}")
            success = False
            result = None
            
            # Try solving the problem up to max_attempts times
            for attempt in range(max_attempts):
                try:
                    if attempt > 0:
                        print(f"Retrying problem {slug} (attempt {attempt+1}/{max_attempts})")
                    
                    # Test the problem
                    result = self.test_problem(slug)
                    
                    # Check if test was successful
                    if result['test_result']['success']:
                        success = True
                        print(f"Successfully solved problem {slug} on attempt {attempt+1}")
                        break
                    else:
                        print(f"Failed to solve problem {slug} on attempt {attempt+1}. Error: {result['test_result']['output']}")
                        
                except Exception as e:
                    print(f"Error processing problem {slug} (attempt {attempt+1}): {e}")
                    result = {'error': str(e)}
            
            # Record final result after all attempts
            results[slug] = result
            
            # Update summary
            if success:
                summary['success'] += 1
            elif result and 'test_result' in result:
                summary['failed'] += 1
            else:
                summary['error'] += 1
        
        # Calculate success rate
        if summary['total'] > 0:
            summary['success_rate'] = summary['success'] / summary['total']
        
        # Save detailed results
        summary_result = {
            'summary': summary,
            'results': results,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        summary_file = os.path.join(self.results_dir, f"summary_{int(time.time())}.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_result, f, ensure_ascii=False, indent=2)
        
        # Save a simplified metrics summary
        metrics = {
            'model': self.model_name,
            'total_problems': summary['total'],
            'success_count': summary['success'],
            'failed_count': summary['failed'],
            'error_count': summary['error'],
            'success_rate': summary['success_rate'],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        metrics_file = os.path.join(self.results_dir, f"metrics_{int(time.time())}.json")
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        
        print(f"\nTesting complete!")
        print(f"Success rate: {summary['success_rate']:.2%} ({summary['success']}/{summary['total']})")
        print(f"Failed: {summary['failed']} | Errors: {summary['error']}")
        print(f"Detailed results saved to: {summary_file}")
        print(f"Metrics summary saved to: {metrics_file}")
        
        return summary_result
    
    def run_batch_test(self, num_problems: int = 100, random_seed: int = 42):
        """
        Run a batch test on a random sample of downloaded problems.
        
        Args:
            num_problems: Number of problems to test
            random_seed: Random seed for reproducibility
        """
        import random
        
        print(f"Starting batch test of {num_problems} problems using {self.model_name}")
        
        # Get list of available problems
        all_problems = []
        for filename in os.listdir(self.dataset_dir):
            if filename.endswith('.json'):
                problem_slug = filename.split('_', 1)[1].rsplit('.', 1)[0]
                all_problems.append(problem_slug)
        
        print(f"Found {len(all_problems)} problems in dataset")
        
        if len(all_problems) == 0:
            print("No problems found in dataset. Please run download_problems first.")
            return
        
        # Randomly select problems
        random.seed(random_seed)
        if num_problems >= len(all_problems):
            selected_problems = all_problems
            print(f"Testing all {len(selected_problems)} available problems")
        else:
            selected_problems = random.sample(all_problems, num_problems)
            print(f"Randomly selected {len(selected_problems)} problems for testing")
        
        # Run tests
        return self.test_multiple_problems(selected_problems, max_attempts=2)
    
    def download_problems(self, limit: int = 500):
        """
        Download problems from LeetCode without testing them.
        
        Args:
            limit: Maximum number of problems to download and save
        """
        print(f"Downloading up to {limit} LeetCode problems...")
        
        # Get a larger list to account for premium problems we'll skip
        problem_list = self.scraper.get_problem_list(limit * 2)
        
        print(f"Retrieved {len(problem_list)} problems, will save up to {limit}")
        
        saved_count = 0
        skipped_count = 0
        premium_count = 0
        
        for i, problem_info in enumerate(problem_list):
            # Exit if we've saved enough problems
            if saved_count >= limit:
                print(f"Reached target of {limit} saved problems. Stopping.")
                break
                
            slug = problem_info['titleSlug']
            problem_id = problem_info['questionFrontendId']
            
            # Skip if we already have this problem cached and count it
            cache_file = os.path.join(self.scraper.cache_dir, f"{slug}.json")
            result_file = os.path.join(self.dataset_dir, f"{problem_id.zfill(4)}_{slug}.json")
            
            if os.path.exists(result_file):
                print(f"Problem already saved in dataset: {problem_id}: {problem_info['title']} ({saved_count+1}/{limit})")
                saved_count += 1
                continue
                
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        problem_data = json.load(f)
                    
                    # Check if this is a premium problem
                    if problem_data is None or 'content' not in problem_data or problem_data['content'] is None:
                        print(f"Skipping premium problem {problem_id}: {problem_info['title']}")
                        premium_count += 1
                        continue
                        
                    # Format and save the problem
                    formatted_problem = self.scraper.format_problem(problem_data)
                    
                    # Create JSON file with formatted data
                    filename = f"{problem_id.zfill(4)}_{slug}.json"
                    filepath = os.path.join(self.dataset_dir, filename)
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(formatted_problem, f, ensure_ascii=False, indent=2)
                    
                    print(f"Saved cached problem {problem_id}: {problem_info['title']} ({saved_count+1}/{limit})")
                    saved_count += 1
                    continue
                except Exception as e:
                    print(f"Error with cached problem {slug}: {e}, will try to download again")
            
            # Try to download the problem
            max_retries = 3
            success = False
            
            for retry in range(max_retries):
                try:
                    print(f"Downloading problem {problem_id}: {problem_info['title']} ({saved_count+1}/{limit}, total processed: {i+1}) - Attempt {retry+1}/{max_retries}")
                    problem_data = self.scraper.get_formatted_problem(slug)
                    
                    # Check if this looks like a premium problem
                    if not problem_data or not problem_data.get('description') or 'premium' in problem_data.get('description', '').lower():
                        print(f"Detected premium problem {problem_id}: {problem_info['title']}, skipping")
                        premium_count += 1
                        success = True  # Mark as success so we don't retry, but don't increment saved_count
                        break
                    
                    # Create JSON file with formatted data
                    filename = f"{problem_id.zfill(4)}_{slug}.json"
                    filepath = os.path.join(self.dataset_dir, filename)
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(problem_data, f, ensure_ascii=False, indent=2)
                    
                    print(f"Saved problem {problem_id}: {problem_info['title']} to {filename} ({saved_count+1}/{limit})")
                    saved_count += 1
                    success = True
                    break
                        
                except Exception as e:
                    if "NoneType' has no len" in str(e):
                        print(f"Detected premium problem {problem_id}: {problem_info['title']} (NoneType error), skipping")
                        premium_count += 1
                        success = True  # Mark as success so we don't retry
                        break
                    else:
                        print(f"Error downloading problem {slug} (Attempt {retry+1}/{max_retries}): {e}")
                        if retry < max_retries - 1:
                            # Exponential backoff: 2, 4, 8 seconds...
                            wait_time = 2 ** (retry + 1)
                            print(f"Waiting {wait_time} seconds before retrying...")
                            time.sleep(wait_time)
            
            if not success:
                print(f"Failed to download problem {slug} after {max_retries} attempts, skipping")
                skipped_count += 1
            
            # Sleep between requests to avoid rate limiting
            if i < len(problem_list) - 1 and saved_count < limit:
                sleep_time = 1
                print(f"Waiting {sleep_time} seconds before next request...")
                time.sleep(sleep_time)
        
        print(f"\nDownload summary:")
        print(f"- Saved problems: {saved_count}/{limit}")
        print(f"- Premium problems skipped: {premium_count}")
        print(f"- Other problems skipped due to errors: {skipped_count}")
        print(f"- Total processed: {saved_count + premium_count + skipped_count}")
        
        if saved_count < limit and i+1 >= len(problem_list):
            print(f"\nWarning: Only found and saved {saved_count} problems, which is less than the requested {limit}")
            print("Consider increasing the initial problem list size if you want to reach the full limit.")
    
    def retest_results(self, file_pattern: str = None, max_attempts: int = 2):
        """
        Retest existing solution results
        
        Args:
            file_pattern: File match pattern (e.g. "00*.json")
            max_attempts: Maximum attempts per problem
            
        Returns:
            Summary of test results
        """
        print(f"Retesting existing solution results for {self.model_name}")
        return self.executor.test_multiple_problems(file_pattern, max_attempts)
    
    def run_batch_retest(self, num_problems: int = None, random_seed: int = 42):
        """
        Run a batch retest on a random sample of solved problems
        
        Args:
            num_problems: Number of problems to test (None = all)
            random_seed: Random seed for reproducibility
            
        Returns:
            Summary of test results
        """
        print(f"Running batch retest on {self.model_name} results")
        return self.executor.run_batch_test(num_problems, random_seed)

# Example usage - add new arguments to the parser
if __name__ == "__main__":
    # Create argument parser
    parser = argparse.ArgumentParser(description="LeetCode Tester")
    parser.add_argument("--mode", type=str, choices=["download", "test", "retest"], default="download",
                        help="Mode: download problems, test solutions, or retest existing solutions")
    parser.add_argument("--api-key", type=str, default=None,
                        help="OpenAI API key (or set OPENAI_API_KEY environment variable)")
    parser.add_argument("--model", type=str, default="openai/gpt-4o-mini",
                        help="Model to use for solution generation")
    parser.add_argument("--limit", type=int, default=500,
                        help="Number of problems to download in download mode")
    parser.add_argument("--test-count", type=int, default=500,
                        help="Number of problems to test in test mode")
    parser.add_argument("--pattern", type=str, default=None,
                       help="Result file match pattern (e.g. '00*.json')")
    parser.add_argument("--attempts", type=int, default=2,
                       help="Maximum test attempts per problem")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed for problem selection")
    
    args = parser.parse_args()
    
    # Get API key from args or environment
    api_key = args.api_key
    if not api_key:
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key and args.mode != "retest":
            print("Error: OpenAI API key is required. Provide it with --api-key or set OPENAI_API_KEY environment variable.")
            exit(1)
    
    # Create tester instance
    tester = LeetCodeTester(api_key if api_key else "dummy-key", model_name=args.model)
    
    if args.mode == "download":
        # Download problems
        print(f"Downloading {args.limit} LeetCode problems...")
        tester.download_problems(args.limit)
    elif args.mode == "test":
        # Test problems
        print(f"Testing {args.test_count} problems using {args.model}...")
        tester.run_batch_test(args.test_count)
    elif args.mode == "retest":
        # Retest existing solutions
        if args.pattern:
            print(f"Retesting problems matching pattern: {args.pattern}")
            tester.retest_results(args.pattern, args.attempts)
        elif args.test_count is not None:
            print(f"Retesting random sample of {args.test_count} problems")
            tester.run_batch_retest(args.test_count, args.seed)
        else:
            print("Retesting all problems")
            tester.run_batch_retest()