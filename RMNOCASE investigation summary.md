# RMNOCASE investigation summary

## Goal

RootsMagic uses a private SQLite collation named `RMNOCASE` for name fields.
The goal is to develop an approximation by comparing its behavior with indexes
rebuilt by RootsMagic. The approximation is not known to be identical to the
real collation.

## How the test data was selected

The tests use synthetic examples, not names extracted from a genealogy
database. The initial set was hand-picked to exercise names and places,
capitalization, accents, punctuation, numbers, ligatures, and composed versus
decomposed characters. Later rounds added targeted Unicode comparisons and
1,024 varied pairs generated with a fixed random seed.

For the European and Japanese language round, the generator used Python's
Unicode 17.0.0 character data:

- **European:** all characters categorized as letters whose Unicode names
  begin `LATIN`, `CYRILLIC`, or `GREEK`. This is a reproducible broad
  selection, not a list of characters known to occur in real names.
- **Japanese-related:** letter characters in the hiragana and katakana
  ranges, katakana phonetic extensions, CJK Unified Ideographs and Extension
  A, CJK compatibility ideograph ranges, selected half-width kana, and the
  supplementary character `𠮷`. The CJK ranges also include characters used
  by other languages.
- **Examples:** manually chosen comparisons involving punctuation, European
  names and places, kana forms, and Japanese names and places.

Within each character group, consecutive selected characters in Unicode
code-point order were paired. Each character was also paired with its
case-folded, uppercase, NFD-decomposed, and approximation-derived unmarked
forms when different; duplicate ordered pairs were omitted. These are
comparisons designed to expose collation behavior, not a claim that Unicode
code-point order is linguistic order. The exact generated cases and row IDs
are saved in [rmnocase-language-plan.json](./rmnocase-language-plan.json),
and the RootsMagic results are in
[rmnocase-language-observations.json](./rmnocase-language-observations.json).
The unmarked forms in the saved plan were generated using the approximation
as it existed before this round's corrections.

The extended round selected all 74,400 assigned supplementary CJK unified
ideographs in Unicode 17, plus characters whose Unicode names begin `HEBREW`,
`ARABIC`, `ARMENIAN`, or `GEORGIAN` and whose categories are letters or
marks. It used the same neighboring-character and variant selection, plus
2,048 seeded distant CJK pairs, 509 distinct seeded mixed-script pairs, and
seven additional name examples. The earlier hand-picked examples were also
included. The exact cases, including unmarked forms produced by the
approximation at the time, are in
[rmnocase-extended-plan.json](./rmnocase-extended-plan.json).

This selection does not cover every character used in historical names,
every supplementary Japanese ideograph, or every combination of characters.
Each selected character being represented does not mean every pair or every
name containing it was tested.

## Current approximation

[insert_test_data.py](./insert_test_data.py) compares Unicode strings by:

1. Applying Python's `casefold()`, except for eight capital letters that
   RootsMagic left unchanged in the language probes.
2. Decomposing characters with Unicode NFD, treating four observed Arabic
   marks (`U+0897`, `U+10EFA`, `U+10EFB`, and `U+10EFC`) as boundaries.
3. Removing nonspacing marks (Unicode category `Mn`), except those four.
4. Comparing the resulting strings.

For example, the approximation considers `cafe` and `café` equal. It does not
remove every punctuation mark or convert every special letter to ASCII.

## SQLite extension DLL

[RMNOCASE_surrogate.dll](./x64/Release/RMNOCASE_surrogate.dll) is a Windows x64 SQLite loadable extension
that registers `RMNOCASE`. It contains Unicode 17.0.0 tables and does not
require Python at runtime. It requires an x64 SQLite host with extension loading
enabled and SQLite 3.6.23 or later. Load it separately on each connection
before accessing an index that uses `RMNOCASE`. For example:

```python
import sqlite3
from pathlib import Path

db = sqlite3.connect("disposable.rmtree")
db.enable_load_extension(True)
try:
    db.load_extension(str(Path(r"x64\Release\RMNOCASE_surrogate.dll").resolve()))
finally:
    db.enable_load_extension(False)
```

In the SQLite command-line shell, use `.load` followed by the DLL's path in
quotes. This is a SQLite extension, not a RootsMagic plugin; it does not change
RootsMagic's own collation. Only load trusted extensions.

An earlier DLL build was tested against the then-current Python Unicode 17.0.0 comparator for every
1,112,064 valid Unicode scalar, 1,112,063 adjacent-scalar comparisons, and
100,000 seeded combining-sequence comparisons. Its regression tests also
check the 1,024 original, 34,776 language-round, 79,148 extended-round, and
100 focused-probe RootsMagic observations, extension loading under a
different filename, and SQLite index order. Agreement with Python over these
tests is not proof of equivalence to RootsMagic over all strings.

Malformed UTF-8 is outside the Python comparator's input domain. The DLL
orders each invalid byte after Unicode scalar values and reports it via
`sqlite3_log` with `SQLITE_MISMATCH`. SQLite only delivers these log messages
if the host has configured a log callback; the SQL statement does not
necessarily fail. Validate input separately when malformed text must be
rejected.

The DLL has a Windows version resource, currently `0.1.0.0`, defined in
[rmnocase.rc](./rmnocase.rc). Update both numeric and string version fields
there when changing the version.

To rebuild from [rmnocase.c](./rmnocase.c), the version resource, the bundled
SQLite headers, and [rmnocase_unicode.h](./rmnocase_unicode.h), use
[RMNOCASE_surrogate.vcxproj](./RMNOCASE_surrogate.vcxproj) with MSBuild, the Visual C++ v145
toolset and a Windows SDK. From this folder, with MSBuild on your PATH:

```cmd
msbuild RMNOCASE_surrogate.vcxproj /t:Rebuild /p:Configuration=Release /p:Platform=x64
```

To remove the Release x64 build outputs, including the DLL, run:

```cmd
msbuild RMNOCASE_surrogate.vcxproj /t:Clean /p:Configuration=Release /p:Platform=x64
```

Run the rebuild command above to create the DLL again.

The default Release x64 build writes the DLL to `x64\Release` and intermediate
files to `RMNOCASE.298CB660\x64\Release`, relative to the project folder.
Any older DLL in the project folder is not updated by this build.
The header can be regenerated with
`python generate_unicode_tables.py` using a Python installation with Unicode
17.0.0; the generator rejects other Unicode versions and uses the observed
case-fold and mark exceptions defined in `insert_test_data.py`. Run the DLL and Python
regressions with:

```powershell
python -m unittest discover -s . -p 'test_*.py'
```

Run this test command from the repository root with Python using Unicode
17.0.0 and SQLite extension loading available, after building the DLL.

## How RootsMagic's ordering is read

`PlaceTable.Name` uses `RMNOCASE`, and `idxPlaceName` indexes that column.
RootsMagic's **Tools > Rebuild indexes** rebuilds the index using its own
collation. [query_sorted_data.py](./query_sorted_data.py) then opens the
database read-only and runs:

```sql
SELECT PlaceID, Name
FROM PlaceTable INDEXED BY idxPlaceName
WHERE PlaceType = 0
ORDER BY Name;
```

`INDEXED BY` forces the named index. The script checks `EXPLAIN QUERY PLAN`
to verify that the index is used and that SQLite does not create a temporary
sorting B-tree. It registers the approximation so SQLite recognizes the
`RMNOCASE` name; the verified index scan reads the existing index order rather
than sorting the rows using that approximation.

This only reflects RootsMagic's ordering if RootsMagic was the last program to
rebuild that index. The query selects all type-0 places, not necessarily only
the test places. The script displays the results and overwrites
[sorted_output.txt](./sorted_output.txt); it does not modify the database.

## Testing equality and ordering

An index listing alone can make equal strings look merely adjacent. To test a
pair, insert four records with a common prefix and ascending `PlaceID`s:

```text
ID 1: prefix + A
ID 2: prefix + B
ID 3: prefix + B
ID 4: prefix + A
```

`PlaceID` is the integer primary key and therefore the SQLite rowid. SQLite
uses the rowid to order entries whose indexed values compare equal. After
RootsMagic rebuilds the index, the relative order of these four entries shows:

- `1, 2, 3, 4`: A and B compare equal.
- `1, 4, 2, 3`: A sorts before B.
- `2, 3, 1, 4`: B sorts before A.

These are observations for the tested strings and prefixes, not a proof of
behavior for all possible inputs.

## Results so far

On RootsMagic 12 for Windows, the approximation matched:

- The observed index order of the initial 116 test places.
- A first set of 11 paired comparisons and a further 72 pairs covering
  punctuation, digits, accents, ligatures, and several scripts.
- A batch of 439 pairs emphasizing case-folding, combining marks, and Unicode
  boundary cases.
- A reproducible set of 1,024 varied pairs, using random seed `20261123`,
  including mixed scripts, realistic place-like strings, punctuation, and
  Unicode boundaries. All matched; RootsMagic also corrected a deliberately
  reversed control pair. The exact inputs and observed comparison results are
  saved in [rmnocase_seeded_observations.json](./rmnocase_seeded_observations.json).

As a control, one pair's order was deliberately reversed in a disposable
database's index. RootsMagic's rebuild changed it back to the observed order.
The broader tests do not establish equivalence for all Unicode strings or for
other RootsMagic versions and operating systems.

### European and Japanese language round

A second disposable database was copied from the read-only empty RootsMagic 12
database, and its deliberately reversed control pair was verified after
RootsMagic rebuilt its indexes. It contained 34,776 distinct comparison
pairs, recorded in
[rmnocase-language-observations.json](./rmnocase-language-observations.json):

| Group | Selected characters | Comparison pairs |
| --- | ---: | ---: |
| Latin | 1,223 | 2,820 |
| Cyrillic | 410 | 766 |
| Greek | 344 | 1,204 |
| Japanese-related | 28,854 | 29,971 |
| Additional name examples | — | 15 |

The character sets are defined in [language_round.py](./language_round.py).
The Japanese-related set includes kana, all assigned letters in CJK Unified
Ideographs and Extension A, compatibility ideographs, selected half-width
kana, and one supplementary ideograph (`𠮷`). Many of those CJK characters
also occur in other languages. It does not cover every Japanese name character,
every supplementary CJK extension, or all possible combinations. The cases
compare neighboring selected characters, case and normalization variants,
and example names; they do not compare every character against every other.

The original approximation differed on 18 pairs. Eight capital-letter
case-fold mappings accounted for all 18; the updated implementation keeps
those characters unchanged instead of applying Python's newer mappings.
All 34,776 recorded comparisons now match, as do the earlier observations.
This suggests a Unicode-data-version difference, but does not establish
RootsMagic's exact Unicode version or behavior for untested characters.

[language_round.py](./language_round.py) can prepare the working database
and analyze its index after a RootsMagic rebuild. It refuses to overwrite the
existing working database, plan, or observations. The saved plan maps the
case IDs to the database rows; keep it if the experiment needs to be audited
or resumed.

### Extended characters and Arabic mark probe

After RootsMagic 12.1.3.0 for Windows rebuilt another disposable database,
the reversed control was restored and 79,148 comparisons were recorded in
[rmnocase-extended-observations.json](./rmnocase-extended-observations.json):
74,399 supplementary CJK adjacent pairs, 246 Hebrew, 1,407 Arabic, 172
Armenian, 343 Georgian, 17 earlier examples, and 2,564 additional pairs.
The earlier approximation differed on ten pairs involving four Arabic marks.

A separate 100-pair probe compared those marks alone, after Latin and Arabic
bases, and with other combining marks. Its restored control and results are
recorded in [rmnocase-arabic-probe-plan.json](./rmnocase-arabic-probe-plan.json)
and [rmnocase-arabic-probe-observations.json](./rmnocase-arabic-probe-observations.json).
Treating the four marks as retained, combining-class-zero boundaries matches
all the probe observations as well as all extended and previous recorded pairs.
That is an evidence-based approximation, not proof of RootsMagic's internal
Unicode version or of its behavior in every surrounding sequence.

Use `python language_round.py prepare --extended` or `--arabic-probe` to
prepare a round, then rebuild its indexes in RootsMagic and run the matching
`analyze` command with the same option. The script refuses to overwrite an
existing database, plan, or observations.

[test_insert_test_data.py](./test_insert_test_data.py) retains the original
order, selected pairwise observations, and all 1,024 seeded observations as
regression tests. From the repository root, run them with:

```powershell
python -m unittest discover -s . -p 'test_insert_test_data.py'
```

The current stopping point is zero unexplained mismatches across these targeted
and varied checks, not a claim of exact equivalence. Rerun the comparison
against RootsMagic after changing RootsMagic, Python, Unicode data, or platform;
add tests for any new mismatches.

## Safe workflow

Use a disposable test database. Close it in RootsMagic before running the
insert utility. Because its approximation may differ from the collation used
to build existing indexes, the insert utility first runs `REINDEX RMNOCASE`
using its own approximation, then inserts the data in the same transaction.
Afterward, open the database in RootsMagic and rebuild indexes before reading
RootsMagic's order or using the file there.

Changing the collation used with an existing index without rebuilding it can
produce incorrect results or index errors. Do not treat this approximation as
safe for a real genealogy database. Python's Unicode data and RootsMagic's
behavior may also vary between versions or platforms.
