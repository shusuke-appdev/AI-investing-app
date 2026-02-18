import argparse
import os
import re
import sys
import zipfile


def validate_skill(skill_path):
    print(f"Validating skill at: {skill_path}")
    skill_name = os.path.basename(skill_path)

    # 1. Check directory name
    if not re.match(r"^[a-z0-9-]+$", skill_name):
        print(
            "Error: Skill directory name must contain only lowercase letters, numbers, and hyphens."
        )
        return False

    # 2. Check for SKILL.md
    skill_md_path = os.path.join(skill_path, "SKILL.md")
    if not os.path.exists(skill_md_path):
        print("Error: SKILL.md not found.")
        return False

    # 3. Check frontmatter
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        print("Error: SKILL.md missing valid YAML frontmatter.")
        return False

    frontmatter = match.group(1)
    if "name:" not in frontmatter:
        print("Error: Frontmatter missing 'name' field.")
        return False
    if "description:" not in frontmatter:
        print("Error: Frontmatter missing 'description' field.")
        return False

    print("Validation successful.")
    return True


def package_skill(skill_path, output_dir):
    skill_name = os.path.basename(skill_path)
    zip_filename = f"{skill_name}.zip"

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        zip_path = os.path.join(output_dir, zip_filename)
    else:
        zip_path = zip_filename

    print(f"Packaging skill to: {zip_path}")

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(skill_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(skill_path))
                    zipf.write(file_path, arcname)
        print("Packaging complete.")
        return True
    except Exception as e:
        print(f"Error packaging skill: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate and package a skill.")
    parser.add_argument("path", help="Path to the skill directory")
    parser.add_argument(
        "output_dir", nargs="?", help="Optional output directory for the zip file"
    )

    args = parser.parse_args()

    path = os.path.abspath(args.path)
    if not os.path.isdir(path):
        print(f"Error: Directory not found at {path}")
        sys.exit(1)

    if validate_skill(path):
        package_skill(path, args.output_dir)
    else:
        print("Skill validation failed. Aborting package.")
        sys.exit(1)


if __name__ == "__main__":
    main()
