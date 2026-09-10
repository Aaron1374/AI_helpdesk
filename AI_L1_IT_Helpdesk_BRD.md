**AI ENGINEER NEW-JOINER PROGRAM**

**AI L1 IT Helpdesk**

_Business Requirements Document | Capstone Group Project_

| **Document Type**    | Business Requirements Document |
| -------------------- | ------------------------------ |
| **Project Duration** | 1 Week Group Project           |
| **Team Size**        | 4 AI Engineer Trainees         |
| **Status**           | Training Baseline / MVP Scope  |

**Training alignment:** This BRD is designed as the capstone for the four-week AI Engineer program. The scope intentionally exercises AI application development, backend/API engineering, QA, security, CI/CD, containerization, deployment and observability.

# 1\. Executive Summary

The AI L1 IT Helpdesk is an internal support platform designed to handle common first-line IT requests through a conversational assistant, controlled diagnostic tools and a ticketing workflow. The platform should resolve simple issues when confidence is high and escalate appropriately when human intervention is required.

**Business outcome:** Reduce repetitive L1 support work, improve first-response quality, make ticket context easier to hand over, and demonstrate responsible agentic AI with strong human escalation boundaries.

# 2\. Business Problem

A significant share of IT support demand consists of repeatable first-line issues. Users may need to wait for support staff, repeat information, or be routed manually before basic troubleshooting begins. A lightweight AI-assisted L1 layer can collect context, perform safe checks, guide troubleshooting and create well-structured tickets.

- Users may not know which support route to use.
- Support engineers spend time collecting basic details and categorizing tickets.
- Common checks can be repetitive.
- Duplicate or related incidents may be reported separately.
- Escalated tickets can lose conversation context if handover is manual.

# 3\. Business Objectives

1. Provide employees with a single support entry point.
2. Automate safe first-line triage and basic troubleshooting.
3. Create consistently categorized and prioritized tickets.
4. Detect when a problem should be escalated to a human or another support tier.
5. Provide L1 engineers with complete context when taking over.
6. Measure AI resolution, escalation and support workload.

# 4\. Stakeholders

| **Stakeholder**           | **Interest / Responsibility**                                                  |
| ------------------------- | ------------------------------------------------------------------------------ |
| Employee                  | Reports an issue and confirms whether the proposed resolution worked.          |
| L1 Support Engineer       | Handles assigned tickets, reviews AI suggestions and takes over conversations. |
| L2 Support Engineer       | Handles escalated issues outside L1 scope.                                     |
| Support Lead              | Reviews queues, priorities, analytics and escalation patterns.                 |
| Program Mentor / Assessor | Evaluates AI quality, security, testing and operational maturity.              |

# 5\. User Roles and Permissions

| **Role**            | **Key Permissions**                                                                            |
| ------------------- | ---------------------------------------------------------------------------------------------- |
| Employee            | Create/view own tickets; interact with AI; provide additional information; confirm resolution. |
| L1 Support Engineer | View assigned/queue tickets; review AI output; update tickets; respond; escalate.              |
| L2 Support Engineer | View escalated tickets; add diagnosis/resolution; close escalated tickets.                     |
| Support Lead        | View all queues/analytics; configure categories/priorities; review escalations.                |
| Administrator       | Manage users, queues and mock diagnostic integrations.                                         |

# 6\. Scope

## 6.1 In Scope

- Employee support portal and conversational assistant.
- Ticket creation, categorization, prioritization and lifecycle.
- Synthetic/mock diagnostic tools for common IT checks.
- AI troubleshooting and controlled tool use.
- Human escalation and conversation handover.
- L1 dashboard and basic support analytics.
- Authentication, authorization and audit logging.
- Automated testing, containerization, CI/CD, deployment and observability.

## 6.2 Out of Scope

- Real password administration or real identity-system changes.
- Real VPN restart or network-control operations.
- Real endpoint management or device control.
- Replacement for ServiceNow or another enterprise ITSM system.
- Autonomous execution of privileged or security-sensitive production changes.

**Implementation constraint:** All diagnostic actions may be represented by mock APIs. Example functions include check_vpn_status(), check_application_status(), check_account_status() and check_device_status().

# 7\. Business Process

| **Stage**                    | **Business Outcome**                                                        |
| ---------------------------- | --------------------------------------------------------------------------- |
| 1\. User reports issue       | The assistant captures the initial problem statement.                       |
| 2\. Clarify                  | The assistant asks only the questions needed for safe L1 triage.            |
| 3\. Classify / prioritize    | A category and priority are suggested with reasons.                         |
| 4\. Diagnose                 | The assistant uses safe diagnostic tools where appropriate.                 |
| 5\. Resolve or create ticket | A simple issue is resolved, or a ticket is created with useful context.     |
| 6\. Escalate when needed     | Complex, sensitive or unresolved issues move to human/L2 support.           |
| 7\. Confirm resolution       | The user confirms whether the proposed action worked.                       |
| 8\. Analyze workload         | Support leads review ticket volumes, AI resolution and escalation patterns. |

# 8\. Functional Requirements

| **ID** | **Requirement**         | **Business Requirement**                                                                                                  |
| ------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| FR-01  | Support request         | Users shall be able to submit an IT issue through the portal or assistant.                                                |
| FR-02  | Clarification           | The assistant shall ask relevant follow-up questions before taking action when required.                                  |
| FR-03  | Categorization          | The system shall assign a suggested category such as Access, Network, Hardware, Software, Email, Security or Application. |
| FR-04  | Priority                | The system shall suggest Critical, High, Medium or Low priority with a rationale.                                         |
| FR-05  | L1 troubleshooting      | The AI shall provide guided first-line troubleshooting for supported issue types.                                         |
| FR-06  | Diagnostic tools        | The assistant shall use controlled tools to check mock system status rather than guessing.                                |
| FR-07  | Ticketing               | The system shall create and update tickets with user, category, priority, status, history and resolution details.         |
| FR-08  | Duplicate detection     | The system should identify likely duplicate or related incidents using existing ticket data.                              |
| FR-09  | Escalation              | The assistant shall escalate low-confidence, sensitive, unsupported or unresolved issues to human support.                |
| FR-10  | Handover                | An L1/L2 engineer shall be able to see the relevant conversation and diagnostic context when taking over.                 |
| FR-11  | Resolution confirmation | Users shall be able to confirm or reject a proposed resolution.                                                           |
| FR-12  | Dashboard               | Support staff shall have views of open, escalated, resolved and prioritized tickets plus basic AI/support metrics.        |

# 9\. AI Requirements

- The AI must not invent system status, fixes or policies.
- The AI should use diagnostic tools when available instead of guessing.
- The AI should ask clarifying questions when the initial request is ambiguous.
- The AI should state uncertainty when evidence is insufficient.
- The AI should recognize security-sensitive or privileged requests and escalate them.
- State-changing or privileged actions shall require authorization and an appropriate confirmation step.
- The assistant should produce a concise handover summary when escalating a ticket.

# 10\. Security Requirements

- Users shall only see their own tickets unless their role permits broader access.
- Support roles shall be enforced server-side, not only in the UI.
- Protected diagnostic or state-changing tools shall require authorization.
- Input validation and secure API practices shall be applied to ticket and tool endpoints.
- Audit records shall capture important actions, including escalation and privileged operations.
- The team shall test prompt-injection attempts that try to expose unauthorized ticket information or invoke restricted actions.

# 11\. Quality and Testing Requirements

| **Area**      | **Minimum Evidence**                                                                                               |
| ------------- | ------------------------------------------------------------------------------------------------------------------ |
| Unit testing  | Ticket-state rules, prioritization/categorization logic and core service functions.                                |
| API testing   | Ticket CRUD, authorization, validation, escalation and tool endpoints.                                             |
| UI/E2E        | Employee issue → AI triage → ticket → support handover/closure.                                                    |
| Performance   | A basic concurrent request/load test on selected support APIs.                                                     |
| Security      | Role separation, unauthorized-ticket access, injection/validation and dependency/security checks.                  |
| AI evaluation | Synthetic scenarios covering easy resolution, ambiguity, escalation, duplicate detection and unsupported requests. |

# 12\. Operational Requirements

- Core services shall be containerized and deployable to a repeatable training environment.
- A CI pipeline shall run automated tests and security/dependency checks.
- The deployment should use the container/orchestration and GitOps practices covered in the training where practical.
- The system shall expose service health information.
- Important AI, API, tool and ticket events shall be logged.
- The team shall be able to diagnose a deliberately failed component using observability evidence.

# 13\. Synthetic Data and Mock Tools

Use synthetic support history and mock systems so the trainees can demonstrate realistic behavior without access to real corporate systems.

| **Dataset / Tool**       | **Examples**                                                                                        |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| Synthetic ticket history | VPN problems, password expiry, application outages, email issues, device issues, software requests. |
| Account check            | check_account_status(user_id)                                                                       |
| VPN check                | check_vpn_status(user_id)                                                                           |
| Application check        | check_application_status(application_name)                                                          |
| Device check             | check_device_status(device_id)                                                                      |
| Ticket search            | search_similar_tickets(query, user_id/category)                                                     |

# 14\. Example Business Scenarios

| **Scenario**                              | **Expected Behavior**                                                                                                         |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Forgotten password                        | Classify as Access; explain the safe reset path or call a simulated reset workflow; do not expose secrets.                    |
| VPN not connecting                        | Ask clarifying questions, check mock VPN status, guide troubleshooting, create/escalate a ticket if unresolved.               |
| HR portal unavailable                     | Check application status; if service is down, identify likely broader incident and escalate rather than pretending to fix it. |
| Vague request: "My laptop is not working" | Ask for the minimum clarifying information needed before choosing a troubleshooting path.                                     |
| Repeated VPN complaint                    | Search existing tickets/incidents and identify likely duplicates or a shared issue.                                           |
| Sensitive request                         | Refuse or escalate requests involving privileged access, secrets or another employee's private information.                   |

# 15\. Non-Functional Requirements

| **NFR**         | **Expectation**                                                              |
| --------------- | ---------------------------------------------------------------------------- |
| Security        | Least-privilege access and strict tenant/role boundaries.                    |
| Reliability     | AI failure must not destroy or hide ticket data.                             |
| Maintainability | Separate AI orchestration, ticketing domain logic and mock integrations.     |
| Observability   | Errors, tool calls, escalations and service health should be traceable.      |
| Usability       | An employee can describe an issue without knowing IT terminology.            |
| Human control   | AI assists L1 work but escalates rather than forcing unsupported automation. |

# 16\. Acceptance Criteria

| **ID** | **Requirement**     | **Acceptance Evidence**                                                                                  |
| ------ | ------------------- | -------------------------------------------------------------------------------------------------------- |
| AC-01  | Issue intake        | An employee can start a support request and the system records it.                                       |
| AC-02  | Clarification       | The AI asks an appropriate follow-up question for at least one ambiguous issue.                          |
| AC-03  | Classification      | Category and priority are proposed with a visible rationale.                                             |
| AC-04  | Diagnostic tool     | The AI uses at least one mock diagnostic function to obtain real system state.                           |
| AC-05  | Simple resolution   | At least one seeded L1 issue reaches a successful AI-assisted resolution flow.                           |
| AC-06  | Ticket creation     | A non-resolvable issue becomes a structured support ticket with conversation context.                    |
| AC-07  | Duplicate detection | The system identifies a seeded related/duplicate incident.                                               |
| AC-08  | Escalation          | An unsupported or sensitive request is escalated to human support.                                       |
| AC-09  | Handover            | An L1/L2 engineer can review the full context and continue the case.                                     |
| AC-10  | Security            | A user cannot access another user's ticket and restricted tools cannot be invoked without authorization. |
| AC-11  | Automated quality   | The repository/pipeline contains unit, API, UI/E2E, performance and security evidence.                   |
| AC-12  | Observability       | The team can explain a failed tool/service interaction from logs/health information.                     |

# 17\. Final Demonstration Scenario

1. Employee A reports: "I forgot my password." Demonstrate a safe, simple L1 resolution using a simulated workflow.
2. Employee B reports: "The HR portal is not working." The AI checks the application status and discovers a simulated outage; it creates/escalates a ticket with evidence.
3. Employee C reports: "VPN stopped working after I changed my network." The AI asks clarifying questions, runs safe checks and escalates if it cannot confidently resolve the issue.
4. Show the L1 engineer view and demonstrate takeover using the conversation and diagnostic context.
5. Submit a prompt-injection attempt requesting another employee's ticket data and show that authorization boundaries remain intact.
6. Introduce a controlled service/tool failure and use observability information to diagnose it.
7. End by showing ticket analytics and the AI-resolution/escalation metrics.

# 18\. Recommended Team Ownership

| **Trainee** | **Primary Ownership**      | **Expected Integration**                                                |
| ----------- | -------------------------- | ----------------------------------------------------------------------- |
| Member 1    | AI / Conversation          | Agent orchestration, classification, troubleshooting flows, evaluation. |
| Member 2    | Backend / Ticketing / Auth | Ticket domain, APIs, state machine, permissions.                        |
| Member 3    | QA / Security              | Scenario matrix, API/E2E/performance/security tests, AI red-team cases. |
| Member 4    | DevOps / Platform          | CI/CD, containers, deployment, observability, reliability checks.       |

# 19\. Deliverables

- Working application and source repository.
- Architecture diagram and concise technical design.
- API/tool contract documentation.
- Synthetic dataset and mock integration definitions.
- Automated test report and security evidence.
- CI/CD pipeline and deployment artifacts.
- Operations/runbook notes for common failure modes.
- Final presentation and live scenario demonstration.

# 20\. Success Measures

- Simple L1 issues can be resolved faster with less repetitive human effort.
- Escalations contain useful context instead of forcing the engineer to restart diagnosis.
- The AI does not invent system state and knows when to stop.
- Unauthorized users cannot access restricted tickets or tools.
- The platform can be tested, deployed and observed through a repeatable workflow.

# 21\. Training Alignment Note

This BRD intentionally maps the capstone to the supplied AI Engineer training program, which establishes a common engineering baseline across AI development, backend integration, quality engineering, CI/CD, deployment and monitoring. The project also provides practical opportunities to demonstrate secure APIs, automated testing, agent/tool use, containerization and operational troubleshooting.