# ADR 06: Qp-2 compliance

## Status
Approved

## Context
The VISOR project follows the continuous development lifecycle of Ansys products. As such, it needs to adhere to the QP-2 guidelines. The full Quality Procedure can be found [here](https://ansys.policytech.com/dotNet/documents/?docid=1452&app=pt&source=search).

## Responsible parties
QP-2 requires the following parties to be well defined, as person responsible for the different aspects of compliance. As pf December 2024, this is the list of people and roles.

| Role               | Person                |
|--------------------|-----------------------|
| Release Manager    | Palaniappan Nagappan  |
| Team Lead          | Marina Galvagni       |
| Test Lead          | Laurent Gerboud       |
| Documentation Lead | Paul Coinaud          |
| Product Manager    | Anna Kvarnstrom       |

## QP-2 Main Requirements
In this section, we address the main requirements of QP-2 and how the project fulfills them

### Tracebility
Both the code base and the project board of VISOR are hosted in the Ansys internal Github space. This ensures the following:
1. From a code point of view, being hosted on github allows for version control. Any audit would be able to quickly retrieve different versions of the code base and analyze the differences between versions. Single contributions are also tracked, making sure an audit could easily determine when a specific feature is entered into the code base.
2. From a project management point of view, the platform offers the Github project feature. Through this, the team can create issues, assign them, and track the code changes corresponding to each issue. Tests can also be associated with each Github issue, ensuring each feature is fully tested before release.
The Project associated with the VISOR code base can be found [here](https://github.com/orgs/ansys-internal/projects/420).

### Correct Issue Definition
Each issue has the following mandatory fields:
1. Title: brief description of the issue
2. Description: lengthy description of the issue, with details to explain its context
3. Acceptance Criteria: a set of criteria that need to be met in order for the issue to be considered Done.

Additional, optional fields are available to help with project management, such as iteration, links, third party software, and so on.

Labels are used to keep track of additional information. More notabily, the following labels:
1. beta: feature not fully released to the end user. As such, it does not require testing and documentation.
2. class3: used to mark a "class 3 defect". These are hidden defects and require a special level of attention for QP-2 - see later in the Bug section.
3. maintenance / research / technical: these issues do not require testing nor documentation assodiated with them. They track, respectively: maintenance work, research spikes, and technical work (such as code refactoring) that do not have any impact on the users experience
4. documentation: issues to describe documentation work. Does not need any testing associated with it
5. test case: issue describing a test case. It will be associated with a specific functional issue.
6. test log: issue describing the results of running a test case. These are necessary only for tests that are not automated.
7. functional: issue that describles a new functionality that the user will have access to. These issues need to have documentation and testing associated with them

There are multiple hierarchical levels of issues. While this structure isn't explicitly required by QP-2 and therefore not enforced, it helps to keep the work organized. This is done via issue types:
1. Epic: an epic is the highest level, describing a high-level functionality. A single epic can span multiple releases
2. Feature: a feature is a functionality that will be delivered in a single release cycle. It is testable and capable of adding value for the customer.
3. User Story: a single step in implementing a feature, that adds value that a user can verify independently from other user stories. It can be delived within a single iteration.
4. Task: a specific part of the work to implement a user story. Might not be testable on its own.

### Independent review
QP-2 requires an independent review process. This is enforced in the VISOR project via the following mechanism. No user can directly push new code into the main branch (branch-protection is active). In order for the code to be merged, it needs to be reviewed and approved by at least one person who has not contribuited in the code changes. This is automatically enforced by Github.

Moreover, issues can only be closed by someone who has not authored any of the PRs related to the issue itself. This ensures that each code change has been reviewed by an independent entity. This currently is not enforced by Github, but it is a practice inside the team. It can be verified by reviewing the history of each issue.

### Testing
As described above, we use labels to mark test cases and test logs. Each new functionality will have tests associated with it to, and they will be executed before the release. Note that this might be done at the Feature or at the User Story level, not necessarily at both.

A test case will contain all the instructions to reproduce the test. After being created, it needs to be reviewed by someone who is not its author. When executing it, at least one person between the author of the test case and the reviewer must not have been involved in developing the functionality that is being tested.

The test cases can be ran manually or as part of the automated tests system. These automated tests are run nightly and before each PR is merged into the code base. Note that for automated tests, no test logs are necessary.

### Bugs
Bugs are filed into the repository as issues with issue type: Bug. When filing a bug, the following fields are mandatory:
1. Title: short description of the issue.
2. Description: Lengthy description of the problem and how to reproduce it.
3. Severity: severity level of the bug. These are the levels:
    3a. Class 1: crash or major data loss
    3b. Class 2: Seriour problem
    3c. Class 2: Minor problem
    3d. Class 3: Hidden error. This is a separate type of bug that needs special attention (see [here](https://ansys.policytech.com/dotNet/documents/?docid=1338&app=pt&source=search)). It is reserved for bugs where the user gets a wrong output.
4. Fixed in: version that contains the bug fix

Please note that once a bug is fixed by the developers, it goes into "Resolved" mode. It can be moved from Resolved to Done only after it has been verified by a person who was not involved in the code changes for the bug fix. This person needs to verify that the code change addresses the bug and then move the bug report from Resolved to Done.

### OSS Usage and Security Scan
The VISOR project takes advantage of Third-Party Software components. As such, it needs to follow the procedures outlined in [QP-10](https://ansys.policytech.com/dotNet/documents/?docid=1228&app=pt&source=search) to ensure the integrated Third-Party Software satisfies functional and quality requirements.

The Team Lead will originate the request for use of a Third-Party Software Component. Independent reviewers assigned by the Released Management Unit will review and approve the requests. This is all done via the OSS Sharepoint form. OSR reviews will therefore be recorded on this Shareport [site](https://ansys.sharepoint.com/sites/OpenSourceSoftwareTrackingIntake/Lists/OSR%20Reviewed%20Components/AllItems.aspx).

Note that the VISOR project also takes advantage of an automated github workflow to scan third-party libraries to identify security concerns. These scans are executed nightly and at each PR push. Find more information [here](https://empowerment.dev.ansysapis.com/docs/devops/vulnerability-management/). Note that this mechanism also allows for an automatically created and retained list of Third-Party libraries used by VISOR.

### Release
As VISOR is part of the continuous development cycle, there are no set dates for the releases. These are created on a per-need basis, balancing the needs of the team and the requests from users (internal and external to Ansys).

In order for a release to be created, the following criteria needs to be met:
1. Stories and their tests are complete, reviewed and accepted
2. Resolved bugs are verified
3. Automated testing report has been created and published
4. Documentation is complete and reviewed
5. Regression tests have at least 90% passing rate
6. Total and priority bugs are within limits (20 bugs in total; 5 for Class 2 bugs; 0 for Class 3 bugs)
7. Third-Party Software components have been reviewed and accepted to be integrated
8. Known issues and limitations are approved
9. Legal Notices and Software Bill Of Material (SBOM) are up to date
