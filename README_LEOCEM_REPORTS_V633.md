# Leocem reporting improvements, v6.3.3

- The Dashboard aggregates latest `script_runs` instead of unrelated `module_cases`, while keeping the old module-case database intact.
- Test Cases & Excel shows real instrumented script events in 11 familiar columns and exports the populated workbook.
- Reports > View report opens HTML directly; Download HTML continues to download.
- PDF print result `fields[]` are shown individually, including mismatches and unmapped values.
- Additional numeric checks are applied to the existing script through a targeted, idempotent migration. Customized scripts are never replaced wholesale.
- The JS failure overlay uses a literal `\\n` string rather than a parser-breaking newline.
- No credentials are requested by this new reporting layer; the Leocem URL test/staging safeguard is unchanged.
