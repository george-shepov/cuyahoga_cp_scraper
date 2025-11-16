#!/usr/bin/env python3
"""
Scan all 2023 case PDFs for Brad B Davis metadata and other anomalies.
Cross-reference with Judge Saffold cases to find patterns.
"""

import json
import subprocess
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def get_pdf_author(pdf_path):
    """Extract Author field from PDF using exiftool"""
    try:
        result = subprocess.run(
            ['exiftool', '-Author', '-Creator', '-Title', str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        metadata = {}
        for line in result.stdout.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()
        
        return metadata
    except Exception as e:
        return {}

def scan_all_pdfs():
    """Scan all PDFs in out/2023/pdfs/"""
    results = {
        'brad_davis_docs': [],
        'author_stats': defaultdict(int),
        'creator_stats': defaultdict(int),
        'title_stats': defaultdict(int),
        'total_pdfs': 0,
        'cases_scanned': set(),
        'judge_saffold_cases': [],
        'anomalies': []
    }
    
    pdfs_dir = Path('out/2023/pdfs')
    if not pdfs_dir.exists():
        print(f"Directory {pdfs_dir} not found")
        return results
    
    # Find all PDFs
    all_pdfs = list(pdfs_dir.glob('**/*.pdf'))
    total = len(all_pdfs)
    
    print(f"Found {total} PDFs to analyze...")
    print("=" * 80)
    
    for idx, pdf_path in enumerate(all_pdfs, 1):
        if idx % 100 == 0:
            print(f"Progress: {idx}/{total} ({idx/total*100:.1f}%)")
        
        # Extract case ID from path
        case_id = pdf_path.parent.name
        results['cases_scanned'].add(case_id)
        results['total_pdfs'] += 1
        
        # Get metadata
        metadata = get_pdf_author(pdf_path)
        
        author = metadata.get('Author', '').strip()
        creator = metadata.get('Creator', '').strip()
        title = metadata.get('Title', '').strip()
        
        # Track statistics
        if author:
            results['author_stats'][author] += 1
        if creator:
            results['creator_stats'][creator] += 1
        if title:
            results['title_stats'][title] += 1
        
        # Check for Brad B Davis
        if 'brad' in author.lower() or 'davis' in author.lower():
            results['brad_davis_docs'].append({
                'case_id': case_id,
                'filename': pdf_path.name,
                'path': str(pdf_path),
                'author': author,
                'creator': creator,
                'title': title
            })
        
        # Check for other personal names (not software)
        if author and 'abbyy' not in author.lower() and 'adobe' not in author.lower():
            results['anomalies'].append({
                'case_id': case_id,
                'filename': pdf_path.name,
                'author': author,
                'creator': creator,
                'title': title
            })
    
    return results

def check_judge_saffold_cases():
    """Find all cases from Judge Saffold"""
    saffold_cases = []
    json_files = list(Path('out/2023').glob('*.json'))
    
    print(f"\nScanning {len(json_files)} case JSON files for Judge Saffold...")
    
    for json_file in json_files:
        try:
            with open(json_file) as f:
                data = json.load(f)
                
            judge = data.get('summary', {}).get('fields', {}).get('Judge Name:', '')
            if 'SAFFOLD' in judge.upper():
                case_id = data.get('metadata', {}).get('case_id', '')
                saffold_cases.append({
                    'case_id': case_id,
                    'judge': judge,
                    'json_file': str(json_file)
                })
        except Exception:
            continue
    
    return saffold_cases

def main():
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "BRAD B DAVIS METADATA FORENSIC SCAN" + " " * 28 + "║")
    print("║" + " " * 20 + "2023 Cuyahoga County Cases" + " " * 31 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Scan all PDFs
    results = scan_all_pdfs()
    
    print()
    print("=" * 80)
    print("SCAN COMPLETE")
    print("=" * 80)
    print(f"Total PDFs scanned: {results['total_pdfs']:,}")
    print(f"Total cases scanned: {len(results['cases_scanned']):,}")
    print()
    
    # Brad B Davis findings
    print("=" * 80)
    print("BRAD B DAVIS DOCUMENTS:")
    print("=" * 80)
    if results['brad_davis_docs']:
        print(f"Found {len(results['brad_davis_docs'])} document(s) with Brad B Davis metadata:")
        print()
        for doc in results['brad_davis_docs']:
            print(f"  Case: {doc['case_id']}")
            print(f"  File: {doc['filename']}")
            print(f"  Author: {doc['author']}")
            print(f"  Creator: {doc['creator']}")
            print(f"  Title: {doc['title']}")
            print(f"  Path: {doc['path']}")
            print()
    else:
        print("No Brad B Davis documents found outside CR-23-684826-A")
    print()
    
    # Other anomalies
    print("=" * 80)
    print("OTHER PERSONAL AUTHOR NAMES:")
    print("=" * 80)
    if results['anomalies']:
        print(f"Found {len(results['anomalies'])} document(s) with personal author names:")
        print()
        # Group by author
        by_author = defaultdict(list)
        for doc in results['anomalies']:
            by_author[doc['author']].append(doc)
        
        for author, docs in sorted(by_author.items()):
            print(f"  Author: {author}")
            print(f"  Document count: {len(docs)}")
            print(f"  Cases: {', '.join(sorted(set(d['case_id'] for d in docs)))}")
            print()
    else:
        print("No other personal author names found")
    print()
    
    # Top creators
    print("=" * 80)
    print("TOP PDF CREATORS:")
    print("=" * 80)
    for creator, count in sorted(results['creator_stats'].items(), key=lambda x: x[1], reverse=True)[:10]:
        pct = count / results['total_pdfs'] * 100
        print(f"  {count:5,} ({pct:5.1f}%) - {creator}")
    print()
    
    # Judge Saffold cases
    print("=" * 80)
    print("JUDGE SAFFOLD CASES:")
    print("=" * 80)
    saffold_cases = check_judge_saffold_cases()
    print(f"Found {len(saffold_cases)} cases with Judge Jeffrey P. Saffold")
    
    # Check if any have PDFs
    saffold_with_pdfs = []
    for case in saffold_cases:
        case_id = case['case_id']
        pdf_dir = Path(f'out/2023/pdfs/{case_id}')
        if pdf_dir.exists():
            pdf_count = len(list(pdf_dir.glob('*.pdf')))
            if pdf_count > 0:
                saffold_with_pdfs.append({
                    **case,
                    'pdf_count': pdf_count,
                    'pdf_dir': str(pdf_dir)
                })
    
    if saffold_with_pdfs:
        print(f"{len(saffold_with_pdfs)} Saffold cases have PDFs downloaded:")
        print()
        for case in saffold_with_pdfs[:10]:  # Show first 10
            print(f"  {case['case_id']}: {case['pdf_count']} PDFs")
    print()
    
    # Save detailed results
    output_file = f"brad_davis_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            'scan_date': datetime.now().isoformat(),
            'total_pdfs': results['total_pdfs'],
            'total_cases': len(results['cases_scanned']),
            'brad_davis_documents': results['brad_davis_docs'],
            'other_anomalies': results['anomalies'],
            'saffold_cases': saffold_cases,
            'saffold_with_pdfs': saffold_with_pdfs,
            'creator_stats': dict(results['creator_stats']),
            'author_stats': dict(results['author_stats']),
            'title_stats': dict(results['title_stats'])
        }, f, indent=2)
    
    print("=" * 80)
    print(f"Detailed results saved to: {output_file}")
    print("=" * 80)

if __name__ == '__main__':
    main()
