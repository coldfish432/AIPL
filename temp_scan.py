import os
import re
modules=set()
root='fix/refactored-src'
for dirpath, _, filenames in os.walk(root):
    for f in filenames:
        if not f.endswith(('.ts','.tsx','.js','.jsx')):
            continue
        path=os.path.join(dirpath,f)
        with open(path,'r',encoding='utf-8',errors='ignore') as fh:
            for line in fh:
                m=re.search(r'from\s+["\']([^"\']+)["\']', line)
                if m:
                    mod=m.group(1)
                    if mod.startswith('.') or mod.startswith('@'):
                        continue
                    modules.add(mod)
print('\n'.join(sorted(modules)))
