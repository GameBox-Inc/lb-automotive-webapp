-- Create services table
CREATE TABLE IF NOT EXISTS services (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    duration INTEGER NOT NULL, -- in minutes
    price DECIMAL(10,2) NOT NULL,
    is_emergency BOOLEAN DEFAULT false,
    category VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create appointments table
CREATE TABLE IF NOT EXISTS appointments (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    appointment_time TIMESTAMP WITH TIME ZONE NOT NULL,
    service_type VARCHAR(255) NOT NULL,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    emergency_request BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create call_states table
CREATE TABLE IF NOT EXISTS call_states (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    call_sid VARCHAR(255) NOT NULL UNIQUE,
    current_step VARCHAR(50) NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    metadata JSONB DEFAULT '{}',
    last_response_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create ivr_logs table
CREATE TABLE IF NOT EXISTS ivr_logs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    call_sid VARCHAR(255) NOT NULL,
    step VARCHAR(50) NOT NULL,
    input TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
