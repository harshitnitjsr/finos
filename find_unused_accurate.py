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
                                        
                                        full_path = f"/{prefix}{path}"
                                        full_path = full_path.replace('//', '/')
                                        if full_path.endswith('/') and len(full_path) > 1:
                                            full_path = full_path[:-1]
                                            
                                        endpoints.append({
                                            "method": dec.func.attr.upper(), 
                                            "path": full_path, 
                                            "file": file, 
                                            "func": node.name
                                        })
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
for ep in endpoints:
    # Convert FastAPI path params to regex matching Next.js template literals or fetch calls
    # E.g. /invoices/{invoice_id}/approve -> r'/invoices/[^/]+/approve'
    pattern = ep["path"]
    
    # We replace {} with a non-slash matcher
    pattern = re.sub(r'\{.*?\}', r'[^/]+', pattern)
    
    # Let's see if the path appears in frontend
    # Since frontend might use /api/backend/invoices//approve, we'll check if
    # the static segments appear in sequence.
    
    segments = [s for s in re.split(r'\{.*?\}', ep["path"]) if s and s != '/']
    
    # To be extremely accurate, we can use regex to find fetch calls or url builders
    # Regex: build something like /invoices/.*?/approve
    regex_str = '.*'.join([re.escape(s) for s in segments])
    if not regex_str:
        continue
        
    match = re.search(regex_str, frontend_content)
    
    if not match:
        unused.append(ep)

print("--- UNUSED API ENDPOINTS ---")
for ep in sorted(unused, key=lambda x: x["file"]):
    print(f"[{ep['method']}] {ep['path']}  (in {ep['file']} -> {ep['func']})")
