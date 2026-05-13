Preparation

- Further studies on agentic solutions (there are many things using that name and they are conceptually different)  
- [https://gist.github.com/burkeholland/0e68481f96e94bbb98134fa6efd00436](https://gist.github.com/burkeholland/0e68481f96e94bbb98134fa6efd00436) seems to be the closest to what I want it to be. Multi subagents and an orchestrator. Runnable in vscode and copilot cli (later for scale).  
- More experimental and more code+llm instead of LLM+code (in terms of what has priority): [https://github.com/VRSEN/agency-swarm](https://github.com/VRSEN/agency-swarm)

Background

- Active Ubuntu releases have the versions of their packages locked, for newer versions one generally needs to upgrade to a newer Ubuntu release   
- Fixes can be applied to resolve security vulnerabilities or functional issues, but they have to follow the [SRU principles](https://documentation.ubuntu.com/project/SRU/explanation/principles/) of 1\. Minimise regressions 2\. User confidence 3\. Maintain usefulness  
- A few upstream projects have stable minor releases that aim for the same principles, in those cases an exception is made and those stable minor releases can be uploaded to Ubuntu.  
- But for projects that do not have stable upstream minor releases Ubuntu relies on the following steps:  
  - a) Reporting of issues  
  - b) Finding a fix for that issue in the upstream project  
  - c) Balancing the impact of that change with its risk to justify the change  
  - d) Find a way to test and verify that particular change  
  - e) Prepare the process paperwork  
  - f) Prepare the upload  
  - g) test builds  
  - h) follow up on builds  
  - i) follow up on automated tests  
  - j) verifying the fix  
- An upgrade to a later release shall not regress the user, therefore only fixes present in subsequent releases can be applied

Goal:

- Eliminate the need for “a) Reporting of issues” and “b) Finding a fix for that issue in the upstream project” by proactively identifying changes in the upstream repository that qualify for an SRU  
- Automate the following steps out of the overall effort:  
  - c) Balancing the impact of that change with its risk to justify the change  
  - d) Find a way to test and verify that particular change  
  - e) Prepare the process paperwork  
  - Other steps are left out for handling by other tools or later additions  
- Input shall be a Ubuntu source package name like “dovecot”, a target release (like 24.04 noble) and a source release (like 26.04 resolute)

General constraints:

- Keep context consumption in mind and try to pick the most reasonable model for the given task balancing ability and cost  
- Log design decisions (like which agent framework or style was chosen and why) in a file and keep it updated when those change while iterating on it in the plan  
- This shall be an agentic solution, to keep tasks isolated, with more context available for that task and room specialization and ability for that task  
- Agents shall use code where deterministic code can do the job and AI where it can’t
- Mark source files created with "Copyright 2026 Canonical Ltd." and "SPDX-License-Identifier: GPL-3.0-only"

Roles:

- “Stabilizer-orchestrator”  
  - Oversees the whole process from start to end running subagents for their specific tasks.  
  - Keep track of what changes were evaluated and why they have been excluded to finalize the overall work with a report  
- “Stabilizer-version-identifier”  
  - Identifies versions present in  in “target release” and “source release”  
    - Using launchpad api calls or the \`rmadison\` tool to get the packaging versions  
    - Derives the upstream version from that (what comes before the \`-\` in the version  
- “Stabilizer-get-repository”  
  - Detects the upstream git repository  
    - Get the package source via `git ubuntu clone $packagename`  
    - Process debian/watch and the `homepage` field in debian/control to see where the project comes from  
    - Use that info, web search and knowledge in the LLM toIdentify the upstream repository  
- “Stabilizer-identify-commit-range”  
  - Finds the tags or commits representing the formerly identified versions of “target release” and “source release” in the identified repository  
- “Stabilizer-identify-safe-changes”  
  - Checks the commits that got added between the identified tags and identifies which would be safe fixes for an SRU (no behavior change, balance the impact of that change with its risk to justify the change)  
  - Returns a list of changes, those might be individual commits, or groups of commits if multiple belong together to address a single case  
  - Also Returns the reasoning (impact: why it is needed; regression-risk: why it is safe to be applied) associated to the change it belong to  
- “Stabilizer-identify-applicable-fixes”  
  - There will be other projects that focus on overcoming backporting challenges, for now we’d only consider patches that apply cleanly  
  - Patches depend on former patches that are applied, those we evaluate in this process and those already applied in the packaging  
  - To get a repository to try this use  
    - `git ubuntu clone $package` \- to get a repository of the packaging in Ubuntu  
    - In there `git checkout pkg/applied/${release}-devel` to get a git state that has all changes of the packaging already applied  
    - Add the identified upstream repository as extra remote and fetch it  
    - Evaluate the considered changes if they would cleanly apply by cherry-picking on top, aborting failed cherry picks to get back to a good state before trying the next  
  - Returns the reduced list (only those that apply well) of changes that are considered  
- “Stabilizer-identify-testable-changes”  
  - For each identified set of changes that would be a safe fix for an SRU and apply, work out how that change could be tested  
  - Understand the target packages usage and setup  
  - Map the change to a test case describing how to run the software to trigger that path  
  - Describe what will happen without the fix and how it will behave with the fix applied  
    - Test if we should use applied branches for that or how to make it understand to use quilt  
    - Those that do not fit to be sorted out \- complex backports/forward ports are parts of other teams items as well as hackathon ideas. No investing much into “making them apply” here  
  - Returns the reduced list (only those that can be tested well) of changes that are considered  
  - Also returns the test-description associated to the change it belongs to  
- “Stabilizer-prepare-paperwork”  
  - For the remaining changes that were identified to be safe for the SRU policy, applicable cleanly and testable prepare SRU paperwork  
  - Follow the required template: [https://documentation.ubuntu.com/project/SRU/reference/bug-template/](https://documentation.ubuntu.com/project/SRU/reference/bug-template/)   
  - Use the info reported by other agents to build this:  
    - From “Stabilizer-identify-safe-changes”: reasoning (impact: why it is needed; regression-risk: why it is safe to be applied)  
    - From “Stabilizer-identify-testable-changes”: Test-description  
    - The associated change commit (or group of commits)  
  - Put those into one file each for later re-use but since the changes might be order dependent ensure this order is retained  
- “Stabilizer-report”  
  - Report about the identified potential fixes to active Ubuntu releases  
  - Create a summary and point to the files with the prepared SRU templates


– – –  – – –   
For today’s scope we skip the next steps like actually packaging the change, test building and uploading it. Many others hunt for that, reduce overlap and focus on what makes this approach likely more unique

- Create proposes upload  
  - Stabilizer-create-bugs  
    - Create and document bugs (Fake this for now and blast it into text files for one each)  
  - Stabilizer-create-upload  
    - Create proper dquilt style patches with headers, changelog entries and such  
  - stabilizer-create-PPA  
    - Create PPA  
    - Upload there for builds  
  - stabilizer-run-tests  
    - Run tests on the PPA after build

