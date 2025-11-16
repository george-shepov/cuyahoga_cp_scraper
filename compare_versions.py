#!/usr/bin/env python3
"""
Compare multiple versions of the same case to detect docket tampering
Usage: python3 compare_versions.py CR-23-684826-A
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from difflib import unified_diff

def load_case_versions(case_id: str) -> List[Dict[str, Any]]:
    """Load all saved versions of a case"""
    versions = []
    
    # Search in out/ directory for all JSON files
    for json_file in Path("out").rglob("*.json"):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if data.get("metadata", {}).get("case_id") == case_id:
                    versions.append({
                        "file": str(json_file),
                        "scraped_at": data.get("metadata", {}).get("scraped_at"),
                        "data": data
                    })
        except:
            continue
    
    # Sort by scrape time
    versions.sort(key=lambda x: x["scraped_at"])
    return versions

def compare_dockets(old_docket: List[Dict], new_docket: List[Dict]) -> Dict[str, Any]:
    """Compare two docket versions and detect changes"""
    changes = {
        "entries_added": [],
        "entries_removed": [],
        "entries_modified": [],
        "total_old": len(old_docket),
        "total_new": len(new_docket)
    }
    
    # Create lookup by date+description for matching
    old_entries = {f"{e.get('proceeding_date', '')}|{e.get('description', '')[:100]}": e for e in old_docket}
    new_entries = {f"{e.get('proceeding_date', '')}|{e.get('description', '')[:100]}": e for e in new_docket}
    
    # Find removed entries
    for key, entry in old_entries.items():
        if key not in new_entries:
            changes["entries_removed"].append({
                "date": entry.get("proceeding_date"),
                "type": entry.get("document_type"),
                "description": entry.get("description", "")[:200]
            })
    
    # Find added entries
    for key, entry in new_entries.items():
        if key not in old_entries:
            changes["entries_added"].append({
                "date": entry.get("proceeding_date"),
                "type": entry.get("document_type"),
                "description": entry.get("description", "")[:200]
            })
    
    # Find modified entries (same date but different content)
    old_by_date = {}
    for e in old_docket:
        date = e.get("proceeding_date", "")
        if date not in old_by_date:
            old_by_date[date] = []
        old_by_date[date].append(e)
    
    new_by_date = {}
    for e in new_docket:
        date = e.get("proceeding_date", "")
        if date not in new_by_date:
            new_by_date[date] = []
        new_by_date[date].append(e)
    
    for date in old_by_date:
        if date in new_by_date:
            old_desc = " ".join(e.get("description", "") for e in old_by_date[date])
            new_desc = " ".join(e.get("description", "") for e in new_by_date[date])
            if old_desc != new_desc:
                changes["entries_modified"].append({
                    "date": date,
                    "old_count": len(old_by_date[date]),
                    "new_count": len(new_by_date[date]),
                    "old_desc": old_desc[:200],
                    "new_desc": new_desc[:200]
                })
    
    return changes

def compare_attorneys(old_attorneys: List[Dict], new_attorneys: List[Dict]) -> Dict[str, Any]:
    """Compare attorney lists"""
    changes = {
        "added": [],
        "removed": [],
        "total_old": len(old_attorneys),
        "total_new": len(new_attorneys)
    }
    
    old_names = {a.get("name") for a in old_attorneys}
    new_names = {a.get("name") for a in new_attorneys}
    
    for name in old_names - new_names:
        changes["removed"].append(name)
    
    for name in new_names - old_names:
        changes["added"].append(name)
    
    return changes

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 compare_versions.py CR-XX-XXXXXX-X")
        sys.exit(1)
    
    case_id = sys.argv[1]
    versions = load_case_versions(case_id)
    
    if len(versions) < 2:
        print(f"Found only {len(versions)} version(s) of {case_id}")
        print("Need at least 2 versions to compare")
        sys.exit(0)
    
    print(f"\n{'='*80}")
    print(f"DOCKET TAMPERING DETECTION REPORT")
    print(f"Case: {case_id}")
    print(f"Versions found: {len(versions)}")
    print(f"{'='*80}\n")
    
    # Compare each version with the previous one
    for i in range(1, len(versions)):
        old_ver = versions[i-1]
        new_ver = versions[i]
        
        print(f"\n{'─'*80}")
        print(f"COMPARISON #{i}")
        print(f"Old: {old_ver['scraped_at']} ({old_ver['file']})")
        print(f"New: {new_ver['scraped_at']} ({new_ver['file']})")
        print(f"{'─'*80}\n")
        
        # Compare dockets
        old_docket = old_ver["data"].get("docket", [])
        new_docket = new_ver["data"].get("docket", [])
        docket_changes = compare_dockets(old_docket, new_docket)
        
        print(f"📋 DOCKET CHANGES:")
        print(f"   Total entries: {docket_changes['total_old']} → {docket_changes['total_new']}")
        
        if docket_changes["entries_removed"]:
            print(f"\n   🚨 REMOVED ENTRIES ({len(docket_changes['entries_removed'])}):")
            for entry in docket_changes["entries_removed"]:
                print(f"      - {entry['date']} [{entry['type']}]: {entry['description'][:150]}")
        
        if docket_changes["entries_added"]:
            print(f"\n   ✅ ADDED ENTRIES ({len(docket_changes['entries_added'])}):")
            for entry in docket_changes["entries_added"]:
                print(f"      + {entry['date']} [{entry['type']}]: {entry['description'][:150]}")
        
        if docket_changes["entries_modified"]:
            print(f"\n   ⚠️  MODIFIED ENTRIES ({len(docket_changes['entries_modified'])}):")
            for entry in docket_changes["entries_modified"]:
                print(f"      ~ {entry['date']}: Count {entry['old_count']} → {entry['new_count']}")
                if entry['old_desc'] != entry['new_desc']:
                    print(f"        OLD: {entry['old_desc']}")
                    print(f"        NEW: {entry['new_desc']}")
        
        if not any([docket_changes["entries_removed"], docket_changes["entries_added"], docket_changes["entries_modified"]]):
            print("   ✓ No docket changes detected")
        
        # Compare attorneys
        old_attorneys = old_ver["data"].get("attorneys", [])
        new_attorneys = new_ver["data"].get("attorneys", [])
        attorney_changes = compare_attorneys(old_attorneys, new_attorneys)
        
        print(f"\n👔 ATTORNEY CHANGES:")
        print(f"   Total attorneys: {attorney_changes['total_old']} → {attorney_changes['total_new']}")
        
        if attorney_changes["removed"]:
            print(f"   🚨 REMOVED: {', '.join(attorney_changes['removed'])}")
        
        if attorney_changes["added"]:
            print(f"   ✅ ADDED: {', '.join(attorney_changes['added'])}")
        
        if not any([attorney_changes["removed"], attorney_changes["added"]]):
            print("   ✓ No attorney changes detected")
        
        # Compare costs
        old_costs = len(old_ver["data"].get("costs", []))
        new_costs = len(new_ver["data"].get("costs", []))
        if old_costs != new_costs:
            print(f"\n💰 COSTS CHANGED: {old_costs} → {new_costs}")
    
    print(f"\n{'='*80}")
    print("RECOMMENDATION: Save all versions as evidence of any tampering")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
