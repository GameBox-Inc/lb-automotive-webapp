# LB Automotive Dashboard - API Reference

## Base URL
```
http://localhost:8000/api
```

## Authentication

All endpoints (except login/register) require JWT authentication.

### Headers
```
Authorization: Bearer <your_jwt_token>
Content-Type: application/json
```

### Get Token
```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

## Customer Management

### List Customers
```http
GET /customers?skip=0&limit=100
```

### Search Customers
```http
GET /customers/search?q=john
```

### Get Customer
```http
GET /customers/{customer_id}
```

### Get Customer History
```http
GET /customers/{customer_id}/history
```

### Create Customer
```http
POST /customers
Content-Type: application/json

{
  "name": "John Doe",
  "phone": "5551234567",
  "email": "john@example.com"
}
```

### Update Customer
```http
PUT /customers/{customer_id}
Content-Type: application/json

{
  "name": "John Doe Updated",
  "phone": "5551234567",
  "email": "john.doe@example.com"
}
```

### Delete Customer
```http
DELETE /customers/{customer_id}
```

## Staff Management

### List Staff
```http
GET /staff
```

### Create Staff
```http
POST /staff
Content-Type: application/json

{
  "name": "Mike Mechanic",
  "role": "mechanic",
  "active": true
}
```

### Update Staff
```http
PUT /staff/{staff_id}
Content-Type: application/json

{
  "name": "Mike Senior Mechanic",
  "role": "mechanic",
  "active": true
}
```

### Delete Staff
```http
DELETE /staff/{staff_id}
```

## Settings

### Get All Settings
```http
GET /settings
```

### Update Setting
```http
PUT /settings/{key}
Content-Type: application/json

{
  "value": "09:00"
}
```

**Common Setting Keys:**
- `opening_time`
- `closing_time`
- `ivr_greeting`
- `ivr_closed_message`
- `ivr_voice`
- `ivr_language`
- `staff_count`

## Response Codes

- `200 OK` - Success
- `201 Created` - Resource created
- `400 Bad Request` - Validation error
- `401 Unauthorized` - Missing/invalid token
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

## Rate Limits

- **Short Window**: 100 requests per minute
- **Long Window**: 1000 requests per hour

Rate limit headers included in responses:
- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`
