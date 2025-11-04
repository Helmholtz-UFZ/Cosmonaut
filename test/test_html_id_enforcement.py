"""Test HTML ID constants enforcement.

This test ensures:
1. All id= usages in cosmonaut_app/ use constants from html_ids.py
2. All constants in html_ids.py are used in callbacks (or marked with # nocheck)
"""

import ast
import re
from pathlib import Path
from typing import List, Set, Tuple, Dict


def get_cosmonaut_app_path() -> Path:
    """Get path to cosmonaut_app directory."""
    return Path(__file__).parent.parent / "cosmonaut_app"


def get_html_ids_path() -> Path:
    """Get path to html_ids.py file."""
    return get_cosmonaut_app_path() / "constants" / "html_ids.py"


def load_html_ids_constants() -> Dict[str, bool]:
    """Load all ID constants from html_ids.py.

    Returns:
        Dict mapping constant name to whether it has # nocheck comment.
    """
    html_ids_file = get_html_ids_path()
    constants = {}

    with open(html_ids_file, "r") as f:
        for line in f:
            # Match pattern: CONSTANT_NAME = "value"
            match = re.match(r'^([A-Z_]+_ID)\s*=\s*"[^"]*"(.*)$', line)
            if match:
                const_name = match.group(1)
                rest_of_line = match.group(2)
                has_nocheck = "# nocheck" in rest_of_line or "#nocheck" in rest_of_line
                constants[const_name] = has_nocheck

    return constants


def find_python_files(directory: Path) -> List[Path]:
    """Find all Python files in directory recursively."""
    return list(directory.rglob("*.py"))


def is_comment_or_docstring(line: str) -> bool:
    """Check if line is a comment or likely in docstring."""
    stripped = line.strip()
    return (
        stripped.startswith("#")
        or stripped.startswith('"""')
        or stripped.startswith("'''")
    )


def find_id_usages_in_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Find all id= usages in Dash components.

    Returns:
        List of (line_number, matched_text, id_value) tuples.
    """
    violations = []

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Common Dash component prefixes and callback patterns
    component_prefixes = [
        "html\\.",
        "dcc\\.",
        "dbc\\.",
        "dl\\.",
        "Input\\(",
        "Output\\(",
        "State\\(",
    ]

    # Track if we're inside a component definition (multi-line)
    in_component = False

    for line_num, line in enumerate(lines, start=1):
        # Skip comment lines
        if is_comment_or_docstring(line):
            continue

        # Skip variable assignments (id = something with spaces around =)
        if re.search(r"\bid\s+=\s+", line):
            continue

        # Check if this line starts or continues a component
        has_component_start = any(
            re.search(prefix, line) for prefix in component_prefixes
        )

        # Start component context when we see a component prefix with opening paren
        if has_component_start and "(" in line:
            in_component = True

        # End component context when we see a closing paren at the start (dedented)
        if in_component and re.match(r"^\s*\)", line):
            in_component = False
            continue

        # Only check lines that are in a component context OR have a component prefix
        if not (in_component or has_component_start):
            continue

        # Now find id= patterns in this component line
        # Match: id="string", id='string', id=variable, id=f"string"
        patterns = [
            r'id\s*=\s*"([^"]+)"',  # id="string"
            r"id\s*=\s*'([^']+)'",  # id='string'
            r'id\s*=\s*f"([^"]+)"',  # id=f"string"
            r"id\s*=\s*f'([^']+)'",  # id=f'string'
            r"id\s*=\s*([a-z_][a-zA-Z0-9_]*)",  # id=variable (lowercase start = not constant)
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, line)
            for match in matches:
                id_value = match.group(1)
                matched_text = match.group(0)
                violations.append((line_num, matched_text, id_value))

    return violations


def check_if_constant_from_html_ids(
    id_value: str, html_ids_constants: Set[str]
) -> bool:
    """Check if an ID value is a constant from html_ids.py."""
    # Constant names are uppercase with underscores
    if not id_value.isupper():
        return False
    if not id_value.endswith("_ID"):
        return False
    return id_value in html_ids_constants


def find_callback_id_usages_in_file(file_path: Path) -> Set[str]:
    """Find all ID constants used in @app.callback or @callback decorators.

    This now also finds callbacks inside registration functions like:
        def register_navbar_callbacks(app):
            @app.callback(...)
            def some_function():
                pass

    Returns:
        Set of constant names used in Input/Output/State.
    """
    used_constants = set()

    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Parse the file as AST
        tree = ast.parse(content, filename=str(file_path))

        # Recursively find all FunctionDef nodes (including nested ones)
        def find_all_functions(node):
            """Recursively find all function definitions."""
            functions = []
            for child in ast.walk(node):
                if isinstance(child, ast.FunctionDef):
                    functions.append(child)
            return functions

        # Find all function decorators (top-level and nested)
        for func_node in find_all_functions(tree):
            for decorator in func_node.decorator_list:
                # Check if this is a callback decorator
                # Pattern 1: @app.callback (ast.Attribute)
                # Pattern 2: @callback (ast.Name)
                is_callback = False
                if isinstance(decorator, ast.Call):
                    if (
                        isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == "callback"
                    ):
                        is_callback = True
                    elif (
                        isinstance(decorator.func, ast.Name)
                        and decorator.func.id == "callback"
                    ):
                        is_callback = True

                if is_callback:
                    # Look at all arguments to the decorator
                    for arg in decorator.args:
                        used_constants.update(extract_constants_from_ast(arg))
                    for keyword in decorator.keywords:
                        used_constants.update(extract_constants_from_ast(keyword.value))

    except SyntaxError as e:
        # If file has syntax errors, fail with file name
        raise SyntaxError(f"Syntax error in {file_path}: {e}") from e

    return used_constants


def extract_constants_from_ast(node: ast.AST) -> Set[str]:
    """Extract constant names from an AST node.

    Recursively searches for Name nodes that look like ID constants.
    """
    constants = set()

    if isinstance(node, ast.Name):
        # Check if this looks like an ID constant
        if node.id.isupper() and node.id.endswith("_ID"):
            constants.add(node.id)
    elif isinstance(node, ast.Call):
        # For Input(...), Output(...), State(...)
        # Check all arguments
        for arg in node.args:
            constants.update(extract_constants_from_ast(arg))
        for keyword in node.keywords:
            constants.update(extract_constants_from_ast(keyword.value))
    elif isinstance(node, ast.List) or isinstance(node, ast.Tuple):
        # Handle [Input(...), Output(...)]
        for element in node.elts:
            constants.update(extract_constants_from_ast(element))

    return constants


def test_no_string_literal_ids():
    """Test that all id= usages use constants from html_ids.py."""
    cosmonaut_app = get_cosmonaut_app_path()
    html_ids_constants = set(load_html_ids_constants().keys())

    all_violations = []

    # Scan all Python files
    for py_file in find_python_files(cosmonaut_app):
        # Skip html_ids.py itself
        if py_file.name == "html_ids.py":
            continue

        # Skip __pycache__ and similar
        if "__pycache__" in str(py_file):
            continue

        violations = find_id_usages_in_file(py_file)

        for line_num, matched_text, id_value in violations:
            # Check if this is a constant from html_ids.py
            if not check_if_constant_from_html_ids(id_value, html_ids_constants):
                rel_path = py_file.relative_to(cosmonaut_app.parent)
                all_violations.append(f"{rel_path}:{line_num} - {matched_text}")

    if all_violations:
        error_msg = "\n\nVIOLATIONS: Found id= usages with string literals or non-html_ids constants:\n\n"
        error_msg += "\n".join(f"  {v}" for v in all_violations)
        error_msg += "\n\nAll id= usages must use constants from cosmonaut_app/constants/html_ids.py"
        error_msg += '\nExample: id=START_JOB_BUTTON_HOME_ID (not id="start-job")'
        assert False, error_msg


def test_no_unused_id_constants():
    """Test that all constants in html_ids.py are used in callbacks or marked with # nocheck."""
    cosmonaut_app = get_cosmonaut_app_path()
    html_ids_constants = load_html_ids_constants()

    # Find all constants used in callbacks across all files
    used_in_callbacks = set()
    for py_file in find_python_files(cosmonaut_app):
        if "__pycache__" in str(py_file):
            continue
        used_in_callbacks.update(find_callback_id_usages_in_file(py_file))

    # Check for unused constants
    violations = []
    for const_name, has_nocheck in html_ids_constants.items():
        if const_name not in used_in_callbacks:
            if not has_nocheck:
                violations.append(const_name)

    if violations:
        error_msg = "\n\nVIOLATIONS: Found ID constants not used in any @app.callback decorator:\n\n"
        error_msg += "\n".join(f"  {v}" for v in sorted(violations))
        error_msg += "\n\nEither:"
        error_msg += "\n  1. Use the constant in a callback (Input/Output/State), OR"
        error_msg += "\n  2. Add '# nocheck' comment if constant is legitimately unused"
        error_msg += "\n\nExample in html_ids.py:"
        error_msg += '\n  CONTAINER_DIV_SHARED_ID = "container-div-shared-id"  # nocheck used for CSS only'
        assert False, error_msg
