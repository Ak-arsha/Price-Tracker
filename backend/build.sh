set -o errexit

pip install -r requirements.txt
python -m playwright install --with-deps chromium

python manage.py collectstatic --no-input
python manage.py migrate