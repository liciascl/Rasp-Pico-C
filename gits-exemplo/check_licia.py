#!/usr/bin/env python3

import subprocess
import os
from datetime import datetime
import pandas as pd
from tqdm import tqdm


def run_command(command):
    """Runs a command and returns its output."""
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
        return output
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {command}")
        print(e.output)
        return e.output


def run_embedded_check(repo, date, counter):
    """
    Runs cppcheck on all .c files found in the repository directory and subdirectories.
    """
    c_files = []
    for root, _, files in os.walk(repo):
        for file in files:
            if file.endswith('.c'):
                c_files.append(os.path.join(root, file))

    ret = None
    for path in c_files:
        cppcheck = f"cppcheck -i{repo}/ASF -i{repo}/oled -i{repo}/config --enable=all {path} --dump 2> /dev/null"
        run_command(cppcheck)
        
        command = f"python3 checker2/check.py {path}.dump --xml"
        result = run_command(command)

        if result:
            ret = result

    return ret


def parse_issue(issue_str):
    parts = issue_str.split(':', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, None


def extract_data(repo):
    # Check if the main branch exists before checking out
    #branches = run_command(f"git -C {repo} branch --list main")
    #if 'main' not in branches:
        #print(f"Warning: 'main' branch not found in {repo}. Skipping this repository.")
        #return []

    #run_command(f"git -C {repo} checkout main -f")
    commits = run_command(f"git -C {repo} rev-list --all").split()
    commits.reverse()
    data = []

    commit_counter = 0
    for commit in commits:
        run_command(f"git -C {repo} checkout {commit} -f")
        commit_date_str = run_command(f"git -C {repo} log -1 --format=%cI").strip()
        commit_msg = run_command(f"git -C {repo} log -1 --format=%s").strip()

        try:
            date = datetime.fromisoformat(commit_date_str)
        except ValueError as e:
            print(f"Error parsing date: {commit_date_str} in commit {commit}. Error: {e}")
            continue

        result = run_embedded_check(repo, date, commit_counter)
        if result is not None:
            issues = [parse_issue(issue) for issue in result.strip().split('\n') if issue]
        else:
            issues = [(None, None)]

        for issue in issues:
            try:
                if issue[0] is not None:
                    data.append([repo, date.isoformat(), commit_msg, commit_counter, commit, issue[0], issue[1]])
            except Exception as e:
                print(f"Error processing issue: {e}")
        commit_counter += 1

    #run_command(f"git -C {repo} checkout main -f")

    return data


if __name__ == "__main__":
    rpath = "codes"
    repos = [os.path.join(rpath, repo) for repo in os.listdir(rpath) if os.path.isdir(os.path.join(rpath, repo))]
    repos.sort()

    all_data = []
    for repo in tqdm(repos, desc="Processing Repositories"):
        if repo == '.git':
            continue
        data = extract_data(repo)
        all_data.extend(data)

    if all_data:
        df = pd.DataFrame(all_data, columns=['repo_id', 'Date', 'Commit_msg',
                                             'Commit_counter', 'Commit_hash', 'Issue', 'Description'])
        df.set_index('repo_id', inplace=True)
        print(df)
        df.to_csv('report.csv')
    else:
        print("No data to save.")

