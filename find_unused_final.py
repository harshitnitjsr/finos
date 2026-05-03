import ast
import os

backend_dir = r'd:\finos\backend\app\api\v1'
frontend_dirs = [r'd:\finos\app', r'd:\finos\components', r'd:\finos\lib', r'd:\finos\hooks']

# 1. Gather all API Endpoints
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
                            if isinstance(dec, ast.Call) and getattr(dec.func, 'attr', None) in ['get', 'post', 'put', 'patch', 'delete']:
                                if dec.args and isinstance(dec.args[0], ast.Constant):
                                    path = dec.args[0].value
                                    prefix = file.replace('.py', '')
                                    if prefix == 'router': continue
                                    if prefix == 'workspace_chat': prefix = 'workspace-chats'
                                    elif prefix == 'chat': prefix = 'chat'
                                    
                                    full_path = f"/{prefix}{path}"
                                    full_path = full_path.replace('//', '/')
                                    if full_path.endswith('/') and len(full_path) > 1:
                                        full_path = full_path[:-1]
                                        
                                    endpoints.append({
                                        'method': dec.func.attr.upper(),
                                        'path': full_path,
                                        'file': file,
                                        'func': node.name
                                    })
            except: pass

# 2. Extract apiFetch calls and /api/backend/ calls from frontend
frontend_fetches = set()
for d in frontend_dirs:
    for root, _, files in os.walk(d):
        for file in files:
            if file.endswith(('.ts', '.tsx', '.js', '.jsx')):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for line in lines:
                            if 'apiFetch' in line or '/api/backend/' in line:
                                frontend_fetches.add(line.strip())
                except: pass

unused = []
for ep in endpoints:
    # Build a regex or simple matcher for the endpoint
    # E.g., /workflows/{workflow_id}/state -> /workflows/.*/state
    import re
    pattern = ep['path']
    pattern = re.sub(r'\{.*?\}', r'.*', pattern)
    
    found = False
    for fetch_line in frontend_fetches:
        if re.search(pattern, fetch_line):
            found = True
            break
            
    if not found:
        unused.append(ep)

print(f"Total backend endpoints: {len(endpoints)}")
print(f"Total unused endpoints: {len(unused)}")
print("\n--- UNUSED API ENDPOINTS ---")
for ep in sorted(unused, key=lambda x: x['file']):
    print(f"[{ep['method']}] {ep['path']} (in {ep['file']} -> {ep['func']})")
