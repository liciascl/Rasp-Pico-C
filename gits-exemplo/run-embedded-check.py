#!/usr/bin/env python3

import subprocess
import os
from datetime import datetime
import json
import xml.etree.ElementTree as ET
from tqdm import tqdm
import pandas as pd
from concurrent.futures import ThreadPoolExecutor


def run_command(command):
    """Runs a command and returns its output."""
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
        return output
    except subprocess.CalledProcessError as e:
        print(e.output)
        return e.output


def run_embedded_check(repo, date, counter):

    get_folders_with_main = (
        f"find {repo} -type f -name 'main.c' | sed -r 's|/[^/]+$||' |sort |uniq"
    )

    result = os.popen(get_folders_with_main).read()
    mains = [y for y in (x.strip() for x in result.splitlines()) if y]
    tree = ""

    ret = None
    for path in mains:
        cppcheck = f"cppcheck -i{path}/ASF -i{path}/oled -i{path}/config --enable=all {path}/main.c --dump 2> /dev/null"
        run_command(cppcheck)
        command = f"python3 checker2/check.py {path}/main.c.dump --xml" #2> reports/{repo}.{counter}.checker.xml"
        ret = run_command(command)

    return ret


def parse_issue(issue_str):
    parts = issue_str.split(':', 1)
    if len(parts) == 2:
        return (parts[0], parts[1])
    return (None, None)

def extract_data(repo):
    checkout = run_command(f"git -C {repo} checkout main -f")
    commits = run_command(f"git -C {repo} rev-list --all").split()
    commits.reverse()
    data = []
    print(repo)

    commit_counter = 0
    for commit in commits:
        run_command(f"git -C {repo} checkout {commit} -f")
        commit_date_str = run_command(f"git -C {repo} log -1 --format=%cI").strip()
        commit_msg = run_command(f"git -C {repo} log -1 --format=%s").strip()

        date = datetime.fromisoformat(commit_date_str)
        result = run_embedded_check(repo, date, commit_counter)
        if result is not None:
            issues = [parse_issue(issue) for issue in result.strip().split('\n')]
        else:
            issues = [(None, None)]
        for issue in issues:
            try:
                if issue != (None, None):
                    data.append([repo, date.isoformat(), commit_msg, commit_counter, commit, issue[0], issue[1]])
            except:
                breakpoint()
        commit_counter += 1


    checkout = run_command(f"git -C {repo} checkout main -f")

    return data


if __name__ == "__main__":
    rpath = "codes"  
    repos = [os.path.join(repo) for repo in os.listdir(rpath) if os.path.isdir(os.path.join(rpath, repo))]
    repos.sort()

    all_data = []
    cnt = 0
    for repo in tqdm(repos, desc="Processing Repositories"):
        if repo == '.git':
            continue
        repo = os.path.join(rpath, repo)
        data = extract_data(repo)
        all_data.extend(data)

    df = pd.DataFrame(all_data, columns=['repo_id', 'Date', 'Commit_msg',
                                         'Commit_counter', 'Commit_hash', 'Issue', 'Description'])
    df.set_index('repo_id', inplace=True)
    print(df)

    df.to_csv('report.csv')
