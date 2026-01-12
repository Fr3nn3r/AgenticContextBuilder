Simple instructions to devs

Implement build_classification_context(doc_text_by_page, cue_phrases) that returns:

first 2 pages (truncated)

5–15 cue snippets (page + surrounding text)

Classify using that context bundle.

If confidence below threshold, retry with expanded context (more pages/snippets).