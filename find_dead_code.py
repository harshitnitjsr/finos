import ast
import os
import re

backend_dir = r'd:\finos\backend\app'

# 1. Gather all functions/methods
defined_funcs = []
for root, _, files in os.walk(backend_dir):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    # Class methods and standalone functions
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Ignore magic methods
                        if node.name.startswith('__'): continue
                        
                        # Check if it's an API route (it will have decorators starting with @router)
                        is_route = False
                        for dec in node.decorator_list:
                            if isinstance(dec, ast.Call) and getattr(dec.func, 'attr', '') in ['get', 'post', 'put', 'delete', 'patch']:
                                is_route = True
                            if isinstance(dec, ast.Attribute) and dec.attr in ['get', 'post', 'put', 'delete', 'patch']:
                                is_route = True
                        
                        # We only want internal business logic, not API routes directly
                        if not is_route:
                            defined_funcs.append({
                                'name': node.name,
                                'file': filepath,
                                'filename': file,
                                'class': next((n.name for n in ast.iter_child_nodes(tree) if isinstance(n, ast.ClassDef) and node in getattr(n, 'body', [])), None)
                            })
            except Exception as e:
                pass

# 2. Read entire backend content to search for usage
all_content = {}
for root, _, files in os.walk(backend_dir):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    all_content[filepath] = f.read()
            except: pass

# 3. Find unused
unused_funcs = []
for func_obj in defined_funcs:
    name = func_obj['name']
    
    # If the function is a LangGraph node or tool, it might be referenced by string or registered as a tool
    # Ignore common LangChain/LangGraph required functions or overrides
    if name in ['arun', 'run', 'invoke', 'ainvoke']: continue
    
    # Look for calls to this function in all other files
    # Also look in the same file (could be a helper)
    # A reference is typically 
ame( or 
ame, or .name
    # We will search for the raw string 
ame with word boundaries
    pattern = re.compile(rf'\b{name}\b')
    
    usage_count = 0
    for filepath, content in all_content.items():
        # Count occurrences. If it's in the same file, it must appear more than once (the definition counts as 1)
        matches = pattern.findall(content)
        usage_count += len(matches)
        
    # If usage count is exactly 1, it means it's only the def name declaration itself!
    if usage_count <= 1:
        unused_funcs.append(func_obj)

print(f"Total internal methods/functions found: {len(defined_funcs)}")
print(f"Total dead code candidates: {len(unused_funcs)}")
print("\n--- UNUSED METHODS & FUNCTIONS ---")

# Group by category (agents, core, services, etc)
for f in sorted(unused_funcs, key=lambda x: x['filename']):
    parent = f"{f['class']}." if f['class'] else ""
    print(f"[{f['filename']}] {parent}{f['name']}")
