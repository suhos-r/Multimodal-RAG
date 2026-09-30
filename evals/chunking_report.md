# Chunking benchmark report

Strategies: fixed, recursive, semantic, proposition, layout
Gold: 56 Q (51 answerable, 5 unanswerable), top_k=8
Retrieval proxy: stopword-filtered word overlap (relative ranking; absolutes re-measured under dense retrieval in Plan 04).
Window scale-down (documented): fixed 120/25, recursive 200/40, semantic max 250, proposition parent 200 - ratios mirror production 800/150; without this, no strategy would split this corpus and the comparison would be vacuous.
clean_break = fraction of chunks ending on a sentence/table boundary (higher = fewer mid-sentence cuts).

| strategy | recall@5 | mrr | hit@1 | clean_break | chunks | avg_words | index_s |
|---|---|---|---|---|---|---|---|
| layout | 0.98 | 0.928 | 0.882 | 1.0 | 23 | 63.5 | 0.001 | **WINNER**
| semantic | 0.98 | 0.928 | 0.882 | 0.96 | 50 | 29.2 | 0.004 |
| recursive | 0.98 | 0.928 | 0.882 | 0.84 | 25 | 61.6 | 0.001 |
| fixed | 0.98 | 0.928 | 0.882 | 0.724 | 29 | 55.6 | 0.003 |
| proposition | 0.98 | 0.829 | 0.725 | 0.976 | 164 | 17.8 | 0.002 |

Winner: **layout** (recall@5=0.98, mrr=0.928, clean_break=1.0).
Tie-break order: recall@5, then MRR, then clean_break, then fewest chunks (index/embed cost).
Production default: hybrid - recursive (800/150) parent windows + proposition children (small-to-big retrieval) + layout guard (never split tables/images). Set CHUNK_STRATEGY to the winner for single-strategy runs.
Note: proposition children underperform under this LEXICAL proxy (short sentences share few query terms); small-to-big pays off with dense retrieval in Plan 04, where children are retrieved by embedding and parents served for generation.
Unanswerable Qs are excluded from recall (abstention is tested in Plan 04/06).
