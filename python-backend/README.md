# LB Automotive Python Backend

## Overview
Python-based FastAPI server with SQLite database for LB Automotive shop management system. Includes appointment scheduling, IVR integration, customer management, and staff tracking.

## Features
- 🔐 **JWT Authentication** - Secure token-based authentication
- 📅 **Appointment Management** - Schedule and track customer appointments
- 👥 **Customer Management** - CRM with history tracking
- 🛠️ **Service Catalog** - Manage services and pricing
- 👨‍🔧 **Staff Management** - Track mechanics and advisors
- 📞 **Twilio IVR Integration** - Automated phone system with IVR menu
- ⚙️ **Admin Settings** - Configurable business hours and IVR messages
- 🔒 **Security Hardened** - XSS prevention, SQL injection protection, rate limiting

## Quick Start

### 1. Create Virtual Environment
```bash
cd python-backend
python -m venv venv
```

### 2. Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Environment Variables
Copy `.env.example` to `.env` and update the values:
```bash
copy .env.example .env  # Windows
# OR
cp .env.example .env    # Linux/Mac
```

### 5. Initialize Database
```bash
python database.py
```

This will create the SQLite database, initialize tables, and seed sample data.

### 6. Run the Application
```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Access the API
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Root: http://localhost:8000/

## Docker Deployment

### Build and Run with Docker Compose
```bash
cd ..  # Go back to root directory
docker-compose up -d --build
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
docker-compose logs -f python-backend
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token
- `GET /api/auth/me` - Get current user info

### Services
- `GET /api/services` - List all services
- `GET /api/services/categories` - Get service categories
- `GET /api/services/emergency` - Get emergency services
- `POST /api/services` - Create service (admin only)
- `PUT /api/services/{id}` - Update service (admin only)
- `DELETE /api/services/{id}` - Delete service (admin only)

### Appointments
- `GET /api/appointments` - List appointments
- `POST /api/appointments` - Create appointment
- `GET /api/appointments/{id}` - Get appointment
- `PUT /api/appointments/{id}` - Update appointment
- `DELETE /api/appointments/{id}` - Delete appointment

### Customers (New)
- `GET /api/customers` - List all customers (admin only)
- `GET /api/customers/search?q={query}` - Search customers by name/phone
- `GET /api/customers/{id}` - Get customer by ID
- `GET /api/customers/{id}/history` - Get customer appointment history
- `POST /api/customers` - Create new customer
- `PUT /api/customers/{id}` - Update customer
- `DELETE /api/customers/{id}` - Delete customer

### Staff
- `GET /api/staff` - List staff members (admin only)
- `POST /api/staff` - Add staff member (admin only)
- `PUT /api/staff/{id}` - Update staff member (admin only)
- `DELETE /api/staff/{id}` - Remove staff member (admin only)

### Settings
- `GET /api/settings` - Get all settings (admin only)
- `PUT /api/settings/{key}` - Update setting value (admin only)

### Twilio Webhook
- `POST /api/twilio/webhook?step={step}` - Twilio IVR webhook

## Security Features

### Implemented Protections
- ✅ **Authentication**: JWT token-based auth with FastAPI dependencies
- ✅ **Input Validation**: Pydantic models with custom validators
- ✅ **Input Sanitization**: XSS and SQL injection prevention
- ✅ **Rate Limiting**: 100 req/min, 1000 req/hour per IP
- ✅ **Security Headers**: X-Frame-Options, CSP, HSTS, etc.
- ✅ **CORS**: Whitelisted origins only
- ✅ **Parameterized Queries**: No SQL string concatenation
- ✅ **Error Handling**: No stack traces exposed to clients

### Security Middleware
All responses include security headers:
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security`
- `Content-Security-Policy`
- `Referrer-Policy`

## Database Schema

### Tables
- **users** - User accounts with authentication
- **customers** - Customer contact information (CRM)
- **staff** - Mechanics and service advisors
- **services** - Service catalog with pricing
- **appointments** - Customer appointments
- **settings** - Configurable system settings
- **call_states** - IVR call state management
- **ivr_logs** - IVR interaction logs

### Database Features
- SQLite with WAL mode for better concurrency
- Automatic timestamp tracking
- Unique constraints on phone numbers and emails
- Foreign key relationships

## Default Credentials
- Username: `admin`
- Password: `admin123`

**⚠️ IMPORTANT: Change default credentials in production!**

## Configuration

### Environment Variables
- `DATABASE_URL` - SQLite database path (default: `sqlite:///./lb_automotive.db`)
- `ALLOWED_ORIGINS` - Comma-separated CORS origins
- `SECRET_KEY` - JWT signing secret (set in production!)

### Settings Management
Configurable via Admin UI or API:
- Business hours (opening/closing times)
- IVR greeting messages
- Voice settings (TTS voice, language)
- Daily staff count

## Development

### Project Structure
```
python-backend/
├── main.py              # FastAPI application entry point
├── database.py          # Database initialization and utilities
├── auth.py              # Authentication logic
├── security.py          # Security middleware and validators
├── routes/
│   ├── appointments.py  # Appointment endpoints
│   ├── auth_routes.py   # Auth endpoints
│   ├── customers.py     # Customer management
│   ├── services.py      # Service endpoints
│   ├── settings.py      # Settings endpoints
│   ├── staff.py         # Staff management
│   └── twilio_webhook.py # IVR webhook
├── requirements.txt     # Python dependencies
└── Dockerfile          # Container definition
```

### Running Tests
```bash
# TODO: Add tests
pytest
```

## Traefik Dashboard
When running with Docker Compose, access Traefik dashboard at:
http://localhost:8080

## Troubleshooting

### Database Locked Error
If you encounter "database is locked" errors:
1. Ensure WAL mode is enabled (it should be by default)
2. Check that no other processes are accessing the database
3. Restart the application

### Authentication Issues
- Verify token is included in `Authorization: Bearer <token>` header
- Check token hasn't expired (tokens expire after 30 days by default)
- Ensure user exists and is active

## Contributing
1. Create feature branch
2. Make changes
3. Test thoroughly
4. Submit pull request

## License
Proprietary - LB Automotive

