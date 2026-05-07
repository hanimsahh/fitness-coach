# Check current tools.py nutrition calculation
with open('fitness_coach/tools.py', 'r') as f:
    content = f.read()

# Find and show the calculation section
start = content.find('scale = grams / 100')
print(content[start:start+500])
