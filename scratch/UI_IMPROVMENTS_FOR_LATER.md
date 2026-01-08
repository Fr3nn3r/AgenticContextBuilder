Claim Document Pack must be renamed, Document Sets
the columns on the screen must be sortable
Document sets must indicate the number of extracted documents VS total number of documents
Document sets must indicate the number of extracted document that are not labeled

Field review planel
The "Evidence: Page 1" must be renamed "Show evidence"
The "✓ Match" badge on the top right is too much: remove it
Let's rename the status CONFIRMED into LABELED if there is a match with the truth, INCORRECT if there is a missmatch
The edit button should allow to mark unverifiable as well
The save lavel button should indicate when it requires 

the columns on the screen must be sortable
Certain date values are extracted but not normalized (I'm talling about dates with spanish month name for instance, maybe good to see how we go about fixing this)


---

## Blindspots to watch (so this doesn’t bite you later)

1. **Normalization must be centralized**
   If UI uses one normalizer and backend metrics uses another, you’ll get “Correct” in UI but “Incorrect” in metrics. Define one shared normalization function per field.

2. **Empty vs truly missing**
   Decide once: is `""`, `null`, `"N/A"` considered Missing? Standardize this or you’ll get inconsistent outcomes.

3. **Truth provenance (optional but important)**
   Right now truth_value can be typed by a reviewer without evidence. That’s okay for MVP, but long-term you may want to store “truth evidence page” to protect against accidental mistakes.

4. **Doc type wrong handling**
   Even if you default doc type to “assumed correct”, you still need a way to exclude misclassified docs from benchmark metrics, or you’ll inflate Incorrect/Missing.

---
