"""Read LevelDB log and dump ALL readable key-value data."""
import re, json

path = 'C:/Users/KI/AppData/Local/Microsoft/Edge/User Data/Profile 1/Local Extension Settings/mfbcdcnpokpoajjciilocoachedjkima/000003.log'
with open(path, 'rb') as f:
    data = f.read()

print(f'{len(data)} bytes')
print()

# Extract ALL readable strings (length >= 3, mostly printable)
strings = []
for m in re.finditer(rb'[\x20-\x7E]{3,}', data):
    s = m.group().decode('ascii', errors='replace')
    if s.strip():
        strings.append(s)

# Group consecutive strings (they might belong to same key-value)
# Filter noise
meaningful = [s for s in strings if len(s) > 4 and not s.startswith(' ') and not all(c in '0123456789.+-eE' for c in s)]
print('=== All meaningful strings ===')
for s in meaningful:
    print(f'  {s}')

# Try to find JSON
print()
print('=== Raw data containing possible JSON ===')
# Look for { } patterns
text = data.decode('latin-1', errors='replace')
for m in re.finditer(r'\{[^{}]{10,}\}', text):
    candidate = m.group()
    try:
        obj = json.loads(candidate)
        print(f'  VALID JSON: {json.dumps(obj, ensure_ascii=False, indent=4)}')
    except:
        # Show partial
        if any(kw in candidate for kw in ['verif', 'auth', 'token', 'state', 'session', 'login', 'sign', 'key', 'lock']):
            print(f'  PARTIAL: {candidate[:200]}')

# Also look for boolean-like values
print()
print('=== Looking for state-related patterns ===')
for pattern in [rb'verified', rb'verif', rb'auth', rb'token', rb'session', rb'state', rb'needs', rb'locked']:
    for m in re.finditer(pattern, data, re.IGNORECASE):
        ctx = data[max(0, m.start()-20):m.end()+20]
        print(f'  Found "{pattern.decode()}": context={ctx!r}')
