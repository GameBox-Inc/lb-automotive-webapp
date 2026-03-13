export interface User {
    id: string;
    username: string;
    email?: string;
    is_admin: boolean;
    staff_id?: string;
}

export interface Appointment {
    id: string;
    customer_name: string;
    phone_number: string;
    appointment_time: string;
    service_type: string;
    notes?: string;
    status: string;
    emergency_request: boolean;
    assigned_staff_id?: string;
    vehicle_make?: string;
    vehicle_model?: string;
    vehicle_year?: number;
    created_at?: string;
    updated_at?: string;
    started_at?: string;
    // Foreign keys for creation
    customer_id?: string;
    service_id?: string;
}

export interface Service {
    id: string;
    name: string;
    description?: string;
    duration: number;
    price: number;
    is_emergency: boolean;
    category: string;
}

export interface Setting {
    key: string;
    value: string;
    description?: string;
    updated_at?: string;
    updated_by?: string;
}

export interface Staff {
    id: string;
    name: string;
    role: string;
    active: boolean;
    created_at?: string;
}

export interface StaffSchedule {
    id: string;
    staff_id: string;
    day_of_week: number;
    start_time: string;
    end_time: string;
    is_off: boolean;
}

export interface StaffScheduleUpdate {
    day_of_week: number;
    start_time: string;
    end_time: string;
    is_off: boolean;
}

export interface Customer {
    id: string;
    name: string;
    phone: string;
    email?: string;
    created_at?: string;
    vehicle_make?: string;
    vehicle_model?: string;
    vehicle_color?: string;
    vehicle_year?: number;
}

export interface BusinessHours {
    day_of_week: number; // 0=Monday, 6=Sunday
    day_name: string;
    opening_time: string | null; // HH:MM format
    closing_time: string | null; // HH:MM format
    is_closed: boolean;
    updated_at?: string;
    updated_by?: string;
}

export interface BusinessHoursUpdate {
    opening_time?: string | null; // HH:MM format, null if closed
    closing_time?: string | null; // HH:MM format, null if closed
    is_closed: boolean;
}

export interface DeploymentStatus {
    status: 'building' | 'SUCCESS' | 'FAILURE' | 'ABORTED' | 'unknown' | 'idle' | 'error';
    build_number: number | null;
    timestamp?: number;
    duration?: number;
    estimated_duration?: number;
    detail?: string;
}

export interface BuildLog {
    logs: string;
    more_data: boolean;
    next_start: string;
}
