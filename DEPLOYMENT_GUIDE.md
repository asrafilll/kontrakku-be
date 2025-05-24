# Django Deployment Guide - CORS Configuration

## ✅ CORS Status: FIXED!

Your Django project now has proper CORS configuration that will work when deployed to a server.

## What Was Fixed

1. **Added `django-cors-headers==4.4.0` to requirements.txt**

   - This was the main issue - the package wasn't in your dependencies
   - Now it will be installed when you deploy to production

2. **Updated CORS settings for production flexibility**

   - Made CORS configurable via environment variables
   - Added support for multiple frontend domains
   - Maintained security by defaulting to restricted origins

3. **Added production-ready environment configuration**
   - Made DEBUG configurable
   - Made ALLOWED_HOSTS configurable
   - Created example environment file

## API Endpoints Available

Your project has these API endpoints that will work with CORS:

1. **Contract Management:**

   - `POST /api/contracts/upload/` - Upload contract files
   - `GET /api/contracts/<contract_id>/status/` - Get contract status
   - `GET /api/contracts/` - List all contracts

2. **Chat System:**
   - `GET /api/chats/<contract_id>/` - Get chat history
   - `WebSocket: ws/chat/<contract_id>/` - Real-time chat
   - `WebSocket: ws/notifications/` - Real-time notifications

## Environment Configuration

### Development (.env file)

Create a `.env` file in your project root:

```env
# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
PG_NAME=kontrakku
PG_USER=kontrakku
PG_PASSWORD=kontrakku
PG_HOST=localhost
PG_PORT=5432

# CORS - Allow all origins for development
CORS_ALLOW_ALL=True
```

### Production Environment Variables

```env
# Django Settings
DEBUG=False
SECRET_KEY=your-super-secret-production-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,your-server-ip

# Database
PG_NAME=your_production_db
PG_USER=your_production_user
PG_PASSWORD=your_production_password
PG_HOST=your_db_host
PG_PORT=5432

# CORS - Restrict to your frontend domains
CORS_ALLOW_ALL=False
CORS_ADDITIONAL_ORIGINS=https://yourdomain.com,https://www.yourdomain.com,https://app.yourdomain.com
```

## Deployment Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Set the production environment variables on your server.

### 3. Database Migration

```bash
python manage.py migrate
```

### 4. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 5. Test the Server

```bash
python manage.py runserver 0.0.0.0:8000
```

## Frontend Integration

Your frontend can now make requests to your API from these origins:

### Development:

- `http://localhost:3000` (React)
- `http://localhost:5173` (Vite)
- `http://localhost:8080` (Vue)
- Any origin (when `CORS_ALLOW_ALL=True`)

### Production:

- Add your production domains to `CORS_ADDITIONAL_ORIGINS`

## Example Frontend Request

```javascript
// Example API call from your frontend
fetch("https://yourapi.com/api/contracts/", {
  method: "GET",
  headers: {
    "Content-Type": "application/json",
    // Add any auth headers here
  },
  credentials: "include", // This works because CORS_ALLOW_CREDENTIALS=True
})
  .then((response) => response.json())
  .then((data) => console.log(data));
```

## Security Notes

1. **Never use `CORS_ALLOW_ALL=True` in production**
2. **Always specify exact frontend domains in production**
3. **Use HTTPS in production**
4. **Keep your SECRET_KEY secret**
5. **Set DEBUG=False in production**

## Common Deployment Platforms

### Railway

```bash
railway login
railway init
railway up
```

### Heroku

```bash
heroku create your-app-name
git push heroku main
```

### DigitalOcean App Platform

- Connect your GitHub repository
- Set environment variables in the dashboard
- Deploy

### VPS/Server

- Use gunicorn or uWSGI
- Set up nginx as reverse proxy
- Configure SSL certificate

## Testing CORS

You can test CORS with curl:

```bash
# Test CORS preflight
curl -H "Origin: https://yourdomain.com" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     https://yourapi.com/api/contracts/

# Test actual request
curl -H "Origin: https://yourdomain.com" \
     -X GET \
     https://yourapi.com/api/contracts/
```

## Troubleshooting

1. **CORS errors still occurring?**

   - Check that `django-cors-headers` is installed
   - Verify your frontend domain is in CORS_ALLOWED_ORIGINS
   - Ensure CorsMiddleware is first in MIDDLEWARE

2. **404 errors?**

   - Check your URL patterns
   - Verify ALLOWED_HOSTS includes your domain

3. **500 errors?**
   - Check server logs
   - Ensure all environment variables are set
   - Verify database connection

Your API is now ready for production deployment with proper CORS support! 🚀
