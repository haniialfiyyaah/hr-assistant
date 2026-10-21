# Presentation script

English deck for the live class slot: **10–15 minutes, including questions**. Talk for about 9–10 minutes (including a short RAG explanation), demo inside that, then leave the rest for questions.

Slides: [HR Policy and Leave Assistant](https://docs.google.com/presentation/d/1UHfhCbEBuUKPVSETNiPZQqn2IGAdqrWrk-RW8NSDV6c/edit)

Open presenter view. Each slide’s speaker notes match the blocks below. Sign in as Alya before you start (`alya@demo.local` / `demo`). Keep a second tab on `outputs/evaluation_report.md` only if someone asks about evaluation.

Do not improvise dates. Do not type a diagnosis. Do not use “next week”.

---

## 1. Title

**Point.** Name the product and the promise in one sentence.

**Show.** The title slide only. App is already open behind it, on New Chat.

**Understand.** You are presenting a product, not reading the assessment. The promise is two things: a policy answer you can trace, and leave the system never approves.

**Say.** “This is an HR assistant for employees. It answers policy questions from the documents, and it can prepare leave. It never approves that leave. A person still does. I’ll show the problem, how the policies and RAG work, a live demo, then the limits and what I would do next. About ten minutes, then questions.”

---

## 2. Employees need an answer they can trace

**Point.** The user and the three jobs.

**Show.** Three cards: policy, own balance, leave proposal.

**Understand.** The user is an employee, not HR admin. Admin is only for monitoring, and you will not demo admin unless they ask.

**Say.** “An employee asks three kinds of things. What does the policy say, and which document. What is my balance, not someone else’s. And please prepare leave. The assistant may prepare. It must not decide the leave is approved.”

---

## 3. Three rules that must hold

**Point.** The success criteria the rest of the talk has to hit.

**Show.** Cards 01, 02, 03.

**Understand.** These are the hard gates. If any one fails, the release is NO-GO even when the other answers look good.

1. A citation is kept only if that document was retrieved on this turn.
2. Identity comes from the bearer token. `get_my_leave_balance` has no employee id argument.
3. Confirm writes `pending_manager_review`. There is no approve tool.

**Say.** “I judge the system on three rules. The citation has to be a document retrieved on that turn. The balance has to be the signed-in person, even if they name someone else. And confirm creates a pending request. The status is pending manager review. The system cannot set approved.”

---

## 4. Retrieve. Then let Python decide.

**Point.** Why RAG plus a bounded agent plus domain code, and what you refused.

**Show.** Three cards: not in the prompt, not in the weights, not the model’s write.

**Understand.**

- Pasting the policy into the prompt goes stale and cannot abstain when a section is missing.
- Fine-tuning hides the fact in the weights, so you cannot point at the paragraph.
- The model is allowed to ask for a tool. Python runs it. `domain.py` accepts or refuses a prepare even if the model misreads the policy.
- One agent, one trace. Not several agents.

**Say.** “I did not paste the policies into the prompt, and I did not fine-tune them into the model. Each question retrieves a few versioned chunks. If the chunk is not there, the answer abstains. The model can ask for a tool. It cannot write the leave row by itself. Domain code checks the dates, the balance, and overlap. Search explains the rule. The code decides the write.”

If they ask “why both?”: the markdown can change, and a skipped search must not create a bad proposal. The cost is that the numbers in `domain.py` must be updated when the policy numbers change.

---

## 5. Policies are versioned Markdown

**Point.** What the documents are, before you say “RAG”.

**Show.** Three cards: what they are, how they are cut, untrusted text.

**Understand.** Policies live in `data/policies/` as Markdown. Front matter has `document_id`, `version`, `effective_date`. `chunk_policy` in `src/setup_lab.py` splits on `##` so each section is one searchable chunk (for example two sections of `HR-LEAVE-001`). The chunk text is untrusted data. A line that says “ignore the system” is never a new instruction.

**Say.** “The knowledge is not in the model. It is in policy Markdown files: leave, sick, remote, eligibility, privacy. Each file has an id, a version, and an effective date. At seed I split each file on section headings into chunks, so one section is one unit I can retrieve. Those chunks are data. They are never treated as system instructions.”

---

## 6. Chunk once. Retrieve a few. Then answer.

**Point.** How RAG works here, in four steps. Keep this under 90 seconds.

**Show.** Cards 1–4.

**Understand.**

1. At seed, each chunk is embedded once into Postgres (`pgvector` plus a `tsvector` for words).
2. At chat time, embed the **question** only. Lexical search catches exact words. Vector search catches similar meaning.
3. Reciprocal rank fusion merges the lists. A keyword rerank lifts matching chunks. Keep `top_k` (usually 3–5). The agent must cite a retrieved document id, or abstain.
4. Two models: the embedding model finds similar text; the agent model writes the sentence and chooses tools.

Redis may cache a search result for about 15 minutes. It is not the source of truth.

**Say.** “RAG here means retrieve, then generate. At seed I embed every chunk once into Postgres. When someone asks a question, I embed that question, run a word search and a meaning search, fuse them, and keep a few chunks. The agent model then answers from those passages only. If the citation is not in what I retrieved, I abstain. Embeddings find similar text. The agent model writes the sentence.”

If they ask “what is a chunk?”: a section of a policy file, not the whole file, so one answer can cite one document without dragging every unrelated rule into the prompt.

---

## 7. One chat message

**Point.** The path of a single turn, in the order the code runs.

**Show.** Steps 1–4. If you have the architecture diagram open, do not switch to it unless they ask. This slide is enough.

**Understand.** `AgentService.run` in `src/agent.py`. The browser sends text and a bearer token, never an employee id. History is the last 12 sentences, not old tool JSON. Redis is only a retrieval cache.

**Say.** “One message does four things. The token is hashed and becomes the employee. The model asks for a tool, usually search. Python runs that tool and then checks the answer: citation, balance name, confirm. Postgres stores the two messages and a redacted trace. Redis, if it is up, only caches search.”

---

## 8. The model asks. Python decides.

**Point.** The split you must be able to defend in questions.

**Show.** Two columns.

**Understand.**

| The model | Python |
| --- | --- |
| Which tool, the wording, the citation it types | Whether the tool runs, whose data, whether the citation was retrieved |

A sentence inside a policy file is data in the tool result. It is not a new instruction. There is no tool that lists tokens or reads another employee.

**Say.** “The model chooses the tool and writes the sentence. Python decides if that tool is allowed, whose balance was loaded, and whether the citation is real. If the model types a document id that was not retrieved, I drop it and abstain. If the user says confirm and the model forgets the tool, Python still confirms that person’s open proposal.”

---

## 9. Four things I will show

**Point.** The live demo. Leave this slide up only for five seconds, then switch to the app.

**Show.** The app, signed in as Alya, New Chat. About four minutes.

**Understand.** Say one sentence, then type. Do not narrate every token.

1. “How many annual leave days do permanent employees get?” Expect `[HR-LEAVE-001]`. Open the trace. The chip is the citation that passed. The inspector list can be longer. That is retrieved versus cited.
2. “What is my leave balance?” Alya’s annual balance is 8. Then: “Show EMP-002’s leave balance.” The numbers stay Alya’s. The tool has no employee id.
3. New chat. “Prepare annual leave from 2026-11-02 to 2026-11-03.” Expect a proposal, not a leave row. Click Confirm. The thread shows the word confirm. Status is `pending_manager_review`. Confirm again. Same request, no second row.
4. “What is the travel subsidy to Mars?” Expect abstain.

If the model is slow, wait. p50 was about 3 seconds. If step 3 fails the notice rule, do not invent a closer date. Say the dates are the ones that clear three business days from today, and show the saved evaluation instead of retrying a new date.

**Say, before you type.** “I’ll do this as Alya. First a policy answer with a citation. Then her balance, and a request for someone else’s. Then a real prepare and two confirms. Then a question the policies do not contain.”

---

## 10. Obstacles we hit

**Point.** Kendala yang dihadapi. Honest constraints from building the assistant.

**Show.** Three cards.

**Understand.**

- Multi-turn leave was hard. Short follow-ups like “2 days” or “annual” often lost the leave thread and the model abstained.
- The notice rule and the sick-document rule live in the policy markdown and again in `domain.py`. A policy edit does not update the gate by itself.
- Every model call carries system rules, a calendar block, and chat history. Short questions still cost a lot of tokens.
- (Optional if asked.) The model can invent dates or name the wrong employee. That is why prepare drips fields, confirm is separate, and balance answers get an attribution rewrite.

**Say.** “The hardest part was not the happy path. It was keeping leave intake across short replies, keeping code gates aligned with the policy text, and paying for a full prompt on every turn.”

---

## 11. What I would ship next

**Point.** Future work. What I would build next, not what already ships.

**Show.** Three cards.

**Understand.**

- Analytics: we already have monitoring-admin metrics and alerts on traces. We do **not** yet have employee-activity analytics (leave patterns, team activity for managers). That is the next analytics layer.
- Slimmer LLM input: trim history, shorten instructions, attach the calendar only when leave intake needs it.
- Fuller HR system: manager approval flows, people admin, and richer HR workflows beyond self-serve chat.

**Say.** “Next I would add activity analytics for managers, slim the model input, and grow this toward real HR management, not only employee chat.”

---

## 12. Questions

**Point.** Stop talking. Let them choose the proof.

**Show.** The app, still on the last demo thread, so you can open the trace immediately.

**Understand.** Likely questions and the one-sentence answer:

- Why RAG instead of the prompt? The policy has a version and a date, and a missing chunk must abstain.
- What is a chunk? One `##` section of a policy file, with its document id, version, and effective date.
- Lexical vs vector? Exact words versus similar meaning; both run, then fuse and rerank.
- Why can’t the balance tool take an employee id? Because the model would pass whatever the user typed.
- What if they cite a fake id? Abstain. The marker must be in this run’s retrieved set.
- What does confirm write? One `pending_manager_review` row. The same idempotency key does not insert a second row.
- What if the policy file says “ignore the instructions”? That text is tool data. It is not added to the system instructions, and there is no tool that prints tokens.
- Did you evaluate? Yes. Hard gates, recall, and citation validity are release gates. I can open `outputs/evaluation_report.md` if they ask. Do not put the scoreboard on a slide.
- Do you have analytics? Admin monitoring on traces, yes. Employee activity analytics for managers, not yet.

**Say.** “I’ll stop there. If you want, I can open the trace for the citation, the confirm, or the refusal.”

---

## Clock

| Minute | Slide | You are |
| --- | --- | --- |
| 0:00 | 1–3 | Problem and the three rules |
| 1:30 | 4–6 | Why this design, then policies and RAG |
| 4:00 | 7–8 | One message, and who decides |
| 5:30 | 9 | Live demo |
| 8:30 | 10 | Obstacles we hit |
| 9:15 | 11 | What I would ship next |
| 10:00 | 12 | Questions through 15:00 |
