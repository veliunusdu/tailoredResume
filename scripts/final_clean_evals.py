import json
import os

def clean_evals():
    dataset_path = 'app/evals_dataset.json'
    
    with open(dataset_path, 'r', encoding='utf-8') as f:
        cases = json.load(f)

    fixed_count = 0
    senior_keywords = ['senior ', 'lead ', 'staff ', 'principal ', 'manager']

    for case in cases:
        title = case.get('title', '').lower()
        
        # If the dataset expects a "yes" but the title has a senior keyword
        if case.get('expected_verdict') == 'yes':
            if any(keyword in title for keyword in senior_keywords):
                print(f"Fixing mismatch: {case['title']}")
                case['expected_verdict'] = 'no'
                case.pop('min_score', None)
                case['max_score'] = 3
                case['difficulty'] = 'easy'
                fixed_count += 1

    with open(dataset_path, 'w', encoding='utf-8') as f:
        json.dump(cases, f, indent=2)

    print(f"\nFixed {fixed_count} flawed test cases!")

if __name__ == "__main__":
    clean_evals()
