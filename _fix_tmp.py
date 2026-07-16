# -*- coding: utf-8 -*-
import re

path = r'C:\code\SVN_CODE\branches\real\could_frontend\audit-report-could_frontend-2026-07-16.md'
with open(path, encoding='utf-8', errors='replace') as f:
    text = f.read()

lines = text.split('\n')

out = []
in_finding = False
current_category = None

BETTER_FIX_LINE = '- Better long-term fix: 见 Minimal fix；长期见 Recommended Fix Order 段与 Quick Wins 段。'

i = 0
n = len(lines)
while i < n:
    line = lines[i]

    # Detect finding start
    if line.startswith('### Finding:'):
        in_finding = True
        current_category = None
        out.append(line)
        i += 1
        continue

    # Detect leaving a finding chunk: a ## or # heading ends the chunk
    if in_finding and (line.startswith('## ') or line.startswith('# ')):
        in_finding = False
        current_category = None
        out.append(line)
        i += 1
        continue

    if not in_finding:
        out.append(line)
        i += 1
        continue

    # --- Inside a finding chunk ---

    # Pattern: "- **FIELD:** value"  (with wrapping **)
    m = re.match(r'^- \*\*([^*]+?)\*\*:?\s?(.*)$', line)
    # Pattern: "- Realistic failure scenario：" indented ("-   - **Realistic ...：** value")
    m_real = re.match(r'^\s*-\s+\*\*Realistic failure scenario[：:]\*?\*?\s?(.*)$', line)

    # Handle indented Realistic failure scenario FIRST (before generic field match)
    if m_real:
        out.append(f'- Realistic failure scenario: {m_real.group(1)}')
        i += 1
        continue

    if m:
        field = m.group(1)
        value = m.group(2)
        new_line = f'- {field}: {value}'

        # Track category value
        if field == 'Category':
            current_category = value

        # Before "Why it matters", insert a Problem line (same value)
        if field == 'Why it matters':
            out.append(f'- Problem: {value}')

        out.append(new_line)

        # After "Status", insert Affected area using current_category
        if field == 'Status':
            out.append(f'- Affected area: {current_category if current_category else ""}')

        # After "Minimal fix", insert Better long-term fix
        if field == 'Minimal fix':
            out.append(BETTER_FIX_LINE)

        i += 1
        continue

    # Non-field line (e.g., Evidence sub-bullets) — but check for stray
    # "Realistic failure scenario" without ** that's still indented
    m_real2 = re.match(r'^\s*-\s+Realistic failure scenario[：:]\s?(.*)$', line)
    if m_real2:
        out.append(f'- Realistic failure scenario: {m_real2.group(1)}')
        i += 1
        continue

    # Default: keep line as-is
    out.append(line)
    i += 1

new_text = '\n'.join(out)

# Ensure no BOM
with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(new_text)

print('done; lines in=', len(lines), 'lines out=', len(out))