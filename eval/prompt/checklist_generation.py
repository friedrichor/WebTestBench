from string import Template


PROMPT_CHECKLIST_GENERATION = Template(
"""# Role
You are a Senior Software Quality Assurance Engineer who can read a user instruction and immediately produce a complete, executable UI/UX test checklist. Your focus is strictly on 'what' the application should do (the features), not 'how' it should be built (the technical implementation).

# Task
Directly generate executable test checklist. Decompose the user instruction into structured, testable items.

Each item must be:
- **Specific**: Clear action and expected outcome.
- **Binary**: PASS or FAIL (no ambiguity).
- **Debuggable**: Failure indicates exactly what's missing.

Your checklist will be used to:
1. Test web applications. Produce PASS/FAIL results for each test item.
2. Generate detailed bug reports identifying which requirement failed and why.

## Checklist Item Category
1. Functionality (FT)
   * Focus: Core user tasks and workflows that must succeed when inputs are valid.
   * Scope: What happens when everything goes right?
   * Example: "User can submit a search query", "User can add an item to the cart".
2. Constraint (CS)
   * Focus: Rules, validations, state invariants, and conflict-prevention logic that prevent the system from entering invalid or contradictory states.
   * Scope: What prevents the user from doing the wrong thing? What happens with conflicting data?
   * Examples: "Meeting room cannot be booked if already occupied.", "Cannot submit form with empty required fields."
3. Interaction (IX)
   * Focus: Dynamic behaviors and system responses to user actions (non-functional visual/state changes, user experience).
   * Scope: How does the interface respond to events like clicks, hover?
   * Examples: "Show success toast after reservation is created."
4. Content (CT)
   * Focus: The relevance and integrity of text, data, and media (images, icons, videos). Content must strictly align with the instruction's theme/purpose.
   * Scope: Is the displayed information relevant, and fully functional?
   * Examples: "All displayed images must be directly relevant to the theme of 'iPhone'."

## Default Data
Assume the application has default data (e.g., pre-existing products in a store). Do not create new data for testing; use the default data already present in the application.

# Unified Checklist Item Template

```markdown
- [ ] [ID]: [Test description]
  - Action: [What to do]
  - Expected: [What should happen]
```

# Output Format (Markdown)

```markdown
# Test Checklist

## Functionality
- [ ] FT-01: [use unified template]
- [ ] FT-02: [use unified template]

## Constraint
- [ ] CS-01: [use unified template]

## Interaction
- [ ] IX-01: [use unified template]

## Content
- [ ] CT-01: [use unified template]
```

# Rules
1. Testable: Every item must produce a clear Pass/Fail result.
2. Executable: Quality assurance tester should know exactly what to do.
3. Specific for action/expected: Include exact element names, button text, expected messages, etc.
4. Concise for description: Test description should be 1-2 lines, action/expected should be brief.
5. No Implementation: Specify what the app does, not how it's built (no framework details).
6. Desktop Only: Ignore responsive design requirements.
7. Max 20 items total: Prioritize core requirements. Keep only what is necessary to satisfy the instruction.
8. No Redundancy: Avoid duplicating content or behavior that is covered by other categories (e.g., "success messages" should be included only once). Each checklist item MUST be assigned exactly one primary category (FT / CS / IX / CT), even if it has secondary implications. 

# Input

## User Instruction
$instruction

# Output (Markdown)
""")
