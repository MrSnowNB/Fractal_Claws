import yaml

# Test YAML dump and load
d = {'goal_class': 'integration-test'}
y = yaml.dump(d)
print('YAML output:')
print(repr(y))

docs = list(yaml.safe_load_all(y))
print(f'len(docs)={len(docs)}')
print(f'docs[0]={docs[0]}')
print(f'isinstance(docs[0], dict)={isinstance(docs[0], dict)}')
print(f'"elapsed_s" in docs[0]={"elapsed_s" in docs[0]}')

# Now test the actual test scenario
closed_dir = r'C:\Users\AMD\Documents\Fractal_Claws\tickets\closed'
log_dir = r'C:\Users\AMD\Documents\Fractal_Claws\logs'
skills_dir = r'C:\Users\AMD\Documents\Fractal_Claws\skills'

# Run extraction
from src.trajectory_extractor import run_extraction
paths = run_extraction(closed_dir=closed_dir, log_dir=log_dir, skills_dir=skills_dir)
print(f'paths={paths}')