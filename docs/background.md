# Background, problem, and core ideas

This is the product story. How the models work is in [ai-guide.md](ai-guide.md). How a request moves through the files is in [code-guide.md](code-guide.md). Runtime decisions are in [architecture.md](architecture.md).

## Who it is for

The primary user is an **employee**, not an HR admin.

They need to:

1. Ask what a policy says and which document that answer came from
2. See **their own** leave balance, not a coworker’s
3. Prepare a leave request without the system deciding that leave is approved

A monitoring admin exists only to view metrics and alerts. They are not the leave happy path.

The product uses synthetic demo people (Alya, Bima, a monitoring admin). It is not framed as a named company assignment in the UI.

## The problem

HR policy lives in documents that change (version, effective date). Employees still ask the same questions in chat: how many days, when a doctor’s note is needed, whether they can take leave next month.

Three things go wrong if you treat that as “just ask a chatbot”:

| Failure | Why it hurts |
| --- | --- |
| An answer with no source | The employee cannot check the rule, and you cannot audit what the model used |
| An answer from memory or a pasted prompt | The policy file can change tomorrow; the prompt or the weights stay wrong |
| A leave row written too early | The model may invent dates, skip notice rules, or imply the leave is already approved |

Identity makes it worse. A chat message can name another employee. If the tool accepts that name as an id, private balance and leave data leak.

So the product problem is not “make a fluent HR bot.” It is: **grounded policy answers for the signed-in person, and leave that stays pending until a human decides.**

## What success looks like

Three rules must hold. In evaluation they are hard gates: any one failure is a release NO-GO.

1. A citation is kept only if that document was retrieved on **this** turn
2. Balance and leave rows use the **bearer token**, never an employee id from the user text
3. Confirm creates `pending_manager_review` only. There is no approve tool

Soft quality (overall pass rate, recall) can be imperfect and still GO. These three cannot.

## Core ideas

```text
Versioned policy documents
        │
        ▼
Chunk and embed once (seed)
        │
        ▼
On each question: retrieve a few chunks (RAG)
        │
        ▼
Agent may call tools (search, balance, prepare, confirm, ticket)
        │
        ▼
Python decides: citation ok? whose data? may we write?
        │
        ▼
Leave row only after confirm → pending_manager_review
```

| Idea | Meaning |
| --- | --- |
| RAG, not prompt dump | Policies stay in Markdown with id, version, and effective date. A question retrieves a few chunks. A missing chunk means abstain. |
| Chunk by section | Split on `##` headings so one section is one searchable unit. The whole file is too coarse. |
| The model asks; Python runs | The agent names a tool. Identity and writes stay in code you can test. |
| Domain for writes | `domain.py` checks dates, balance, overlap, notice. Search explains; domain refuses a bad prepare. |
| Two-step leave | Prepare stores a proposal. Confirm stores a pending request. A person still approves. |
| Untrusted documents | Retrieved policy text is data. A sentence that says “ignore the system” is not a new instruction. |
| One agent, one trace | One loop, one redacted trace. Easier to evaluate than a multi-agent graph. |

## What we refused

| Turned down | Used instead |
| --- | --- |
| Paste every policy into the system prompt | Retrieve versioned chunks per question |
| Fine-tune the policy into the model weights | Keep the fact in a document you can open and cite |
| Let the model query Postgres or pass `employee_id` | Bearer token on the server; tools bound to that id |
| Approve leave in the assistant | `pending_manager_review` only; human approves later |
| Several agents for search, leave, and tickets | One bounded agent and one trace |
| Vector search only | Lexical + vector, fuse, then keyword rerank |
| Trust the model’s citation marker | Keep the marker only if it was retrieved this run |

## What is out of scope (this demo)

- Real employee data or production SSO
- Automated leave approval
- Legal advice or medical triage
- An admin editor that auto-extracts prepare rules from Markdown without a human check

Those limits are intentional. The demo proves grounding, identity binding, and confirmation. It does not claim to be production HR.

## Where to go next

| Topic | Doc |
| --- | --- |
| Flows and modules | [project-guide.md](project-guide.md) |
| Models, RAG, tool loop | [ai-guide.md](ai-guide.md) |
| File-by-file request path | [code-guide.md](code-guide.md) |
| Trust boundaries and ADR | [architecture.md](architecture.md) |
| Residual risks | [risks.md](risks.md) |
