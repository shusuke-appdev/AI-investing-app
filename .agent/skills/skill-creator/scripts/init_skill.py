import os
import argparse
import sys

def create_skill(name, output_dir):
    skill_path = os.path.join(output_dir, name)
    
    if os.path.exists(skill_path):
        print(f"Error: Directory '{skill_path}' already exists.")
        sys.exit(1)

    # Create directories
    os.makedirs(skill_path)
    os.makedirs(os.path.join(skill_path, 'scripts'))
    os.makedirs(os.path.join(skill_path, 'references'))
    os.makedirs(os.path.join(skill_path, 'assets'))

    # Create SKILL.md template
    skill_md_content = f"""---
name: {name}
description: Description of what this skill does and when to use it.
---

# {name.replace('-', ' ').title()}

## Usage

Description of how this skill should be used.

## Instructions

Detailed instructions for the agent.
"""
    with open(os.path.join(skill_path, 'SKILL.md'), 'w', encoding='utf-8') as f:
        f.write(skill_md_content)

    # Create example files
    with open(os.path.join(skill_path, 'scripts', 'example_script.py'), 'w', encoding='utf-8') as f:
        f.write("# Example script\nprint('Hello from the skill script')\n")
    
    with open(os.path.join(skill_path, 'references', 'example_reference.md'), 'w', encoding='utf-8') as f:
        f.write("# Example Reference\n\nThis is reference material.\n")

    print(f"Skill '{name}' initialized successfully at: {skill_path}")

def main():
    parser = argparse.ArgumentParser(description='Initialize a new skill directory.')
    parser.add_argument('name', help='Name of the skill')
    parser.add_argument('--path', default='.', help='Output directory (default: current directory)')
    
    args = parser.parse_args()
    create_skill(args.name, args.path)

if __name__ == '__main__':
    main()
