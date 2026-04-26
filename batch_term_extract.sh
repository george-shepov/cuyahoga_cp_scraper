#!/usr/bin/env bash
# Batch download PDFs and extract grand jury term for cases 684824 down to 684796
# Usage: bash batch_term_extract.sh

cd "$(dirname "$0")"

RESULT_FILE="term_extraction_results.txt"
echo "Case Number | Grand Jury Term" > "$RESULT_FILE"
echo "------------|----------------" >> "$RESULT_FILE"

# Already extracted manually:
echo "CR-23-684826-A | May of 2023" >> "$RESULT_FILE"
echo "CR-23-684825-A | September of 2023" >> "$RESULT_FILE"
echo "CR-23-684824-A | May of 2023" >> "$RESULT_FILE"
echo "CR-23-684823-A | NO INDICTMENT PDF FOUND" >> "$RESULT_FILE"
echo "CR-23-684822-A | NO INDICTMENT PDF FOUND" >> "$RESULT_FILE"
echo "CR-23-684821-A | NO INDICTMENT PDF FOUND" >> "$RESULT_FILE"
echo "CR-23-684820-A | NO INDICTMENT PDF FOUND" >> "$RESULT_FILE"
echo "CR-23-684819-A | September of 2023" >> "$RESULT_FILE"
echo "CR-23-684818-A | September of 2023" >> "$RESULT_FILE"
echo "CR-23-684817-A | NO INDICTMENT PDF FOUND" >> "$RESULT_FILE"
echo "CR-23-684816-A | May of 2023" >> "$RESULT_FILE"
echo "CR-23-684815-A | September of 2023" >> "$RESULT_FILE"
echo "CR-23-684814-A | NO INDICTMENT PDF FOUND" >> "$RESULT_FILE"
echo "CR-23-684813-A | NO INDICTMENT PDF FOUND" >> "$RESULT_FILE"
echo "CR-23-684812-A | May of 2023" >> "$RESULT_FILE"
echo "CR-23-684811-A | September of 2023" >> "$RESULT_FILE"
echo "CR-23-684810-A | NO INDICTMENT PDF FOUND" >> "$RESULT_FILE"
echo "CR-23-684809-A | NO INDICTMENT PDF FOUND" >> "$RESULT_FILE"

for N in $(seq 684808 -1 684796); do
    CASE_ID="CR-23-${N}-A"
    PDF_DIR="out/2023/pdfs/${CASE_ID}"
    START=$((N + 1))

    echo ""
    echo "=== Processing $CASE_ID ==="

    # Download PDFs if not already present
    if [ ! -d "$PDF_DIR" ]; then
        echo "Downloading CR-only PDFs for $CASE_ID ..."
        python3 main.py scrape \
            --year 2023 \
            --start "$START" \
            --limit 1 \
            --direction down \
            --headless \
            --delay-ms 1000 \
            --download-pdfs \
            --pdf-types CR \
            --pdf-cases "$CASE_ID"
    else
        echo "PDF dir already exists: $PDF_DIR"
    fi

    # Find CR-type (indictment) PDF
    CR_PDF=$(find "$PDF_DIR" -name "*_CR_*.pdf" 2>/dev/null | sort | head -1)

    if [ -z "$CR_PDF" ]; then
        echo "  WARNING: No CR-type PDF found for $CASE_ID"
        echo "${CASE_ID} | NO INDICTMENT PDF FOUND" >> "$RESULT_FILE"
        continue
    fi

    echo "  Found indictment PDF: $CR_PDF"

    # Extract the term
    TERM=$(pdftotext "$CR_PDF" - 2>/dev/null | grep -A1 "The Term Of" | tail -1 | sed "s/^[[:space:]']*//;s/[[:space:]]*$//")

    if [ -z "$TERM" ]; then
        # Try alternate pattern
        TERM=$(pdftotext "$CR_PDF" - 2>/dev/null | grep -E "(January|February|March|April|May|June|July|August|September|October|November|December) of 20[0-9][0-9]" | head -1 | sed "s/^[[:space:]']*//;s/[[:space:]]*$//")
    fi

    if [ -z "$TERM" ]; then
        echo "  WARNING: Could not extract term from $CR_PDF"
        echo "${CASE_ID} | TERM NOT FOUND IN PDF" >> "$RESULT_FILE"
    else
        echo "  Term: $TERM"
        echo "${CASE_ID} | ${TERM}" >> "$RESULT_FILE"
    fi

done

echo ""
echo "========================================"
echo "COMPLETE. Results saved to: $RESULT_FILE"
echo "========================================"
cat "$RESULT_FILE"
