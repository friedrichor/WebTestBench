from string import Template


PROMPT_MATCH_ITEM = Template(
"""
Given a list of predicted checklist items and a list of gold checklist items. You are required to align predicted (model-generated) test items to gold (human-labeled) test items for the same web instruction.

Instruction:
```
$instruction
```

Gold Test Items (`"gold_id": "description"`):
```
$gold_items
```

Predicted Test Items (`"pred_id": "description"`):
```
$pred_items
```

Goal:
For each predicted item, decide if it corresponds to exactly one gold item describing the same requirement/behavior. Produce a one-to-one mapping; unmatched predictions should map to None.

Matching rules:
1. Mapping constraint: each predicted item maps to AT MOST ONE gold item; each gold item MAY be assigned to MULTIPLE predicted items.
2. Prioritize intent over wording: if a predicted item is more specific/less specific but clearly covers the same user requirement, match it; otherwise, leave it unmatched.
3. Do NOT force matches: if no gold item cleanly aligns, use None.
4. Preserve predicted order: output tuples follow the input predicted sequence; length of output list equals number of predicted items.

Output Format (Markdown)
[("pred_id_1", "gold_id" or None), ("pred_id_2", "gold_id" or None), ...]

DO NOT PROVIDE ANY OTHER OUTPUT TEXT OR EXPLANATION. Only output the List. Output:
""")
