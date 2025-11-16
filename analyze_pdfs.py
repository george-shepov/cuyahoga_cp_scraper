#!/usr/bin/env python3
"""
Analyze PDF metadata to detect potential document tampering or administrative manipulation
Usage: python3 analyze_pdfs.py CR-23-684826-A
       python3 analyze_pdfs.py out/2023/pdfs/CR-23-684826-A/
"""

import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import re

def get_pdf_metadata(pdf_path: Path) -> Dict[str, Any]:
    """Extract metadata from PDF using pdfinfo and exiftool"""
    metadata = {
        "file": str(pdf_path),
        "filename": pdf_path.name,
        "size_bytes": pdf_path.stat().st_size,
        "modified_date": datetime.fromtimestamp(pdf_path.stat().st_mtime).isoformat(),
        "created_date": datetime.fromtimestamp(pdf_path.stat().st_ctime).isoformat(),
    }
    
    # Try pdfinfo first
    try:
        result = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip()
    except Exception as e:
        metadata["pdfinfo_error"] = str(e)
    
    # Try exiftool for more detailed metadata
    try:
        result = subprocess.run(
            ["exiftool", "-j", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            exif_data = json.loads(result.stdout)[0]
            metadata["exif"] = exif_data
    except Exception as e:
        metadata["exiftool_error"] = str(e)
    
    return metadata

def analyze_suspicious_patterns(metadata: Dict[str, Any]) -> List[str]:
    """Analyze metadata for suspicious patterns indicating tampering"""
    flags = []
    
    # Check for common PDF editors (not court systems)
    creator = metadata.get("Creator", "").lower()
    producer = metadata.get("Producer", "").lower()
    
    suspicious_creators = [
        "adobe acrobat",
        "microsoft word",
        "microsoft office",
        "libreoffice",
        "openoffice",
        "pdftk",
        "ghostscript",
        "foxit",
        "nitro",
        "nuance",
        "pdf24",
        "cutepdf",
        "novapdf"
    ]
    
    for susp in suspicious_creators:
        if susp in creator or susp in producer:
            flags.append(f"🚨 SUSPICIOUS CREATOR/PRODUCER: {creator or producer} (not court system)")
    
    # Check for creation date vs modification date mismatches
    creation = metadata.get("CreationDate", "")
    mod_date = metadata.get("ModDate", "")
    
    if creation and mod_date and creation != mod_date:
        flags.append(f"⚠️  MODIFIED AFTER CREATION: Created {creation}, Modified {mod_date}")
    
    # Check file modified date vs PDF internal dates
    file_mod = metadata.get("modified_date", "")
    if file_mod and mod_date:
        try:
            # Parse dates and compare
            file_dt = datetime.fromisoformat(file_mod)
            # PDF dates are in format like "D:20231124093045-05'00'"
            if mod_date.startswith("D:"):
                pdf_date_str = mod_date[2:16]  # Extract YYYYMMDDHHMMSS
                pdf_dt = datetime.strptime(pdf_date_str, "%Y%m%d%H%M%S")
                
                diff = abs((file_dt - pdf_dt).total_seconds())
                if diff > 3600:  # More than 1 hour difference
                    flags.append(f"⚠️  FILE TIMESTAMP MISMATCH: File modified {file_dt}, PDF says {pdf_dt} (diff: {diff/3600:.1f} hours)")
        except:
            pass
    
    # Check for missing required court metadata
    if not metadata.get("Title") and not metadata.get("Subject"):
        flags.append("⚠️  MISSING TITLE/SUBJECT: Court documents usually have case numbers in metadata")
    
    # Check for encryption or password protection
    if metadata.get("Encrypted", "no") != "no":
        flags.append(f"🔒 ENCRYPTED: {metadata.get('Encrypted')}")
    
    # Check PDF version (very old or very new might be suspicious)
    pdf_version = metadata.get("PDF version", "")
    if pdf_version:
        try:
            version_num = float(pdf_version)
            if version_num < 1.4:
                flags.append(f"⚠️  OLD PDF VERSION: {pdf_version} (pre-2001, unlikely for modern court system)")
            elif version_num > 1.7:
                flags.append(f"⚠️  NEW PDF VERSION: {pdf_version} (might indicate recent recreation)")
        except:
            pass
    
    # Check for incremental updates (sign of editing)
    if "exif" in metadata:
        exif = metadata["exif"]
        linearized = exif.get("Linearized", "")
        if linearized and "yes" not in linearized.lower():
            # Non-linearized PDFs with multiple updates might be edited
            pass
    
    # Check Author field
    author = metadata.get("Author", "")
    if author and author.lower() not in ["", "unknown", "system", "court"]:
        if not any(court_term in author.lower() for court_term in ["court", "clerk", "justice", "cuyahoga"]):
            flags.append(f"⚠️  SUSPICIOUS AUTHOR: '{author}' (not court-related)")
    
    # Check for form fields (administrative documents often have fillable forms)
    page_count = metadata.get("Pages", "0")
    form_fields = metadata.get("Form", "")
    if form_fields and "none" not in form_fields.lower():
        flags.append(f"📝 HAS FORM FIELDS: Might be fillable/editable document")
    
    return flags

def analyze_date_discrepancies(pdf_files: List[Path], case_id: str) -> List[str]:
    """Analyze dates across multiple PDFs for inconsistencies"""
    discrepancies = []
    
    # Load JSON data for the case if available
    json_files = list(Path("out").rglob(f"*{case_id.replace('CR-', '').replace('-', '_')}*.json"))
    if not json_files:
        return discrepancies
    
    # Get latest JSON
    json_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    try:
        with open(json_files[0], 'r') as f:
            case_data = json.load(f)
        
        docket = case_data.get("docket", [])
        
        # Create a mapping of docket dates to document types
        docket_dates = {}
        for entry in docket:
            date = entry.get("proceeding_date", "")
            doc_type = entry.get("document_type", "")
            desc = entry.get("description", "")
            if date:
                if date not in docket_dates:
                    docket_dates[date] = []
                docket_dates[date].append({"type": doc_type, "desc": desc})
        
        # Check each PDF against docket
        for pdf_path in pdf_files:
            filename = pdf_path.name
            # Extract date from filename (format: MM-DD-YYYY_TYPE_NUM.pdf)
            date_match = re.search(r'(\d{2})-(\d{2})-(\d{4})', filename)
            if date_match:
                month, day, year = date_match.groups()
                pdf_date = f"{month}/{day}/{year}"
                
                # Check if this date exists in docket
                if pdf_date not in docket_dates:
                    discrepancies.append(f"🚨 PDF DATE NOT IN DOCKET: {filename} dated {pdf_date} has no matching docket entry")
                
                # Check metadata date vs filename date
                metadata = get_pdf_metadata(pdf_path)
                creation_date = metadata.get("CreationDate", "")
                if creation_date.startswith("D:"):
                    pdf_create_date = creation_date[2:10]  # YYYYMMDD
                    expected_date = f"{year}{month}{day}"
                    if pdf_create_date != expected_date:
                        discrepancies.append(f"⚠️  FILENAME VS METADATA DATE MISMATCH: {filename} says {pdf_date} but PDF created on {pdf_create_date[:4]}/{pdf_create_date[4:6]}/{pdf_create_date[6:8]}")
    
    except Exception as e:
        discrepancies.append(f"Error analyzing dates: {e}")
    
    return discrepancies

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_pdfs.py CR-XX-XXXXXX-X")
        print("   or: python3 analyze_pdfs.py /path/to/pdfs/")
        sys.exit(1)
    
    arg = sys.argv[1]
    
    # Determine if it's a case ID or directory path
    if Path(arg).is_dir():
        pdf_dir = Path(arg)
        case_id = pdf_dir.name if "CR-" in pdf_dir.name else "Unknown"
    else:
        # It's a case ID, find the PDF directory
        case_id = arg
        # Format: CR-23-684826-A -> 2023/pdfs/CR-23-684826-A
        year = "20" + case_id.split("-")[1]
        pdf_dir = Path(f"out/{year}/pdfs/{case_id}")
        
        if not pdf_dir.exists():
            print(f"PDF directory not found: {pdf_dir}")
            sys.exit(1)
    
    # Find all PDFs
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {pdf_dir}")
        sys.exit(1)
    
    print(f"\n{'='*80}")
    print(f"PDF METADATA ANALYSIS & TAMPERING DETECTION")
    print(f"Case: {case_id}")
    print(f"Directory: {pdf_dir}")
    print(f"PDFs found: {len(pdf_files)}")
    print(f"{'='*80}\n")
    
    # Analyze each PDF
    suspicious_count = 0
    all_metadata = []
    
    for i, pdf_path in enumerate(sorted(pdf_files), 1):
        print(f"\n{'─'*80}")
        print(f"[{i}/{len(pdf_files)}] {pdf_path.name}")
        print(f"{'─'*80}")
        
        metadata = get_pdf_metadata(pdf_path)
        all_metadata.append(metadata)
        flags = analyze_suspicious_patterns(metadata)
        
        # Display key metadata
        print(f"📄 Size: {metadata['size_bytes']:,} bytes")
        print(f"📅 File Modified: {metadata.get('modified_date', 'Unknown')}")
        
        if "Pages" in metadata:
            print(f"📃 Pages: {metadata['Pages']}")
        if "PDF version" in metadata:
            print(f"📌 PDF Version: {metadata['PDF version']}")
        if "Creator" in metadata:
            print(f"🔧 Creator: {metadata['Creator']}")
        if "Producer" in metadata:
            print(f"🏭 Producer: {metadata['Producer']}")
        if "CreationDate" in metadata:
            print(f"📆 Creation Date: {metadata['CreationDate']}")
        if "ModDate" in metadata:
            print(f"✏️  Modification Date: {metadata['ModDate']}")
        if "Title" in metadata and metadata["Title"]:
            print(f"📋 Title: {metadata['Title']}")
        if "Author" in metadata and metadata["Author"]:
            print(f"✍️  Author: {metadata['Author']}")
        
        # Display flags
        if flags:
            suspicious_count += 1
            print(f"\n⚠️  SUSPICIOUS INDICATORS FOUND ({len(flags)}):")
            for flag in flags:
                print(f"   {flag}")
        else:
            print(f"\n✅ No obvious tampering indicators detected")
    
    # Cross-document analysis
    print(f"\n{'='*80}")
    print(f"CROSS-DOCUMENT ANALYSIS")
    print(f"{'='*80}\n")
    
    # Check for date discrepancies
    date_issues = analyze_date_discrepancies(pdf_files, case_id)
    if date_issues:
        print("📅 DATE DISCREPANCIES FOUND:")
        for issue in date_issues:
            print(f"   {issue}")
    else:
        print("✅ No date discrepancies detected")
    
    # Check for inconsistent producers/creators
    creators = [m.get("Creator", "").lower() for m in all_metadata if m.get("Creator")]
    producers = [m.get("Producer", "").lower() for m in all_metadata if m.get("Producer")]
    
    unique_creators = set(creators)
    unique_producers = set(producers)
    
    if len(unique_creators) > 1:
        print(f"\n⚠️  MULTIPLE DIFFERENT CREATORS DETECTED ({len(unique_creators)}):")
        for creator in unique_creators:
            count = creators.count(creator)
            print(f"   - {creator}: {count} document(s)")
        print("   NOTE: Court documents should typically come from same system")
    
    if len(unique_producers) > 1:
        print(f"\n⚠️  MULTIPLE DIFFERENT PRODUCERS DETECTED ({len(unique_producers)}):")
        for producer in unique_producers:
            count = producers.count(producer)
            print(f"   - {producer}: {count} document(s)")
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total PDFs analyzed: {len(pdf_files)}")
    print(f"Suspicious documents: {suspicious_count}")
    print(f"Suspicion rate: {suspicious_count/len(pdf_files)*100:.1f}%")
    
    if suspicious_count > 0:
        print(f"\n⚠️  RECOMMENDATION: {suspicious_count} document(s) show suspicious patterns.")
        print(f"   Consider requesting certified copies from court and comparing metadata.")
        print(f"   Save this analysis as evidence of potential tampering.")
    else:
        print(f"\n✅ No major tampering indicators detected in metadata.")
    
    print(f"\n💾 Detailed metadata saved to: pdf_analysis_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    # Save detailed JSON report
    report = {
        "case_id": case_id,
        "analysis_date": datetime.now().isoformat(),
        "pdf_count": len(pdf_files),
        "suspicious_count": suspicious_count,
        "pdfs": all_metadata,
        "date_discrepancies": date_issues
    }
    
    report_file = f"pdf_analysis_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
