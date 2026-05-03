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
                                        full_path = f"/{prefix}{path}" if path not in ["/", ""] else f"/{prefix}"
                                        if full_path.endswith('/') and len(full_path) > 1:
                                            full_path = full_path[:-1]
                                        endpoints.append((dec.func.attr.upper(), full_path, file, node.name))
            except Exception as e:
                pass

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
for method, path, file, func_name in endpoints:
    base_path = re.sub(r'\{.*?\}', '', path).replace('//', '/')
    if base_path.endswith('/'): base_path = base_path[:-1]
    
    parts = [p for p in base_path.split('/') if p]
    if not parts: continue
    
    found = False
    if len(parts) == 1:
        if f"/{parts[0]}" in frontend_content: found = True
    else:
        if parts[-1] in frontend_content and parts[0] in frontend_content:
            found = True
            
    if not found:
        unused.append((method, path, file, func_name))

print("Unused API Endpoints:")
for m, p, f, n in sorted(unused, key=lambda x: x[2]):
    print(f"[{m}] {p} (in {f} -> {n})")
