python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install
cp .env.example .env
python main.py --year 2025 --start 706402 --limit 50 --direction both
