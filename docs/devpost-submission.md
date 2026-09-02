# Muster — Devpost submission copy

Paste-ready. Track: **Professional Agents**.

---

## Elevator pitch (200 char limit)

> New York fined Starbucks $38.9M for getting shift schedules wrong. Muster writes next week's rota under the law, absorbs the sick calls, and stops when the call is a person's to make.

---

## Inspiration

I went looking for the most boring possible problem, on the theory that boring problems are where people actually lose their afternoons.

I found a manager writing next week's rota in a spreadsheet.

That sounds like nothing until you notice that eleven US jurisdictions now regulate how that spreadsheet is allowed to be filled in. Fourteen days' written notice. Cash premiums when a posted schedule changes. Extra pay when someone is scheduled too soon after their last shift. And a worker's right to say no.

The enforcement is not theoretical. New York City's Department of Consumer and Worker Protection settled with **Starbucks** for **$38.9M**, more than $35.5M of it restitution to over 15,000 workers, after an investigation found **more than 500,000 violations** across 300-plus New York locations. The **Chipotle** settlement was **$20M** — at the time the largest worker-protection settlement in the city's history. DCWP has also settled with Dunkin', a Taco Bell franchisee, Theory, and Walgreens over the same law.

Those are companies with legal departments. The person I had in mind runs two or three coffee shops and faces the identical rulebook, enforced by the identical regulator.

Then I read the ordinances properly, and the thing that struck me was that they are not vague. They are arithmetic. Oregon owes one hour at the regular rate for adding a shift, and half the rate per hour taken away. Chicago owes a quarter over base for working inside the rest period, and half over base if those hours are overtime. New York owes $10, $20, $45 or $75 depending on how much notice was given and what changed, and a flat $100 for a clopening.

You can compute all of it. Nobody does, because the moment it matters is a sick call at 6am, and at 6am the manager has a hole in the rota and no time.

## What it does

Muster writes next week's schedule for a small multi-site operator, then holds it together all week.

When a shift loses its worker, it finds **every lawful way to cover it** and prices each one against the governing city's ordinance — the predictability premium, the rest-period remedy, the overtime the cover creates, and whether a carve-out cancels the charge. Then it takes the cheapest lawful option, inside limits the operator set, and writes a receipt.

The receipt is the part I would defend hardest. Every change carries what changed, which clause priced it, what it cost, which carve-out was claimed and the evidence for it, who consented and when, and whether a person or the agent decided. That is the artefact an investigator asks for. Starbucks' exposure ran to half a million violations partly because nobody could produce it.

And it stops. Eight named rules can stop it: the cover costs more than you authorised, the week's premium budget is spent, it would push someone into overtime, it would leave a worker short of the hours they were promised, it would run the site below its certification minimum, the rulebook can't be resolved — and two more.

Those last two ignore the autonomy dial completely. **Muster will never waive a worker's rest period on their behalf, and never asks a worker who has already declined.** At every level, including the most permissive one.

That is not a product opinion dressed up as ethics. It is the law's own structure. Oregon requires the worker's own request or consent. New York requires *written* consent for a clopening and defines consent as agreement after a meaningful opportunity to decline. Chicago's guidance says in terms that the Right to Rest **has no exceptions**. An agent that could dial past those wouldn't be more capable. It would be unlawful.

## How I built it

Strands Agents on Amazon Bedrock, Claude Sonnet 4.6, deployed on App Runner as a single container serving the agent, the API and the console.

**The rulebook is data, not code.** Four jurisdictions — Oregon, Chicago, NYC fast food, NYC retail — each a JSON file where every figure carries the `.gov` URL it was read from. One engine, one row per city. When a council amends an ordinance, that is a diff on a data file with a new effective date, and every receipt written before it still evaluates under the rules that were in force when it was written.

**The model never does the arithmetic.** Notice bands, premiums, rest remedies, overtime and totals are pure functions. Money is integer cents throughout, rounded half-up once at the end of each premium, because half a cent multiplied across a week of shifts stops being half a cent. The agent orchestrates; it never computes.

**A carve-out has to be evidenced, not asserted.** Carve-outs are the highest-value thing for an agent to be wrong about, because they take a premium to zero. So a claim is checked against the world: a standby-list carve-out needs the worker to be *on* the list and to have *accepted*; a worker-requested change needs a request record. An agent that says "she asked for this" gets nothing for saying so. And claiming Oregon's standby carve-out in Chicago fails outright, because Chicago does not offer one.

**The autonomy boundary is a Strands `InterventionHandler`** that runs before every consequential tool call and returns `Proceed` or `Confirm`. A `Confirm` breaks the run out of its loop and snapshots its whole state, so a paused run resumes hours later, in a different process, from a structured human decision.

**Muster also ships an MCP server** over its compliance engine — five read-only tools, so any other agent can ask what a change costs in Chicago and get a cited answer. Deliberately read-only: nothing over that protocol can move a shift, post a schedule or record a consent. A client can ask what something would cost; it cannot change anyone's week.

## Challenges I ran into

Everything real I found, I found by using the thing. Every one of these passed a full test suite first.

**The API called a run "covered" by searching the agent's own closing message for the word "cover".** The message was *"I could not cover this shift."* It contains the word. The ledger was empty and the API said success — the exact failure this project exists to prevent, sitting in my own code, three lines under a docstring claiming the ledger was authoritative.

**`take_snapshot()` needs a preset in Strands 1.54.** Called bare it raises, so every escalation returned a 500 — the one path that must never fail.

**I read the interrupt's fields through `getattr` with defaults.** The real fields are `id` and `reason`, not `interrupt_id` and `prompt`. The defaults turned a wrong name into a cheerful `None`, and the resume then failed with `interrupt_id=<None>` hours later, after a human had already answered and the decision had been consumed.

**Approving cloned the question it was answering.** Strands' default evaluator accepts `True` or `"yes"`. Muster answers with a record — the outcome, who decided, their role, their note — because all four end up on the receipt. That record read as a refusal, so the run resumed, the same call was refused again, and the policy raised an identical question.

**A resumed run is a new agent with a new tools closure**, so its priced-option cache was empty and `assign_cover` rejected the very option the operator had just approved.

**And DRAFT had no way to undo a shift it had proposed.** Generate-and-repair needs a repair primitive; `propose_shift` was append-only. In a live run the agent proposed overlapping shifts, saw the rest breaches it had caused, couldn't remove them, and stopped — asking me to delete them through an admin panel that does not exist.

## Accomplishments that I'm proud of

The rulebook. Four ordinances read from primary sources and encoded as data with citations attached to individual figures, so you can check my work without reading any Python.

The two non-negotiable rules, and the fact that they're grounded in three separate statutes rather than in my opinion about what agents should do.

And the eval suite, where I applied five deliberate breaks to the policy and recorded what actually happened. One of them didn't go red on the test I predicted — raising the conservative ceiling swaps which rule fires rather than adding one, so the count-based test stayed green and a different assertion caught it. That's written down as observed rather than as predicted, because an eval suite that reports what you hoped for is worse than no suite at all.

## What I learned

Tests tell you the code does what you wrote. Clicking tells you whether you wrote the right thing.

The last pass over this was me driving every control in the console — 25 assertions over buttons, tabs, pickers and modals, and 9 more over the end-to-end flows. It found seven controls that were decoration or lied: a "Post schedule" button that ran the drafting loop, a week stepper that was permanently disabled, a view selector with no handler, an "Insights" button with no screen behind it, and two modals that couldn't be dismissed with Escape — the composer's overlay stayed up and swallowed every click on the page behind it.

None of that was visible in 226 passing tests.

## What's next for Muster

Seattle, San Francisco and Philadelphia — three more rulebook rows, each a data file and a citation rather than a code change.

Real integrations behind the seams that are already in the right place: the roster and demand curve arrive as MCP clients, and the messaging channel becomes a real one.

And one honest gap I'd close first: Chicago has no premium tier encoded for an addition made inside 24 hours, because I could not find primary-source text for it. It prices at zero there. I would rather ship that gap named than invent a number to fill it.

---

## Built with

python · fastapi · strands-agents · amazon-bedrock · claude · model-context-protocol · aws-app-runner · amazon-ecr · react · vite · zustand · pydantic · pytest · docker

## Try it out

- **Live console:** https://ipxvamjzfk.us-west-2.awsapprunner.com
- **Source:** (GitHub URL)

Open the console. Set the dial to **conservative** on the Autonomy screen, then use the operator menu to report a sick call. Muster prices every lawful cover, finds that the cheapest is $45 under New York's under-seven-days tier, and stops — because at conservative it may not spend a cent alone. Approve it and the paused run resumes, commits, and writes a receipt with your name on it.

Then look at **Autonomy** for the two rules the dial cannot reach.

## Testing instructions

No login, nothing to install. It runs on a fixed seeded week so every figure is reproducible.

**1. Watch it stop.** Autonomy → **conservative**. Operator menu (top right) → **Report a disruption** → pick a shift → **Send**. It takes 10 to 60 seconds because it is a real Bedrock call. It lands in **Decisions**, naming the rule in plain English: *"$45.00 exceeds the conservative per-incident limit of $0.00."*

**2. Watch the resume.** Add a note and press **Approve**. The paused run picks up where it stopped, commits the cover, and **Receipts** gains a row with the clause, the money and your name.

**3. Watch it draft.** Step to the next week with the toolbar's **›**. It's unposted. Press **Draft with Muster** and it builds the week — proposing, checking, removing what it got wrong, and stopping before it posts if the week would leave a site below its certification minimum.

**4. The line it will not cross.** **Autonomy** shows three levels and, beneath them, two rules marked fixed at every level, each with the statute behind it.

To run it locally instead, see Quick start in the README. The offline suite needs no AWS credentials: `pytest -m "not integration"`.
