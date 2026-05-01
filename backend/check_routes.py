import re
with open('app/api/v1/agents.py') as f:
    content = f.read()
routes = re.findall(r'@router\.(get|post|delete)\(["\']([^"\']+)["\']', content)
for method, path in routes:
    print(method.upper().ljust(6), path)
