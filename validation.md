# Validation notes

This file records the source decisions and the checks behind `figure.png` and
`figure_median.png`. The numbers come from `validate.py` and the CSV files in
`data/processed/`. All dollar values are in 2025 dollars.

## 1. Source report

**Source.** Board of Governors of the Federal Reserve System, Survey of Consumer Finances
(SCF), *Summary Extract Public Data*, CSV version. `get_data.py` finds the links on the
Fed's [current-survey page](https://www.federalreserve.gov/econres/scfindex.htm) and the
per-year pages listed under
[Previous Surveys](https://www.federalreserve.gov/econres/scf-previous-surveys.htm).
It does not use a hard-coded list of years.

**Survey years.** The files cover 13 triennial surveys: 1989, 1992, 1995, 1998, 2001, 2004,
2007, 2010, 2013, 2016, 2019, 2022 and 2025. The 2025 survey is the latest. Its results were
published on 9 October 2026, and every extract file shows "Last updated 10/9/2026". The
survey year is the year the data describe, which is not the year they were published.

**Files.** All files were retrieved on 16 October 2026 (UTC). `data/raw/manifest.csv`
records each file's exact URL, retrieval time, size and SHA-256 hash.

| Purpose | File(s) |
|---|---|
| Data for the figures | `scfp1989excel.zip` … `scfp2025excel.zip` (one CSV per survey) |
| Variable definitions | `bulletin.macro.txt` (the Fed's SAS macro that builds the extract) |
| Benchmark | `scf2025_tables_public_real_historical.xlsx` (historic tables based on public data, 2025 dollars) |
| Uncertainty | `scf2025rw1s.zip` (2025 replicate weights), `codebk2025.txt`, `Standard_Error_Documentation.pdf`, `2025_tables1_2_stderrs.xlsx` |

**Dollar basis.** Every wave is already in September-2025 dollars. The macro builds the real
public extracts with `CPIBASE=4789` for every year. That is the macro's coded value for the
September-2025 R-CPI-U-RS, with the decimal point omitted. Each year's page says that "all dollar variables [are] inflation-adjusted to 2025
dollars". The data confirm this: the unadjusted values reproduce the Fed's 2025-dollar
Table 4 for all 13 years (section 2). The scripts therefore make **no further inflation
adjustment**, because adjusting again would count inflation twice.

**Families.** An SCF "family" is the *primary economic unit*: the economically dominant
single person or couple in a household, plus everyone in the household who is financially
interdependent with them. The **reference person** is the single core individual. In a
couple, it is the man in a mixed-sex couple or the older partner in a same-sex couple
(codebook, "Unit of analysis").

**Families with children.** These are defined as `KIDS > 0`. The macro counts household
members whose relationship code is child (4) or stepchild (13) of the reference person or
spouse/partner. Foster children (36) cannot be identified in the public data. **There is no
age limit**, so this is not an under-18 filter: adult children living at home count. In
every wave, `KIDS > 0` agrees exactly with the macro's `FAMSTRUCT` codes for "with
children".

**Education groups.** `EDCL` is the education of the **reference person only**. Codes 1–2
(no diploma; high-school diploma or GED) form "HS or less", and code 4 (bachelor's degree or
higher) forms "BA or more". Code 3 (some college or an associate degree) is excluded from
this two-group comparison. The measure says nothing about a spouse's education, and nothing
about the education of the respondent's own parents. From 2016 on, `EDCL` is built from the
highest-degree question (`X5931`); before that, it comes from years of schooling and degree
items (`X5901`–`X5905`). The macro harmonizes the two.

**Weights and imputations.** The survey fills in missing answers five times, so each family
appears as five records ("implicates"). The weight `WGT` equals `X42001/5`. Summed over all
five records, it reproduces the number of families: 135.0 million in 2025 and 93.0 million
in 1989. It is therefore not divided by five again. The weights differ slightly across a
family's five records, so the five records are not interchangeable. Identifiers follow the
macro: `XX1` (family) and `X1` (record) in 1989, `YY1`/`Y1` from 1992 on. The implicate
number is `Y1 − 10·YY1`, which runs from 1 to 5 for every family. Families are counted by
distinct family ID, never by rows.

**Mismatches with the workshop's description.**
1. The guide says "parents' education". The data measure the **reference person's**
   education, which is a single person in each family.
2. The original figure's note says "child of the reference person". `KIDS` also counts
   children of the spouse or partner, and it includes children of any age.
3. The original note says values were "inflation-adjusted with the R-CPI-U-RS". That is
   correct, but the Fed has already applied the adjustment inside the extract. No
   adjustment step is needed in the code.
4. A comment in the macro still cites an "Updated R-CPI-U-RS … 1977–2022" file, but the
   macro's index values run through 2025. The comment is stale; the values are current.

## 2. Pass one: provenance and numerical validity

**Coverage** (`validation_coverage.csv`). Every wave has exactly five implicates per
family, and no record is missing `NETWORTH`, `WGT`, `KIDS` or `EDCL`. Zero and negative net
worth are kept: among the 2025 families in the comparison, 7.1% of BA-or-more families and
8.5% of HS-or-less families have negative net worth (weighted). `KIDS` never varies within a
family. `EDCL` varies across implicates for 0.1–1.2% of families, depending on the wave,
because education is sometimes imputed. A small number of families can therefore fall into
a group in some implicates but not others. The processed table reports two counts: distinct
families and records ÷ 5.

| Families with children (distinct IDs) | 1989 | 2001 | 2013 | 2025 |
|---|---|---|---|---|
| BA or more | 543 | 825 | 1,030 | 847 |
| HS or less | 668 | 726 | 943 | 596 |

**Reproducing the Fed's own public-data table.** `validate.py` recomputes Table 4 of
`scf2025_tables_public_real_historical.xlsx` ("Family net worth, by selected
characteristics of families, 1989–2025 surveys", thousands of 2025 dollars). It covers seven
rows: all families, the four education categories, single with child(ren), and couple with
child(ren). Each row has a median and a mean for all 13 years, which makes 182 cells.

- **All 182 cells match.** The largest absolute difference is **$5** (0.005 thousand),
  which is the table's rounding. The largest relative difference is **0.022%** (the 2013
  median for single parents).
- The match requires two choices: estimates pool all five implicates with `WGT`, and the
  median is the first value at which cumulative weight reaches half the total.
- This check confirms the dollar basis, weights, implicate handling, `EDCL` codes and the
  `KIDS > 0` definition. It does **not** directly validate the narrower combination plotted
  in the figures (families with children *and* a given education), because the Fed does not
  publish that cross-tabulation.
- *Public versus internal data.* The Fed also publishes tables built from its internal
  data, which include information withheld from the public files. The 2025 all-family mean
  is $1,232.0K in the public-data table and $1,241.5K in the internal-data standard-error
  workbook. The median is $216.1K and $215.9K. All of our comparisons use the public-data
  tables.

**Estimator conventions** (`validation_conventions.csv`). Our estimates pool all five
implicates, as the Fed's tables do. I compared them with two alternatives for the plotted
series:

| Alternative | Largest difference from what we plot |
|---|---|
| Average of the five implicate-specific means | 0.08% (1989, BA or more) |
| Average of the five implicate-specific medians | 1.5% (2013, BA or more: $372.2K vs $366.6K) |
| Interpolated weighted median | 0.6% |

A pooled weighted median and an average of implicate medians are therefore not
interchangeable. The pooled version reproduces the Fed's published medians exactly, and the
average of implicate medians misses them by up to $6.6K. The pooled version is used here.

**Uncertainty for the latest wave** (`validation_uncertainty_2025.csv`). The method follows
the SCF codebook's `MEANIT` procedure and the Fed's standard-error documentation:

- *Sampling variance.* Each estimate is recomputed with each of the 999 replicate weights
  (`WT1Bk × MMk`) on implicate 1, and the variance is taken across those 999 values.
- *Imputation variance.* This is the variance across the five implicate-specific estimates,
  multiplied by 6/5.
- *Combination.* SE = √(6/5 · imputation variance + sampling variance), and the 95%
  interval is the estimate ± 1.96 SE.
- *Implementation check.* The replicate file stores its `mm` columns in reverse order, so
  the code selects columns by name. After this fix, the replicate totals run from 134.96 to
  135.04 million families, matching the population.

| 2025, thousands of 2025 dollars | Estimate | SE | 95% interval |
|---|---|---|---|
| Mean, BA or more, with children | 2,291.1 | 113.2 | 2,069 – 2,513 |
| Mean, HS or less, with children | 269.2 | 25.6 | 219 – 319 |
| Mean gap (BA − HS) | 2,021.9 | 117.5 | 1,792 – 2,252 |
| Mean ratio (BA ÷ HS) | 8.51× | 0.97 | 6.6 – 10.4 |
| Median, BA or more, with children | 625.8 | 46.2 | 535 – 716 |
| Median, HS or less, with children | 71.8 | 11.2 | 50 – 94 |
| Median gap (BA − HS) | 554.0 | 48.3 | 459 – 649 |
| Median ratio (BA ÷ HS) | 8.72× | 1.41 | 6.0 – 11.5 |

*Check of the method.* The same code gives all-family 2025 SEs close to the Fed's published
ones (internal data, so they should be close but not identical):

| SE, thousands of 2025 dollars | Ours | Fed workbook |
|---|---|---|
| All-family mean | 31.1 | 31.0 |
| All-family median | 6.6 | 6.4 |
| College-degree mean | 61.2 | 62.0 |
| College-degree median | 33.1 | 33.1 |

*A defect in the Fed's workbook.* In Table 2 of `2025_tables1_2_stderrs.xlsx`, the
education rows are shifted down by one. The "Education of reference person" heading carries
the no-diploma values, and the "College degree" row is blank. The comparison above
re-aligns the rows by value.

*Limits.* Intervals were produced only for 2025, because only that wave's replicate weights
are downloaded. The intervals use a normal approximation. Ratio intervals in particular are
approximate.

**Comparison with the workshop's original figures.** The coverage matches (13 waves,
1989–2025), and so do the groups (BA or more versus HS or less among families with a child
at home, reference person's education) and the dollar basis (2025, R-CPI-U-RS). The broad
pattern also matches, with dips in 1992, 2010–2013 and 2022 and a 2025 high for the BA
line. The labels printed on the original figures were used only as a check after our
values had been computed:

| 2025 values | Original label | Ours |
|---|---|---|
| Mean, BA or more | $2,291K | $2,291.1K |
| Mean, HS or less | $269K | $269.2K |
| Median, BA or more | $626K | $625.8K |
| Median, HS or less | $72K | $71.8K |

No discrepancy was found. The guide's remark that the 2025 gap is "about as wide as in
2013" holds for the **ratio** of means (8.6× in 2013, 8.5× in 2025). It does not hold for
the **dollar gap**, which grew from $1.35M to $2.02M.

**Second publication.** U.S. Census Bureau, *Wealth of Households: 2024* (P70BR-218, July
2026), based on the 2025 Survey of Income and Program Participation (SIPP):
<https://www2.census.gov/library/publications/2026/demo/p70br-218.pdf>.

- *Independence.* The SIPP is a separate dataset, not another analysis of the SCF.
- *What it reports.* Median household wealth at the end of 2024 was $323,500 where the most
  educated household member has a bachelor's degree and $61,380 where it is a high-school
  diploma, a ratio of 5.3×.
- *Closest SCF comparison.* The comparable all-family SCF medians for 2025 are $505.0K
  (college degree, which here includes graduate degrees) and $106.7K (high-school diploma),
  a ratio of 4.7×.
- *Why the levels differ.* The definitions differ: households rather than families; the
  most educated member rather than the reference person; bachelor's only rather than
  bachelor's or higher; all households rather than those with children; interpolated
  medians; and nominal end-of-2024 dollars. The SCF also oversamples very wealthy
  families, and the SIPP does not.
- *Conclusion.* The two sources agree on direction and rough size (a college-educated
  household holds about five times the median wealth of a high-school one), but the levels
  are not comparable. The SIPP cannot validate the families-with-children series.

## 3. Values available for personal review

These cells are in `scf2025_tables_public_real_historical.xlsx`, which is linked as
"Estimates inflation-adjusted to 2025 dollars" under *Historic Tables Based on Public Data*
on <https://www.federalreserve.gov/econres/scfindex.htm>. Each is on sheet **Table 4**, in
the 2025 column of the row named. Values are in thousands of 2025 dollars. **Status: not yet
reviewed by Faisal.**

| Cell | Row, statistic | Fed value | Our value |
|---|---|---|---|
| `Z6` | All families, 2025 median | 216.10 | 216.100 |
| `AA36` | College degree, 2025 mean | 2,240.46 | 2,240.464 |
| `Z29` | Couple with child(ren), 2025 median | 333.60 | 333.600 |

## 4. Pass two: reproducibility

The test copied only `get_data.py`, `plot.py`, `validate.py`, `requirements.txt` and
`.gitignore` into an empty temporary folder. No data or outputs were copied. It then created
a new virtual environment from `requirements.txt` (Python 3.11.9) and ran
`get_data.py → plot.py → validate.py`.

- All 19 downloads succeeded, with no outages.
- Every SHA-256 hash matched the original run.
- All six CSVs in `data/processed/` were identical.
- `figure.png` and `figure_median.png` were byte-identical.
- A second, normal run kept the 19 existing files and reproduced identical results.

## 5. Pass three: presentation

Both figures were opened and inspected. The checks covered:

- No clipped or overlapping text, and the legend does not cover the data.
- The y-axis ends on a labeled tick, and endpoint labels agree with
  `networth_by_education.csv`.
- The caption, note and source match the code's definitions.
- The README was rendered with GitHub's Markdown API before committing, and its image
  links point to files at the repository root.
