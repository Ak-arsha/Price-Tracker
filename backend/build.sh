set -o errexit

pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH=0 python -m playwright install chromium

python manage.py collectstatic --no-input
python manage.py migrate