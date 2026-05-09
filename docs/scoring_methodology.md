# Scoring Methodology

The first Civic Access Index version uses transparent weighted subscores:

```text
0.35 * healthcare_gap_score
+ 0.25 * food_gap_score
+ 0.20 * transit_gap_score
+ 0.20 * socioeconomic_vulnerability_score
```

Subscores are percentile-normalized at the tract level. The platform should expose the
metric values, percentile ranks, source provenance, and known limitations behind every
score.

This is not a definitive equity model or policy recommendation. It is an inspectable
public-interest data system for surfacing potential service gaps.

