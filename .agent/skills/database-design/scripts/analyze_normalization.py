import os
import re

def check_normalization(filepath):
    """
    Scans SQL schema for normalization and architecture issues.
    """
    with open(filepath, 'r') as f:
        content = f.read().lower()

    errors = []
    warnings = []
    
    # 1. Check for many nullable columns (potential 1:1 or denormalization issue)
    null_count = len(re.findall(r'null', content))
    column_count = len(re.findall(r'\w+\s+\w+', content)) # Very rough estimate
    if column_count > 10 and null_count / column_count > 0.5:
        warnings.append("High ratio of nullable columns. Consider splitting into separate tables (1:1 relationship).")

    # 2. Check for missing primary keys
    tables = re.findall(r'create\s+table\s+(\w+)\s*\(', content)
    for table in tables:
        # Find the content of the table creation
        table_start = content.find(f'create table {table}')
        table_end = content.find(');', table_start)
        table_content = content[table_start:table_end]
        
        if 'primary key' not in table_content:
            errors.append(f"Table '{table}' is missing a PRIMARY KEY definition.")

    # 3. Check for broad 'text' usage without constraints
    if 'text' in content and 'check' not in content:
        warnings.append("Broad 'TEXT' usage found without constraints. Consider adding CHECK constraints for specific formats.")

    return errors, warnings

def scan_designs(directory="db/schema"):
    if not os.path.exists(directory):
        print(f"Directory {directory} not found.")
        return

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.sql'):
                path = os.path.join(root, file)
                errors, warnings = check_normalization(path)
                
                if errors or warnings:
                    print(f"\nIssues in {path}:")
                    for err in errors:
                        print(f"  [ERROR] {err}")
                    for warn in warnings:
                        print(f"  [WARN] {warn}")

if __name__ == "__main__":
    scan_designs()
