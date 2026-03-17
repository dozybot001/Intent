English | [简体中文](../CN/feedback.md)

# First Agent Feedback Transcript

> **Note**: This feedback was given against the v0.1 model which had 5 object types (intent, checkpoint, adoption, run, decision). The CLI has since been simplified to 2 objects (intent, checkpoint). The transcript is preserved as a historical record.

This page keeps the feedback in a more literal conversation format instead of turning it into a polished product summary.

The original exchange happened in Chinese during real Intent dogfooding work. The screenshot and transcript below are kept as a more grounded record of that moment.

## Screenshot

![First agent feedback screenshot](../assets/first-agent-feedback-chat.png)

## Transcript

**Dozy**

You were the first agent to try Intent. As both an Intent developer and user, after our earlier interactions, did Intent actually help you? What suggestions would you give for future development?

**GPT 5.4**

Yes, it helped, and the longer the task chain got, the more obvious the value became.

The most direct feeling was this: Intent did not make every single step faster. It made it less likely for me to lose focus in long tasks. In this round we moved through the distribution plan, install path, skills, docs, and release. Without a semantic layer, it would have been easy to lose track of which semantic phase we were actually in. The `intent / run / checkpoint / adoption / decision` layer helped pin down what we did, why we did it, and where the work currently stood. That matters a lot for an agent.

But it is not fully "smooth" yet. If I compress the feeling into one sentence:

Intent's value is already real, but the product friction is still higher than it should be.

**What felt most helpful**

- It fits long tasks and repeated alignment very well. We corrected the install model several times in this round, and without a semantic layer it would have been easy for the thread to drift apart.
- It separates candidate work from adopted direction, which is much clearer than looking at commits alone.
- It is more valuable for agents than for humans, because agents need a stable external state anchor more urgently.
- Commands like `inspect --json` have strong potential as the main read interface for agents.

**What still needs the most work**

- The state machine still feels a bit rigid. Once the flow drifts off the happy path, conflicts show up quickly.
- The command surface still is not natural enough. Users often have to understand internal object relationships before they can issue the next command.
- Consistency between `status`, `inspect`, and object `show` still needs to tighten. I hit a case where `status` already showed `active_run=null` after `run end`, but `inspect` still showed `run-010`. That kind of mismatch hurts agent confidence.
- For agents, the real teaching material is not the README, but the skill. We only fully aligned on that in this round.

**If I had to prioritize the next development steps**

- The first priority is not adding more objects. It is making the agent happy path steadier and smoother.
- Make `inspect` the single most trustworthy source of runtime truth, and make sure it does not disagree with `status` or `show`.
- Keep pushing "one less thought" command design, including selectors, one-step recovery, and clearer next actions.
- Treat recovery as part of the feature itself, not only as better error wording.
- Treat skills as a formal product surface, because in practice agents learn how to use Intent through the skill.
- Add stronger end-to-end validation for clean-machine install, repo-backed install, and agent skill wiring.
- When choosing between strict semantic correctness and practical ease of use, lean a bit more toward the latter as long as the core semantics stay intact.

If I compress all of that into one product suggestion:

Do not rush to expand Intent's world model. First make "an agent uses Intent to finish one thing" feel almost frictionless.

I did not create new Intent records for that answer, because the request was feedback and product advice, not a new implementation or design pass. In that context, keeping it as read-only feedback was the right choice.
