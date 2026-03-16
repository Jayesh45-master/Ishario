## Ishario (local setup)

### 1) Create / activate Conda env

From the repo root:

```powershell
conda env create -f environment.yml
conda activate ishario
```

### 2) Configure MySQL

Ishario uses **two MySQL databases** by default:
- `ISHARIO_DB_NAME` (default `ishario_db`) for admin + profiles
- `SIGNEASE_DB_NAME` (default `signease`) for auth + sign images

Set these environment variables (PowerShell examples):

```powershell
$env:ISHARIO_DB_HOST="localhost"
$env:ISHARIO_DB_USER="root"
$env:ISHARIO_DB_PASS="your_mysql_password"
$env:ISHARIO_DB_NAME="ishario_db"

$env:SIGNEASE_DB_HOST="localhost"
$env:SIGNEASE_DB_USER="root"
$env:SIGNEASE_DB_PASS="your_mysql_password"
$env:SIGNEASE_DB_NAME="signease"
```

Initialize databases + tables:

```powershell
python scripts/init_mysql.py
```

Optional: seed an admin account for `admin.py` (plaintext password, dev only):

```powershell
$env:ISHARIO_SEED_ADMIN_EMAIL="admin@example.com"
$env:ISHARIO_SEED_ADMIN_PASSWORD="admin123"
python scripts/init_mysql.py
```

### 3) Run the apps

Main app (port 5000):

```powershell
cd Ishario-main
python app.py
```

Admin app (port 5001):

```powershell
cd Ishario-main
python admin.py
```

### 4) AI Chatbot (optional)

The dashboard includes an AI Tutor chat widget that calls the backend `/api/chat` endpoint.

Set:

```powershell
$env:OPENAI_API_KEY="your_key_here"
# optional:
$env:OPENAI_MODEL="gpt-4o-mini"
```

### Common fixes

- **`Access denied for user 'root'@'localhost'`**: set the correct `*_DB_USER` / `*_DB_PASS` and run `python scripts/init_mysql.py`.
- **Missing `model.h5`**: ML is optional; `/predict` needs a trained model. Set `ISHARIO_MODEL_PATH` to point to your model file if it isn't in the working directory.
