import os
import re

def check_sql_file(filepath):
    """
    Scans SQL files for schema best practices.
    """
    with open(filepath, 'r') as f:
        content = f.read().lower()

    errors = []
    warnings = []
    
    # 1. Check for Foreign Keys without Indexes
    # (Regex to find REFERENCES but check if there's an INDEX on that column in the same file)
    fk_matches = re.findall(r'(\w+)\s+\w+\s+references\s+(\w+)\s*\((\w+)\)', content)
    for col, ref_table, ref_col in fk_matches:
        if f'index' not in content or col not in content:
            warnings.append(f"Foreign key column '{col}' might be missing an index. This will cause slow joins and deletes.")

    # 2. Check for snake_case naming convention
    camel_case_matches = re.findall(r'create\s+table\s+(\w*[A-Z]\w*)', content)
    for table in camel_case_matches:
        errors.append(f"Table name '{table}' uses CamelCase. Use snake_case for Postgres compatibility.")

    # 3. Check for 'SELECT *' in views or functions
    if 'select *' in content:
        warnings.append("'SELECT *' found. Explicitly name columns to prevent breakage if schema changes.")

    # 4. Check for timestamp without timezone
    if 'timestamp' in content and 'timezone' not in content:
        warnings.append("Using 'TIMESTAMP' without 'TIME ZONE'. Always use 'TIMESTAMPTZ' for global consistency.")

    return errors, warnings

def scan_sql(directory="db/migrations"):
    if not os.path.exists(directory):
        print(f"Directory {directory} not found.")
        return

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.sql'):
                path = os.path.join(root, file)
                errors, warnings = check_sql_file(path)
                
                if errors or warnings:
                    print(f"\nIssues in {path}:")
                    for err in errors:
                        print(f"  [ERROR] {err}")
                    for warn in warnings:
                        print(f"  [WARN] {warn}")

if __name__ == "__main__":
    scan_sql()
