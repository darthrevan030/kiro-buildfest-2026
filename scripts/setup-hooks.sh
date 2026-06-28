#!/bin/sh
cp scripts/git-hooks/post-commit .git/hooks/post-commit
chmod +x .git/hooks/post-commit
echo "Git hooks installed successfully."
