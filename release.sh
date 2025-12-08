#!/bin/bash
set -e

# Check for required argument
if [ -z "$1" ]; then
  echo "Usage: $0 <major|minor|patch>"
  exit 1
fi

# Check for clean git status
if ! git diff-index --quiet HEAD --; then
  echo "Git working directory is not clean. Please commit or stash changes."
  exit 1
fi

# Define the manifest file path
MANIFEST_FILE="custom_components/multisport/manifest.json"

# Get current version from manifest.json
current_version=$(grep '"version":' $MANIFEST_FILE | cut -d '"' -f 4)
echo "Current version: $current_version"

# Bump version
IFS='.' read -r -a version_parts <<< "$current_version"
major=${version_parts[0]}
minor=${version_parts[1]}
patch=${version_parts[2]}

case "$1" in
  major)
    major=$((major + 1))
    minor=0
    patch=0
    ;;
  minor)
    minor=$((minor + 1))
    patch=0
    ;;
  patch)
    patch=$((patch + 1))
    ;;
  *)
    echo "Invalid argument. Use 'major', 'minor', or 'patch'."
    exit 1
    ;;
esac

new_version="$major.$minor.$patch"
echo "New version: $new_version"

# Update manifest.json with the new version
# Using sed; works on both macOS and Linux
sed -i.bak "s/\"version\": \"$current_version\"/\"version\": \"$new_version\"/" $MANIFEST_FILE
rm ${MANIFEST_FILE}.bak

# Commit and tag
git add $MANIFEST_FILE
git commit -m "chore(release): version $new_version"
git tag "v$new_version"

echo "Version bumped to $new_version. Pushing to origin..."

# Push changes
git push origin main
git push --tags

echo "Release tag v$new_version pushed successfully."
echo "GitHub Actions will now create a new release."
