#!/usr/bin/env python3
"""
Import existing JSON case files into PostgreSQL and MongoDB
Calculates analytics for all imported cases
"""

import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()


class DataImporter:
    """Import scraped case data into databases"""
    
    def __init__(self, data_dir: str = "out"):
        self.data_dir = Path(data_dir)
        self.stats = {
            "total_files": 0,
            "imported": 0,
            "errors": 0,
            "skipped": 0
        }
    
    def find_json_files(self) -> List[Path]:
        """Find all JSON case files"""
        json_files = []
        for year_dir in self.data_dir.iterdir():
            if year_dir.is_dir():
                json_files.extend(year_dir.glob("*.json"))
        return sorted(json_files)
    
    async def import_to_mongodb(self, case_data: Dict[str, Any], file_path: Path):
        """Import case to MongoDB as raw document"""
        # TODO: Implement MongoDB import
        # from database.mongo_client import get_mongo_db
        # db = await get_mongo_db()
        # collection = db.raw_cases
        # 
        # document = {
        #     "case_number": case_data["metadata"]["case_number"],
        #     "year": case_data["metadata"]["year"],
        #     "scraped_at": case_data["metadata"]["scraped_at"],
        #     "data": case_data,
        #     "source_file": str(file_path),
        #     "imported_at": datetime.utcnow().isoformat()
        # }
        # 
        # await collection.update_one(
        #     {"case_number": document["case_number"]},
        #     {"$set": document},
        #     upsert=True
        # )
        pass
    
    async def import_to_postgres(self, case_data: Dict[str, Any]):
        """Import case to PostgreSQL with normalized structure"""
        # TODO: Implement PostgreSQL import
        # from database.postgres_client import get_db_session
        # from database.models_postgres import Case, Defendant, Judge, Charge, etc.
        # 
        # async with get_db_session() as session:
        #     # Create or get judge
        #     judge_name = case_data["summary"]["fields"].get("Judge:", "Unknown")
        #     judge = await get_or_create_judge(session, judge_name)
        #     
        #     # Create case
        #     case = Case(
        #         case_number=case_data["metadata"]["case_number"],
        #         year=case_data["metadata"]["year"],
        #         judge_id=judge.id,
        #         ...
        #     )
        #     session.add(case)
        #     
        #     # Add charges, defendants, attorneys, etc.
        #     ...
        #     
        #     await session.commit()
        pass
    
    async def calculate_quadrant(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate quadrant analysis for case"""
        from services.quadrant_analyzer import QuadrantAnalyzer
        
        analyzer = QuadrantAnalyzer()
        return analyzer.analyze_case(case_data)
    
    async def import_file(self, file_path: Path) -> bool:
        """Import a single JSON file"""
        try:
            with open(file_path, 'r') as f:
                case_data = json.load(f)
            
            # Import to both databases
            await self.import_to_mongodb(case_data, file_path)
            await self.import_to_postgres(case_data)
            
            # Calculate quadrant analysis
            quadrant = await self.calculate_quadrant(case_data)
            
            # Store quadrant analysis in MongoDB
            # TODO: Store quadrant results
            
            self.stats["imported"] += 1
            return True
            
        except Exception as e:
            console.print(f"[red]Error importing {file_path.name}: {e}[/red]")
            self.stats["errors"] += 1
            return False
    
    async def import_all(self):
        """Import all JSON files"""
        console.print("[bold blue]🔍 Finding JSON files...[/bold blue]")
        json_files = self.find_json_files()
        self.stats["total_files"] = len(json_files)
        
        console.print(f"[green]Found {len(json_files)} case files[/green]")
        console.print()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task(
                "[cyan]Importing cases...",
                total=len(json_files)
            )
            
            for file_path in json_files:
                await self.import_file(file_path)
                progress.update(task, advance=1)
        
        console.print()
        console.print("[bold green]✅ Import Complete![/bold green]")
        console.print()
        console.print(f"Total files: {self.stats['total_files']}")
        console.print(f"[green]Imported: {self.stats['imported']}[/green]")
        console.print(f"[red]Errors: {self.stats['errors']}[/red]")
        console.print(f"[yellow]Skipped: {self.stats['skipped']}[/yellow]")


async def main():
    """Main import function"""
    console.print("[bold]Cuyahoga Court Data Import[/bold]")
    console.print("=" * 50)
    console.print()
    
    importer = DataImporter(data_dir="out")
    await importer.import_all()
    
    console.print()
    console.print("[bold blue]Next steps:[/bold blue]")
    console.print("1. Calculate analytics: python scripts/calculate_analytics.py")
    console.print("2. Start API server: cd deploy && docker-compose up -d api")
    console.print("3. View API docs: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(main())

