git status

git branch --show-current

git log --oneline --decorate -10

git status --short

git diff --stat origin/dev...HEAD

# Restore deleted chipping_norton_theatre file
git restore src/scrapers/chipping_norton_theatre

git rebase --onto origin/main fdeb62b4 ova2-679-thalian-hall

# "Where did my current branch and main last share the same history?"
git merge-base origin/dev HEAD

git diff --stat origin/main...HEAD
