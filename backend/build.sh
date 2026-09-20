set -o errexit

pip install -r requirements.txt
python -m playwright install chromium

python manage.py collectstatic --no-input
python manage.py migrate