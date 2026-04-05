You are an autonomous browser agent. Complete the entire task end-to-end without stopping midway.

Website:
https://www.bseindia.com/Indices/IndexArchiveData.html

Objective:
Download CSV files for every available index under:
- Report = "Total returns Index Values"
- Index Type = "Equity"
- Sub-IndexType = "Sectoral Indices","Strategy Indices","Thematic Indices"

For each index, download data for these date ranges:
1. 01-Jan-2026 to 05-Apr-2026
2. 01-Jan-2025 to 31-Dec-2025
3. 01-Jan-2024 to 31-Dec-2024
4. 01-Jan-2023 to 31-Dec-2023
5. 01-Jan-2022 to 31-Dec-2022
6. 01-Jan-2021 to 31-Dec-2021
7. 01-Jan-2020 to 31-Dec-2020
8. 01-Jan-2019 to 31-Dec-2019
9. 01-Jan-2018 to 31-Dec-2018
10. 01-Jan-2017 to 31-Dec-2017
11. 01-Jan-2016 to 31-Dec-2016
12. 01-Jan-2015 to 31-Dec-2015

Main rules:
- Process ALL index options one by one from the "Select an Index" dropdown.
- Do not skip any index.
- Do not stop after the first successful file.
- Continue until all index options and all date ranges are attempted.
- If a combination returns no data, record it and continue.
- If one index fails, continue with the remaining indices.

Detailed browser steps:
1. Open the historical data page.
2. Select the section or tab named "Total returns Index Values".
3. Set "Select an Index Type" = "Equity".
4. Set "Select a Sub-IndexType" = "Broad based Indices".
5. Open the "Select an Index" dropdown and first capture the full list of all available index names.
6. Maintain that list in memory and process them sequentially.
7. For each index:
   a. Re-select:
      - "Total returns Index Values"
      - "Equity"
      - "Broad based Indices"
      if the page state has reset.
   b. Choose the current index from "Select an Index".
   c. For each date range listed above:
      - Fill start date exactly as specified.
      - Fill end date exactly as specified.
      - Click "Submit".
      - Wait for the results area on the right side to load completely.
      - Search for the "csv format" link.
      - If found, click it and download the file.
      - If "No Data Found" or equivalent appears, log that combination as no-data and continue.
   d. After all date ranges for the current index are completed, move to the next index.

Download and file organization rules:
- Create a parent folder:
  nifty_total_returns_equity_broad_based_indices
- Create one subfolder per index.
- Save each CSV with this filename format:
  <IndexName>_<from_yyyy-mm-dd>_to_<to_yyyy-mm-dd>.csv
- Replace spaces with underscores.
- Remove or replace illegal filename characters such as / \ : * ? " < > | with underscores.
- Examples:
  NIFTY_50_2025-01-01_to_2025-12-31.csv
  NIFTY_MIDCAP_150_2024-01-01_to_2024-12-31.csv

Progress tracking:
Maintain a structured progress log during execution with:
- index_name
- start_date
- end_date
- status = downloaded / no_data / failed
- saved_filename if downloaded
- retry_count if retried

Resilience and retry rules:
- If a click or selection fails, retry up to 2 times.
- If the page reloads or resets, restore the selections and continue from the last unfinished index/date range.
- If the "csv format" link is not immediately visible, scroll the results panel and inspect the right side carefully.
- If a stale download occurs, rename it correctly.
- If duplicate files are downloaded due to retry, keep only one correctly named file.
- If date input gets auto-formatted incorrectly, clear and re-enter it.
- Never abandon the full job because of one bad interaction.

Completion verification:
Before finishing:
- Confirm every index option captured from "Select an Index" was attempted.
- Confirm each attempted index was run for all 12 date ranges.
- Confirm files are stored in the correct folders with the correct naming pattern.
- Produce a final summary with:
  - total index options found
  - total index options completed
  - total CSVs downloaded
  - total no-data combinations
  - total failed combinations
  - list of failed index/date combinations
  - confirmation that all available indices under Equity > Broad based Indices were attempted

Important execution style:
- Be careful and methodical.
- Prefer stable interaction over speed.
- Wait for UI updates before the next action.
- Do not ask the user follow-up questions.
- Do not stop until the full workflow is done.