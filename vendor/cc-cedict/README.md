# CC-CEDICT source data

`cedict.txt.gz` was downloaded from the official MDBG CC-CEDICT export:

<https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz>

The archive includes its own attribution and license header. CC-CEDICT is
licensed under Creative Commons Attribution-ShareAlike 4.0 International:

<https://creativecommons.org/licenses/by-sa/4.0/>

The build script reads release metadata directly from that header and records
it in `public/data/manifest.json`.
