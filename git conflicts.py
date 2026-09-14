git status

git branch --show-current

git log --oneline --decorate -10

# Show me the commits in this repository that changed files inside src/scrapers/philharmonic_hall
git log --oneline --decorate --all -- src/scrapers/philharmonic_hall

# Show me commits whose commit message contains the word philharmonic
git log --oneline --decorate --all --grep="philharmonic"

# Let's compare dev and origin/main.
git log --oneline --left-right --graph origin/main...dev

# The commit where main and dev last shared the same history.
git merge-base origin/main dev

git status --short

git diff --stat origin/dev...HEAD

# Restore deleted chipping_norton_theatre file
git restore src/scrapers/chipping_norton_theatre

git rebase --onto origin/main fdeb62b4 ova2-679-thalian-hall

# "Where did my current branch and main last share the same history?"
git merge-base origin/dev HEAD

git diff --stat origin/main...HEAD

# This shows us exactly what is about to be committed.
git diff --cached --stat


# Fixing merge conflicts
git branch backup-ova2-670-philharmonic-hall

# Does the current origin/main actually contain any files whose path contains philharmonic?"
git ls-tree -r origin/main --name-only | Select-String "philharmonic"

# First, let's verify exactly what your current branch has
git ls-tree -r HEAD --name-only | Select-String "philharmonic"

What we're going to do

We will not cherry-pick 282c7bf5, because that commit contains many unrelated migrated files.

Instead:

#1. Save the four Philharmonic files somewhere temporarily.
#2. Move your feature branch to origin/main.
#3 .Restore only those four files.
#4. Commit them as your Philharmonic Hall feature.
#5. Verify that the branch differs from main only by those files.

git add src/scrapers/liverpool_philharmonic/

git add src/scrapers/liverpool_philharmonic/
git status

# git diff --cached --stat is the correct command right now because it checks what you are about to commit.
git diff --cached --stat


