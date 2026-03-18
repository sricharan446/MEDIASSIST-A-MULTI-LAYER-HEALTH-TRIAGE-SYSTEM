#!/usr/bin/env python3
# Fix all missing create_session mocks in test_pipeline.py

with open('test_pipeline.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    
    # Check if this line contains 'patch("app.memory") as mock_mem'
    if 'patch("app.memory") as mock_mem' in line:
        # Look ahead to find the first mock_mem setup line
        j = i + 1
        # Skip continuation lines (lines with backslash)
        while j < len(lines) and lines[j].rstrip().endswith(', \\'):
            new_lines.append(lines[j])
            j += 1
        
        # Add the line that ends the with statement  
        if j < len(lines):
            new_lines.append(lines[j])
            j += 1
        
        # Now add lines until we find the first mock_mem setup
        first_mock_found = False
        while j < len(lines) and not first_mock_found:
            if 'mock_mem.' in lines[j]:
                if 'create_session' not in lines[j]:
                    # Insert the missing create_session line
                    indent = len(lines[j]) - len(lines[j].lstrip())
                    new_lines.append(' ' * indent + 'mock_mem.create_session.return_value = TEST_SESSION\n')
                first_mock_found = True
            new_lines.append(lines[j])
            j += 1
        
        i = j - 1
    
    i += 1

with open('test_pipeline.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Fixed all memory mocks!')
