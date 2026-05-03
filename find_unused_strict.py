import ast
import os
import re

backend_dir = r'd:\finos\backend\app\api\v1'
frontend_dirs = [r'd:\finos\app', r'd:\finos\components', r'd:\finos\lib', r'd:\finos\hooks']

endpoints = []

for root, _, files in os.walk(backend_dir):
    for file in files:
        if file.endswith('.py') and file != '__init__.py':
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        for dec in node.decorator_list:
                            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                                if dec.func.attr in ['get', 'post', 'put', 'patch', 'delete']:
                                    if dec.args and isinstance(dec.args[0], ast.Constant):
                                        path = dec.args[0].value
                                        prefix = file.replace('.py', '')
                                        if prefix == 'router': continue
                                        if prefix == 'chat': prefix = 'chat'
                                        elif prefix == 'workspace_chat': prefix = 'workspace-chats'
                                        
                                        # Construct full path
                                        full_path = f"/{prefix}{path}"
                                        full_path = full_path.replace('//', '/')
                                        if full_path.endswith('/') and len(full_path) > 1:
                                            full_path = full_path[:-1]
                                            
                                        endpoints.append((dec.func.attr.upper(), full_path, file, node.name))
            except Exception as e:
                pass

# Collect frontend content
frontend_content = ""
for d in frontend_dirs:
    if os.path.exists(d):
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith(('.ts', '.tsx', '.js', '.jsx')):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            frontend_content += f.read() + "\n"
                    except:
                        pass

unused = []
for method, full_path, file, func_name in endpoints:
    # Convert path params to regex for frontend search
    # e.g. /invoices/{id}/analyze -> /invoices/.*/analyze
    # Or just check if the non-variable string exists literally
    
    # Let's extract the static parts of the path that should be in the frontend fetch calls
    # For example, if path is /invoices/{invoice_id}/approve, we search for "/invoices/" and "/approve"
    static_parts = [p for p in re.split(r'\{.*?\}', full_path) if p and p != '/']
    
    found = True
    for part in static_parts:
        if part not in frontend_content:
            found = False
            break
            
    if not found:
        unused.append((method, full_path, file, func_name))

print("--- UNUSED API ENDPOINTS IN FRONTEND ---")
for m, p, f, n in sorted(unused, key=lambda x: x[2]):
    print(f"[{m}] {p} (in {f} -> {n})")
