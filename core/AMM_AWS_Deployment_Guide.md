# 🚀 AMM — Complete AWS Deployment Guide

> **Audience**: Complete beginner to AWS. Every step is explained in detail.  
> **Stack**: Django 6 + Daphne + Celery + Redis + PostgreSQL (RDS) + S3 + Nginx — all in Docker on EC2  
> **Region**: `eu-north-1` (Stockholm)

---

## 📋 What We Will Create

| Service | Purpose | Cost estimate |
|---|---|---|
| **EC2 t3.small** | Runs your entire app in Docker | ~$15/mo |
| **RDS PostgreSQL t3.micro** | Production database | ~$15/mo |
| **S3 Bucket** | Media files (profile photos, etc.) | ~$1-3/mo |
| **Elastic IP** | Fixed public IP for your server | Free while attached |

---

## 🔑 PHASE 1: AWS IAM Setup (You Already Have This)

You mentioned you have an IAM user. Make sure it has these permissions:
- `AmazonEC2FullAccess`
- `AmazonRDSFullAccess`
- `AmazonS3FullAccess`

If you're not sure, go to **IAM → Users → your user → Add permissions** and attach those policies.

---

## 🪣 PHASE 2: Create the S3 Bucket (for Media Files)

> [!IMPORTANT]
> Do this FIRST — you'll need the bucket name for your `.env.production` file.

### Step 2.1 — Create the Bucket

1. Go to **AWS Console** → search for **S3** → click **S3**
2. Click **Create bucket** (orange button, top right)
3. Fill in:
   - **Bucket name**: `amm-media-eu-north-1` *(use something unique — bucket names are global)*
   - **AWS Region**: `eu-north-1 (Stockholm)`
4. **Object Ownership** section: Select **ACLs disabled (recommended)**
5. **Block Public Access settings**: Keep "Block all public access" checked
6. Leave everything else as default → Click **Create bucket**

### Step 2.2 — Add Bucket Policy

1. Click on your new bucket → **Permissions** tab
2. Scroll to **Bucket policy** → click **Edit**
3. Paste this policy (replace placeholders):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowDjangoAppAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::<YOUR_AWS_ACCOUNT_ID>:user/<YOUR_IAM_USERNAME>"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::amm-media-eu-north-1",
        "arn:aws:s3:::amm-media-eu-north-1/*"
      ]
    }
  ]
}
```

> **Where to find Account ID**: Click your name (top right of AWS Console) — 12-digit number like `123456789012`

4. Click **Save changes**

### Step 2.3 — Add CORS Configuration

1. Still in the bucket → **Permissions** tab → **Cross-origin resource sharing (CORS)** → **Edit**
2. Paste:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "POST", "PUT", "DELETE"],
    "AllowedOrigins": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

3. Click **Save changes**

---

## 🗄️ PHASE 3: Create the RDS PostgreSQL Database

### Step 3.1 — Create a Security Group for RDS

1. Go to **EC2** → left sidebar → **Security Groups** → **Create security group**
2. Fill in:
   - **Security group name**: `amm-rds-sg`
   - **Description**: `Allow PostgreSQL access from AMM EC2`
   - **VPC**: Leave as default
3. **Inbound rules**: Click **Add rule**
   - **Type**: `PostgreSQL` | **Port**: `5432` | **Source**: `0.0.0.0/0` *(we'll tighten this after EC2 is created)*
4. Click **Create security group**

### Step 3.2 — Create the RDS Instance

1. Go to **AWS Console** → search **RDS** → click **RDS**
2. Click **Create database** → **Standard create**
3. **Engine**: PostgreSQL, latest version
4. **Templates**: **Free tier** (gives `db.t3.micro`)
5. **Settings**:
   - DB instance identifier: `amm-db`
   - Master username: `amm_admin`
   - Master password: Set a strong password and write it down!
6. **Connectivity**:
   - Compute resource: `Don't connect to an EC2 compute resource`
   - VPC: Default VPC
   - **Public access**: `No` ← IMPORTANT
   - VPC security groups: Remove default → select `amm-rds-sg`
   - Port: `5432`
7. **Additional configuration** (scroll down, expand):
   - **Initial database name**: `amm_db`
8. Click **Create database** — takes 5-10 minutes

### Step 3.3 — Note the RDS Endpoint

1. Once status is **Available**, click your database
2. Copy the **Endpoint** under Connectivity (e.g., `amm-db.xxxxxxxxxxxx.eu-north-1.rds.amazonaws.com`)
3. Save this for `.env.production`

---

## 🖥️ PHASE 4: Create the EC2 Instance

### Step 4.1 — Create EC2 Security Group

1. Go to **EC2** → **Security Groups** → **Create security group**
2. Name: `amm-ec2-sg`, Description: `AMM EC2 web server`
3. **Inbound rules**:

| Type | Port | Source | Why |
|---|---|---|---|
| SSH | 22 | My IP | Only you can SSH in |
| HTTP | 80 | 0.0.0.0/0 | Public web traffic |
| HTTPS | 443 | 0.0.0.0/0 | For future SSL |

4. Click **Create security group**

### Step 4.2 — Update RDS Security Group to Allow Only EC2

> [!IMPORTANT]
> This is critical — your database should only accept connections from EC2, not the whole internet.

1. Go to **Security Groups** → click `amm-rds-sg`
2. **Edit inbound rules**
3. Change the PostgreSQL rule Source from `0.0.0.0/0` → **Custom** → select `amm-ec2-sg`
4. **Save rules**

### Step 4.3 — Create a Key Pair (for SSH login)

1. Go to **EC2** → **Key Pairs** → **Create key pair**
2. Name: `amm-ec2-key`, Type: RSA, Format: `.ppk` (for PuTTY on Windows)
3. Click **Create key pair** — file downloads automatically
4. **Save to**: `C:\Users\maruf\ssh\amm-ec2-key.ppk`

> [!CAUTION]
> You can NEVER download this key again. If you lose it, you lose SSH access forever!

### Step 4.4 — Launch the EC2 Instance

1. Go to **EC2** → **Instances** → **Launch instances**
2. Fill in:
   - Name: `amm-backend`
   - AMI: Search `Ubuntu` → **Ubuntu Server 24.04 LTS**
   - Instance type: `t3.small`
   - Key pair: `amm-ec2-key`
3. **Network settings** → Edit:
   - Auto-assign public IP: Enable
   - Security groups: Select `amm-ec2-sg`
4. **Storage**: Change `8 GiB` to `20 GiB` gp3
5. Click **Launch instance**

### Step 4.5 — Allocate and Attach an Elastic IP

1. Go to **EC2** → **Elastic IPs** → **Allocate Elastic IP address**
2. Region: `eu-north-1` → **Allocate**
3. Select the new IP → **Actions** → **Associate Elastic IP address**
4. Instance: select `amm-backend` → **Associate**
5. **Write down this Elastic IP** — this is your permanent server address

---

## 🖥️ PHASE 5: Connect to EC2 with PuTTY

> Download PuTTY from https://putty.org if you don't have it.

### Step 5.1 — Connect

1. Open **PuTTY**
2. **Session**:
   - Host Name: `ubuntu@<YOUR_ELASTIC_IP>`
   - Port: `22`
   - Connection type: SSH
3. Left sidebar → **Connection** → **SSH** → **Auth** → **Credentials**:
   - Private key file: Browse → select `amm-ec2-key.ppk`
4. Back to **Session** → Saved Sessions: type `amm-backend` → **Save**
5. Click **Open** → Accept the security alert → You're in! 🎉

---

## ⚙️ PHASE 6: Set Up the EC2 Server

> All commands below run in your PuTTY terminal on EC2.

### Step 6.1 — Install Docker

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install prerequisites
sudo apt-get install -y ca-certificates curl gnupg lsb-release git

# Add Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repo
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker + Docker Compose plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add yourself to docker group (no more sudo needed)
sudo usermod -aG docker ubuntu
newgrp docker

# Enable Docker on boot
sudo systemctl enable docker

# Verify
docker --version        # Should show Docker version
docker compose version  # Should show Docker Compose version
```

### Step 6.2 — Set Up GitHub SSH Deploy Key

```bash
# Generate SSH key for GitHub access
ssh-keygen -t ed25519 -C "amm-ec2-deploy" -f ~/.ssh/github_deploy -N ""

# Show public key — COPY this entire output
cat ~/.ssh/github_deploy.pub

# Configure SSH
cat >> ~/.ssh/config << 'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github_deploy
EOF
chmod 600 ~/.ssh/config
```

Then on GitHub:
1. Your repo → **Settings** → **Deploy keys** → **Add deploy key**
2. Title: `AMM EC2 Server`, Paste the public key, Allow write: NO
3. Click **Add key**

Back on EC2:
```bash
# Test connection
ssh -T git@github.com
# Expected: "Hi username! You've successfully authenticated..."
```

### Step 6.3 — Clone the Repository

```bash
git clone git@github.com:<YOUR_GITHUB_USERNAME>/A-Muslim-Matchmaker-Backend.git ~/amm-backend
cd ~/amm-backend
ls  # Should see Dockerfile, docker-compose.prod.yml, nginx.prod.conf, etc.
```

---

## 🔐 PHASE 7: Configure Environment Variables

### Step 7.1 — Create `.env.production` on EC2

```bash
cd ~/amm-backend
nano .env.production
```

Copy the content from `.env.production.example` in your repo and fill in all values:

```env
SECRET_KEY=<generate below>
DEBUG=False
ALLOWED_HOSTS=<YOUR_ELASTIC_IP>

DB_ENGINE=django.db.backends.postgresql
DB_NAME=amm_db
DB_USER=amm_admin
DB_PASSWORD=<your RDS password>
DB_HOST=<your RDS endpoint>
DB_PORT=5432

USE_S3=True
AWS_ACCESS_KEY_ID=<your IAM key>
AWS_SECRET_ACCESS_KEY=<your IAM secret>
AWS_STORAGE_BUCKET_NAME=amm-media-eu-north-1
AWS_S3_REGION_NAME=eu-north-1

REDIS_HOST=redis
REDIS_PORT=6379

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<your gmail>
EMAIL_HOST_PASSWORD=<gmail app password>

CORS_ALLOWED_ORIGINS=http://<YOUR_ELASTIC_IP>
FRONTEND_URL=<your frontend URL or http://localhost:3000>
BASE_URL=http://<YOUR_ELASTIC_IP>
```

**Generate SECRET_KEY** (run locally):
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Save in nano: `Ctrl+X` → `Y` → `Enter`

```bash
# Protect the file
chmod 600 ~/amm-backend/.env.production
```

---

## 🐳 PHASE 8: Deploy the Application (First Run)

```bash
cd ~/amm-backend

# Build Docker images (3-8 minutes first time)
docker compose -f docker-compose.prod.yml --env-file .env.production build

# Start all containers
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# Watch startup logs
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f
# Press Ctrl+C when you see "Daphne running on 0.0.0.0:8000"

# Check all containers are running
docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

All 5 containers should show **Up (healthy)**:
- `amm_nginx` 
- `amm_django` 
- `amm_celery_worker`
- `amm_celery_beat`
- `amm_redis`

### Create Django Superuser

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production \
    exec django python manage.py createsuperuser
```

### Verify It Works

Open browser → `http://<YOUR_ELASTIC_IP>/api/docs/` → You should see your Swagger docs! ✅  
Open browser → `http://<YOUR_ELASTIC_IP>/admin/` → You should see Django admin! ✅

---

## 🔄 PHASE 9: GitHub Actions Secrets

Go to: GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

### Complete Secrets List

| Secret Name | Value | Notes |
|---|---|---|
| `SECRET_KEY` | Django secret key | Generate with Python command |
| `EC2_HOST` | `<YOUR_ELASTIC_IP>` | e.g., `13.61.142.224` |
| `EC2_USER` | `ubuntu` | Always `ubuntu` for Ubuntu AMI |
| `EC2_SSH_KEY` | Contents of `amm-ec2-key.pem` | OpenSSH format — see note below |
| `AWS_ACCESS_KEY_ID` | Your IAM access key ID | From AWS IAM |
| `AWS_SECRET_ACCESS_KEY` | Your IAM secret access key | From AWS IAM (shown once) |
| `AWS_STORAGE_BUCKET_NAME` | `amm-media-eu-north-1` | Your S3 bucket name |
| `AWS_S3_REGION_NAME` | `eu-north-1` | Fixed |
| `DB_NAME` | `amm_db` | RDS database name |
| `DB_USER` | `amm_admin` | RDS master username |
| `DB_PASSWORD` | Your RDS master password | The password you set |
| `DB_HOST` | `amm-db.xxx.eu-north-1.rds.amazonaws.com` | RDS endpoint |
| `DB_PORT` | `5432` | Fixed for PostgreSQL |
| `EMAIL_HOST_USER` | `maruf.bshs@gmail.com` | Your Gmail |
| `EMAIL_HOST_PASSWORD` | Gmail App Password | From Google Account → Security |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | Google Cloud Console |
| `GOOGLE_WEB_CLIENT_ID` | Google Web Client ID | Google Cloud Console |
| `FRONTEND_URL` | Your frontend URL | e.g., `http://localhost:3000` |
| `CORS_ALLOWED_ORIGINS` | `http://<YOUR_ELASTIC_IP>` | Your Elastic IP |

### Getting EC2_SSH_KEY in OpenSSH Format

**Option A — PuTTYgen (Easiest):**
1. Open PuTTYgen
2. File → Load private key → select `amm-ec2-key.ppk`
3. **Conversions → Export OpenSSH key** → save as `amm-ec2-key.pem`
4. Open `amm-ec2-key.pem` in Notepad → copy everything (including `-----BEGIN...-----` lines)
5. Paste as the `EC2_SSH_KEY` secret value

**Option B — Check if the key works:**  
The key content for GitHub should start with:
```
-----BEGIN OPENSSH PRIVATE KEY-----
```

---

## 🔧 Phase 10: Common Commands Reference

```bash
# Logs
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f django
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f

# Restart
docker compose -f docker-compose.prod.yml --env-file .env.production restart

# Run management commands
docker compose -f docker-compose.prod.yml --env-file .env.production \
    exec django python manage.py <command>

# Manual migration
docker compose -f docker-compose.prod.yml --env-file .env.production \
    exec django python manage.py migrate

# Check deployment configuration
docker compose -f docker-compose.prod.yml --env-file .env.production \
    exec django python manage.py check --deploy

# Pull latest code manually + redeploy
cd ~/amm-backend
git pull origin main
docker compose -f docker-compose.prod.yml --env-file .env.production build --no-cache
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

---

## 🐛 Troubleshooting

### Containers keep crashing
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs django
```
Common causes: wrong DB_HOST, wrong SECRET_KEY, RDS security group blocking EC2

### 502 Bad Gateway
Django container is not healthy yet. Wait 90 seconds. Check logs with command above.

### Can't connect to RDS
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production \
    exec django python -c "
import os, psycopg2
conn = psycopg2.connect(
    dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'],
    password=os.environ['DB_PASSWORD'], host=os.environ['DB_HOST'], port=os.environ['DB_PORT']
)
print('RDS OK'); conn.close()
"
```
If it fails → check security group (Step 4.2)

### S3 media files not working
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production \
    exec django python -c "
import boto3, os
s3 = boto3.client('s3', region_name=os.environ['AWS_S3_REGION_NAME'])
print(s3.list_buckets()['Buckets'])
"
```
If it fails → wrong AWS credentials in .env.production

### CI/CD fails with SSH error
Ensure `EC2_SSH_KEY` is in OpenSSH format (starts with `-----BEGIN OPENSSH PRIVATE KEY-----`), not PPK format.

---

## 🌐 Domain Setup (After App is Working)

1. Point domain's A record to your Elastic IP in your DNS registrar
2. Install Certbot: `sudo apt-get install -y certbot`
3. Stop Nginx: `docker compose -f docker-compose.prod.yml --env-file .env.production stop nginx`
4. Get certificate: `sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com`
5. Start the stack again: `docker compose -f docker-compose.prod.yml --env-file .env.production up -d`
6. Test renewal: `sudo certbot renew --dry-run`

---

## ✅ Files Created/Modified Summary

| File | Status | Purpose |
|---|---|---|
| `docker-compose.prod.yml` | ✅ Created | Production Docker Compose (RDS + S3, no source bind-mount) |
| `nginx.prod.conf` | ✅ Created | Production Nginx (security headers, rate limiting, SSL-ready) |
| `.env.production.example` | ✅ Created | Safe-to-commit template with all production env vars |
| `requirements.txt` | ✅ Updated | Added `django-storages`, `boto3` for S3 |
| `core/settings.py` | ✅ Updated | Production security, S3 storage, proper CORS, logging |
| `entrypoint.sh` | ✅ Updated | Celery uses `prefork` pool (better performance on Linux) |
| `.gitignore` | ✅ Updated | Ensures prod files are tracked, example env is allowed |
