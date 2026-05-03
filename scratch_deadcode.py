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
                            # Try to find class name
                            parent_class = None
                            for parent_node in ast.walk(tree):
                                if isinstance(parent_node, ast.ClassDef):
                                    for child in parent_node.body:
                                        if child is node:
                                            parent_class = parent_node.name
                            
                            defined_funcs.append({
                                'name': node.name,
                                'file': filepath,
                                'filename': file,
                                'class': parent_class
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
    
    # Ignore common framework required functions
    if name in ['arun', 'run', 'invoke', 'ainvoke']: continue
    
    pattern = re.compile(rf'\b{name}\b')
    
    usage_count = 0
    for filepath, content in all_content.items():
        matches = pattern.findall(content)
        usage_count += len(matches)
        
    # 1 usage = just the definition itself
    if usage_count <= 1:
        unused_funcs.append(func_obj)

print(f"Total internal methods/functions found: {len(defined_funcs)}")
print(f"Total dead code candidates: {len(unused_funcs)}")
print("\n--- UNUSED METHODS & FUNCTIONS ---")

for f in sorted(unused_funcs, key=lambda x: x['filename']):
    parent = f"{f['class']}." if f['class'] else ""
    print(f"[{f['filename']}] {parent}{f['name']}")
