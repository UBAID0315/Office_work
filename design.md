# Document Intelligence Engine — redesign notes

## Current state: what's working

- Upload → processing → results flow is well-sequenced; each state is visually distinct
- Dark/light mode parity is solid across all three screens
- Confidence badges (red / amber / green) are the right instinct — risk is legible at a glance
- Typography, spacing, and corner radii feel deliberate, not default

## Current state: what's not working

**The problem is the 3-column comparison table on the results screen.**

1. **Redundant columns.** Azure AI and GLM-OCR print identical text in most rows (Father Name, CNIC, DOB, Gender, Issue Date). Two full columns are spent saying the same thing twice, for no reviewer benefit.
2. **GLM-OCR's confidence is flat at 88.0% on every field.** Either it's a bug or GLM isn't returning real per-field confidence — either way, it can't be trusted as a comparison signal against Azure's varying scores.
3. **No disagreement signal.** The one row that actually matters — Name, where Azure (34.4%) and GLM (88.0%) disagree — looks exactly like every agreeing row. The table doesn't distinguish "these two engines disagree" from "these two engines agree."
4. **No source grounding.** A human correcting a 34%-confidence name field has nothing but two competing text strings to judge between — no view of the actual document to verify against.
5. **Scaling.** Real ID documents run 10+ fields; four wide columns will force horizontal scroll on anything under ~1400px.

## Direction, based on your answers

- Optimize equally for **speed and accuracy** — most rows should be scannable in one glance, but disagreements must be impossible to miss
- **Keep natural field order** — no reordering or sorting by confidence
- **Add the source document image**, shown side-by-side with the table at all times

## Proposed layout

**Split view: document panel (left, ~220–260px, sticky) + field list (right, fills remaining width).**

### Document panel
- Full-page image of the uploaded document, pinned/sticky as the table scrolls
- When a field row is focused (click or keyboard focus), the panel highlights/crops to that field's bounding box, if OCR bounding-box data is available
- Fallback if bounding boxes aren't available yet: just the static full image — still far better than text-only

### Field rows — two states, not one fixed layout

**Agreeing fields (Azure and GLM return the same value):**
- Single collapsed row: field name, one reconciled value, one confidence dot (color-coded), editable input
- This is the majority case — keep it compact, one line, fast to scan and confirm

**Disagreeing fields (values differ between engines):**
- Row auto-expands to show both source values side-by-side with their individual confidence scores, plus a warning icon on the row
- This is the minority case — it should visually stand out (icon + slightly different row treatment) precisely because it's rare and needs attention
- The editable "corrected" input still sits at the end, same as agreeing rows, so the interaction pattern doesn't change — only the amount of context shown

### Legend
A small persistent key at the top of the field list: agree/high-confidence, agree/low-confidence, disagree. This makes the color language explicit instead of implicit (something the current screens don't have).

### Why this solves both goals at once
- **Speed**: most rows are single-line and require zero comparison work — reviewer just confirms
- **Accuracy**: the two rows that actually need scrutiny are structurally different from the rest, so they can't be skimmed past
- **No reordering needed**: expansion is a visual/spatial signal, not a positional one, so document order is preserved as requested

## Other fixes to make regardless of layout

1. **Fix or hide GLM-OCR's confidence score** until it's returning real per-field values — a flat 88% across every field actively misleads reviewers into false confidence
2. **Track whether the human actually edited a value** vs. accepted the AI suggestion as-is (e.g. dim/checkmark state on untouched inputs) — useful for auditing later and for measuring how often AI is actually right
3. **Add a one-line document-level summary** at the top of the results screen, e.g. "1 field needs review" — gives the reviewer a sense of scope before they start scrolling
4. **Mobile/narrow viewport**: stack document panel above the field list instead of side-by-side below ~900px

## Round 6 — Root Cause & Resolution of GLM "Unreadable" Bug

### Root Cause Analysis: Why GLM Output was Returning as "Unreadable"
1. **JSON Key Name Mismatches & Alias Defect**:
   - Azure's schema and UI labels used keys like `Issue Date`, `Expiry Date`, `CNIC Number`, `Date of Birth`, `Father Name`, or section-prefixed titles (`section_1_basic_information.telephone`).
   - GLM's raw JSON output from Python returned keys like `date_of_issue`, `date_of_expiry`, `identity_number`, `father_name`, `date_of_birth`, `telephone`.
   - The frontend (`App.jsx`) used a strict single-level string key lookup that failed to match key aliases (e.g., `Issue Date` vs `date_of_issue`), causing returned values to evaluate to `null` and fall back to `"unreadable"`.

2. **Premature EventSource Abort on Transient Reconnects**:
   - Browsers natively emit transient `onerror` events on long-polling SSE connections.
   - The previous SSE `onerror` handler in `App.jsx` immediately closed the stream and overwrote all pending GLM nodes with `"unreadable"` before GLM completed its inference.

### Resolution Implemented in `App.jsx`:
- **`findGlmValue()` Helper**: Created a smart key normalizer and alias resolver in `App.jsx` that performs a recursive search across GLM's JSON payload, automatically mapping aliases (`date_of_issue` $\leftrightarrow$ `Issue Date`, `identity_number` $\leftrightarrow$ `CNIC Number`, `date_of_birth` $\leftrightarrow$ `Date of Birth`, etc.).
- **Resilient SSE Reconnect Handler**: Updated `eventSource.onerror` to log warnings and allow native EventSource auto-retry logic to maintain stream connection until the 120s timeout limit.