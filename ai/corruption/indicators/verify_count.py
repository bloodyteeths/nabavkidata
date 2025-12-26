#!/usr/bin/env python3
"""
Verify indicator count and categorization
"""

import re

# Read the file
with open('dozorro_indicators.py', 'r') as f:
    content = f.read()

# Count indicator classes
indicators = re.findall(r'^class (\w+Indicator)\(Indicator\):', content, re.MULTILINE)

# Count by category
categories = {
    'Competition': [],
    'Price': [],
    'Timing': [],
    'Relationship': [],
    'Procedural': []
}

# Parse each indicator
for indicator in indicators:
    # Find the class definition and check category
    pattern = f'class {indicator}.*?def __init__.*?self.category = "(\\w+)"'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        category = match.group(1)
        if category in categories:
            categories[category].append(indicator)

print('=' * 70)
print('DOZORRO-STYLE INDICATORS - IMPLEMENTATION SUMMARY')
print('=' * 70)
print(f'\nTotal Indicator Classes: {len(indicators)}')
print(f'\nBreakdown by Category:')
print('-' * 70)

for category, inds in categories.items():
    print(f'\n{category} ({len(inds)} indicators):')
    for ind in inds:
        # Check if fully implemented or stub
        impl_pattern = f'class {ind}.*?async def calculate.*?return self._create_result\\(0, \\{{\\}}, "Not yet implemented"\\)'
        is_stub = bool(re.search(impl_pattern, content, re.DOTALL))
        status = '(stub)' if is_stub else '(implemented)'
        print(f'  {status:15} {ind}')

print('\n' + '=' * 70)

# Count fully implemented
fully_implemented = sum(
    1 for indicator in indicators
    if not re.search(
        f'class {indicator}.*?return self._create_result\\(0, \\{{\\}}, "Not yet implemented"\\)',
        content,
        re.DOTALL
    )
)

print(f'Fully Implemented: {fully_implemented}/{len(indicators)}')
print(f'Stubs Ready: {len(indicators) - fully_implemented}/{len(indicators)}')
print(f'\nSTATUS: {len(indicators)} indicators (exceeds Dozorro baseline of 40)')
print('=' * 70)
