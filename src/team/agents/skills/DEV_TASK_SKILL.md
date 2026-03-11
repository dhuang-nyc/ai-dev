# Dev Agent – Task Workflow

You are a dev agent. Your job is to implement a GitHub task and open a pull request.
Follow every step below in order. Do not skip steps.

## Step 1 – Sync with main

```bash
git checkout main
git pull origin main
```

This ensures you are working from the latest code, including any `.gitignore` updates.

## Step 2 – Create a feature branch

Use the exact branch name provided in the task prompt:

```bash
git checkout -b <BRANCH_NAME>
```

If the branch already exists locally, just check it out:

```bash
git checkout <BRANCH_NAME>
git rebase main
```

## Step 3 – Implement the task

Read the task description and implementation details carefully. Write production-quality code.
Make targeted, minimal changes. Do not reformat unrelated files or install new packages unless required.

## Step 4 – Check for large files before committing

Before staging, run:

```bash
find . -not -path './.git/*' -size +50M
```

If any large files exist outside of `.git/`, add them to `.gitignore` before proceeding.
**Never commit `node_modules/`, `.next/`, `dist/`, `build/`, or binary files over 5 MB.**
If `.gitignore` is missing those entries, add them now.

## Step 5 – Stage and commit

```bash
git add -A
git status   # review what is staged — confirm no large files or node_modules
git commit -m "feat: <TASK_TITLE>"
```

If there is nothing to commit (working tree is clean), the task may already be done on this branch — still proceed to open the PR.

## Step 6 – Push the branch

```bash
git push origin <BRANCH_NAME>
```

## Step 7 – Open a pull request

```bash
gh pr create \
  --title "<TASK_TITLE>" \
  --body "<TASK_DESCRIPTION>" \
  --base main \
  --head <BRANCH_NAME>
```

## Step 8 – Output the PR URL

After the PR is created, print this line as the very last line of your response (no trailing text):

```
PR_URL: <pr_url>
```

Example: `PR_URL: https://github.com/owner/repo/pull/42`

---

## Git Troubleshooting – Self-Correction Guide

If you hit any git error, **do not give up**. Diagnose and fix it, then continue.

### Stale or corrupt remote-tracking refs
Symptom: `cannot lock ref 'refs/remotes/origin/...'` or `unable to update local ref`
```bash
git remote prune origin          # remove stale remote-tracking refs
git fetch --prune origin         # re-fetch with pruning
```
If that still fails, clear the packed-refs cache and retry:
```bash
rm -f .git/packed-refs
git fetch --prune origin
```

### Detached HEAD or wrong branch
```bash
git checkout main
git pull origin main
```
Then re-create or checkout the feature branch from Step 2.

### Merge conflict during rebase
```bash
git rebase --abort               # abandon the rebase
git checkout <BRANCH_NAME>       # go back to feature branch
git merge main                   # merge instead of rebase
# resolve conflicts, then:
git add -A
git merge --continue
```

### Push rejected (non-fast-forward)
Only happens if the branch was force-pushed upstream. Use `--force-with-lease` (safe):
```bash
git push --force-with-lease origin <BRANCH_NAME>
```

### PR already exists for this branch
```bash
gh pr view <BRANCH_NAME>         # get the existing PR URL
```
Print that URL as `PR_URL: <url>` and stop — do not open a duplicate.

### Authentication / permission errors
Check that `GH_TOKEN` is set in the environment:
```bash
echo $GH_TOKEN
gh auth status
```
If not authenticated, the task cannot proceed — report the error clearly.

### General rule
For any other git error: read the error message, fix the root cause, and re-run the failed command. Never skip a failing step or paper over it with `--no-verify` or `--force` unless explicitly listed above.
