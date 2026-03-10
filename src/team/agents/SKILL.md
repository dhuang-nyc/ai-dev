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
