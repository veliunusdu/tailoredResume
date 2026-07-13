import json
import random

def main():
    with open('app/evals_dataset.json', 'r', encoding='utf-8') as f:
        cases = json.load(f)

    # add difficulty to original cases
    difficulties = ['easy', 'medium', 'hard']
    for case in cases:
        if 'difficulty' not in case:
            case['difficulty'] = random.choice(difficulties)

    expanded_cases = list(cases)
    
    # generate synthetic variations to reach 40 cases
    count = len(expanded_cases)
    while count < 40:
        base_case = random.choice(cases)
        new_case = base_case.copy()
        prefix = random.choice(["Senior ", "Junior ", "Lead ", "Staff ", "Associate "])
        
        # Don't duplicate prefixes
        if not base_case['title'].startswith(prefix):
            new_case['title'] = prefix + base_case['title'].replace("Senior ", "").replace("Junior ", "")
            
        new_case['company'] = base_case['company'] + " " + str(random.randint(100, 999))
        
        # Adjust difficulty randomly
        if base_case['expected_verdict'] == 'yes':
            new_case['difficulty'] = random.choice(['easy', 'medium'])
        else:
            new_case['difficulty'] = random.choice(['medium', 'hard'])
            
        expanded_cases.append(new_case)
        count += 1

    with open('app/evals_dataset.json', 'w', encoding='utf-8') as f:
        json.dump(expanded_cases, f, indent=2)

    print(f"Expanded to {len(expanded_cases)} cases.")

if __name__ == "__main__":
    main()
