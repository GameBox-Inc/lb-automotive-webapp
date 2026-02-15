/**
 * API Client for LB Automotive Backend
 * Replaces Supabase with secure Python API integration
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

// Debug logging - only in development
const isDevelopment = import.meta.env.DEV;
if (isDevelopment) {
  console.log('API Client Initialized:', { API_BASE_URL });
}

// Token management
const TOKEN_KEY = 'auth_token';
const USER_KEY = 'current_user';

import {
  User,
  Appointment,
  Service,
  Setting,
  Staff,
  StaffSchedule,
  StaffScheduleUpdate,
  Customer,
  BusinessHours,
  BusinessHoursUpdate,
  DeploymentStatus,
  BuildLog
} from '../types';

export type {
  User,
  Appointment,
  Service,
  Setting,
  Staff,
  StaffSchedule,
  StaffScheduleUpdate,
  Customer,
  BusinessHours,
  BusinessHoursUpdate,
  DeploymentStatus,
  BuildLog
};

class APIClient {
  private token: string | null = null;
  private lastRateLimitTime: number = 0;

  constructor() {
    this.token = localStorage.getItem(TOKEN_KEY);
  }

  /**
   * Get authorization headers with JWT token
   */
  private getHeaders(includeAuth = true): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (includeAuth && this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    return headers;
  }

  /**
   * Make API request with error handling
   */
  public async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;

    // Debug logging - only in development
    if (isDevelopment) {
      console.log(`[API] ${options.method || 'GET'} ${url}`, {
        hasToken: !!this.token,
        endpoint
      });
    }

    try {
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), 10000); // 10s timeout

      const headers: any = {
        ...this.getHeaders(),
        ...options.headers,
      };

      // If body is FormData, remove Content-Type to let browser set it with boundary
      if (options.body instanceof FormData) {
        delete headers['Content-Type'];
      }

      const response = await fetch(url, {
        ...options,
        signal: options.signal || controller.signal,
        headers,
      });
      clearTimeout(id);

      if (isDevelopment) {
        console.log(`[API] Response: ${response.status} ${response.statusText}`);
      }

      // Handle rate limiting with exponential backoff
      if (response.status === 429) {
        const resetTime = response.headers.get('X-RateLimit-Reset');
        const now = Date.now();

        // Prevent multiple rapid requests after rate limit
        if (now - this.lastRateLimitTime < 5000) {
          // If we were rate limited less than 5 seconds ago, wait before retrying
          await new Promise(resolve => setTimeout(resolve, 5000));
        }

        this.lastRateLimitTime = now;
        throw new Error(`Rate limit exceeded. Try again after ${new Date(Number(resetTime) * 1000).toLocaleTimeString()}`);
      }

      // Handle authentication errors
      if (response.status === 401) {
        if (isDevelopment) {
          console.error('[API] Authentication failed - logging out');
        }
        this.logout();
        throw new Error('Authentication required. Please log in again.');
      }

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        // Always log errors, but use appropriate level
        if (isDevelopment) {
          console.error('[API] Error response:', error);
        }
        throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      return response.json();
    } catch (error) {
      if (error instanceof Error) {
        // Log errors in development, silent in production
        if (isDevelopment) {
          console.error('API Error:', error.message);
        }
        throw error;
      }
      throw new Error('Network error occurred');
    }
  }

  /**
   * Authentication Methods
   */
  async getCaptcha(): Promise<{ captcha_id: string }> {
    return this.request<{ captcha_id: string }>('/auth/captcha');
  }

  async verifyCaptcha(captchaId: string): Promise<{ verified: boolean }> {
    const formData = new FormData();
    formData.append('captcha_id', captchaId);

    return this.request<{ verified: boolean }>('/auth/verify-captcha', {
      method: 'POST',
      body: formData
    });
  }

  async login(username: string, password: string, captchaId?: string): Promise<{ access_token: string; token_type: string }> {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    if (captchaId) {
      formData.append('captcha_id', captchaId);
    }

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        body: formData,
      });

      // Handle rate limiting
      if (response.status === 429) {
        const resetTime = response.headers.get('X-RateLimit-Reset');
        throw new Error(`Rate limit exceeded. Try again after ${new Date(Number(resetTime) * 1000).toLocaleTimeString()}`);
      }

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Login failed' }));
        throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.token = data.access_token;
      localStorage.setItem(TOKEN_KEY, data.access_token);

      // Fetch user profile
      const user = await this.getCurrentUser();
      localStorage.setItem(USER_KEY, JSON.stringify(user));

      return data;
    } catch (error) {
      if (error instanceof Error) {
        if (isDevelopment) {
          console.error('Login Error:', error.message);
        }
        throw error;
      }
      throw new Error('Login failed');
    }
  }

  async register(username: string, password: string, email?: string): Promise<User> {
    const user = await this.request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, email, is_admin: false }),
    });

    return user;
  }

  async registerStaffUser(username: string, password: string, staffId: string): Promise<User> {
    const user = await this.request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, is_admin: false, staff_id: staffId }),
    });

    return user;
  }

  async getCurrentUser(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  logout(): void {
    this.token = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.dispatchEvent(new Event('auth:unauthorized'));
  }

  isAuthenticated(): boolean {
    return !!this.token;
  }

  getStoredUser(): User | null {
    const userStr = localStorage.getItem(USER_KEY);
    return userStr ? JSON.parse(userStr) : null;
  }

  /**
   * Appointments API
   */
  async getAppointments(status?: string): Promise<Appointment[]> {
    const params = status ? `?status_filter=${encodeURIComponent(status)}` : '';
    return this.request<Appointment[]>(`/appointments${params}`);
  }

  async getAppointment(id: string): Promise<Appointment> {
    return this.request<Appointment>(`/appointments/${id}`);
  }

  async createAppointment(appointment: Omit<Appointment, 'id' | 'created_at' | 'updated_at' | 'status'>): Promise<Appointment> {
    return this.request<Appointment>('/appointments', {
      method: 'POST',
      body: JSON.stringify(appointment),
    });
  }

  async updateAppointment(id: string, updates: Partial<Appointment>): Promise<Appointment> {
    return this.request<Appointment>(`/appointments/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async updateAppointmentStatus(id: string, status: string): Promise<Appointment> {
    return this.updateAppointment(id, { status });
  }

  async rescheduleAppointment(id: string, appointment_time: string): Promise<Appointment> {
    return this.updateAppointment(id, { appointment_time, status: 'rescheduled' });
  }

  async deleteAppointment(id: string): Promise<void> {
    await this.request(`/appointments/${id}`, {
      method: 'DELETE',
    });
  }

  // Staff Credentials
  async getStaffCredentials(staffId: string) {
    return this.request<{ has_account: boolean; username?: string; is_admin?: boolean }>(
      `/staff/${staffId}/credentials`
    );
  }

  async updateStaffCredentials(staffId: string, credentials: any) {
    return this.request(`/staff/${staffId}/credentials`, {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  }

  /**
   * Reports API
   */
  async getReportSummary(timeframe: '7d' | '30d' | '90d' | 'all' = '30d') {
    return this.request(`/reports/summary?timeframe=${timeframe}`);
  }

  async getReportHistory(limit = 50) {
    return this.request(`/reports/history?limit=${limit}`);
  }

  /**
   * Services API
   */
  async getServices(category?: string, isEmergency?: boolean): Promise<Service[]> {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (isEmergency !== undefined) params.append('is_emergency', String(isEmergency));

    const query = params.toString() ? `?${params}` : '';
    return this.request<Service[]>(`/services${query}`);
  }

  async getService(id: string): Promise<Service> {
    return this.request<Service>(`/services/${id}`);
  }

  async getServiceCategories(): Promise<string[]> {
    return this.request<string[]>('/services/categories');
  }

  async getEmergencyServices(): Promise<Service[]> {
    return this.request<Service[]>('/services/emergency');
  }

  async createService(service: Omit<Service, 'id' | 'created_at' | 'updated_at'>): Promise<Service> {
    return this.request<Service>('/services', {
      method: 'POST',
      body: JSON.stringify(service),
    });
  }

  async updateService(id: string, updates: Partial<Service>): Promise<Service> {
    return this.request<Service>(`/services/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteService(id: string): Promise<void> {
    return this.request<void>(`/services/${id}`, {
      method: 'DELETE',
    });
  }

  /**
   * Settings API
   */
  async getSettings(): Promise<Setting[]> {
    return this.request<Setting[]>('/settings');
  }

  async updateSetting(key: string, value: string): Promise<Setting> {
    return this.request<Setting>(`/settings/${key}`, {
      method: 'PUT',
      body: JSON.stringify({ value }),
    });
  }

  /**
   * Business Hours API
   */
  async getBusinessHours(): Promise<BusinessHours[]> {
    return this.request<BusinessHours[]>('/business-hours');
  }

  async updateBusinessHours(dayOfWeek: number, hours: BusinessHoursUpdate): Promise<BusinessHours> {
    return this.request<BusinessHours>(`/business-hours/${dayOfWeek}`, {
      method: 'PUT',
      body: JSON.stringify(hours),
    });
  }

  /**
   * Staff API
   */
  async getStaff(): Promise<Staff[]> {
    return this.request<Staff[]>('/staff');
  }

  async createStaff(staff: Omit<Staff, 'id' | 'created_at'>): Promise<Staff> {
    return this.request<Staff>('/staff', {
      method: 'POST',
      body: JSON.stringify(staff),
    });
  }

  async updateStaff(id: string, updates: Partial<Staff>): Promise<Staff> {
    return this.request<Staff>(`/staff/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteStaff(id: string): Promise<void> {
    return this.request<void>(`/staff/${id}`, {
      method: 'DELETE',
    });
  }

  async getStaffSchedule(staffId: string): Promise<StaffSchedule[]> {
    return this.request<StaffSchedule[]>(`/staff/${staffId}/schedule`);
  }

  async updateStaffSchedule(staffId: string, schedules: StaffScheduleUpdate[]): Promise<void> {
    return this.request<void>(`/staff/${staffId}/schedule`, {
      method: 'PUT',
      body: JSON.stringify(schedules),
    });
  }

  async getAvailableSlots(date: string, serviceId: string): Promise<string[]> {
    return this.request<string[]>(`/appointments/available-slots?date=${date}&service_id=${serviceId}`);
  }

  /**
   * IVR Analytics API
   */
  async getIvrAnalyticsSummary(timeframe: '24h' | '7d' | '30d' | '90d' = '30d') {
    return this.request<{ total_calls: number, total_steps: number, avg_steps_per_call: number }>(
      `/ivr/analytics/summary?timeframe=${timeframe}`
    );
  }

  async getIvrAnalyticsNodes(timeframe: '24h' | '7d' | '30d' | '90d' = '30d') {
    return this.request<{ node_name: string, visits: number }[]>(
      `/ivr/analytics/nodes?timeframe=${timeframe}`
    );
  }

  /**
   * Customer API
   */
  async getCustomers(skip: number = 0, limit: number = 100): Promise<Customer[]> {
    return this.request<Customer[]>(`/customers?skip=${skip}&limit=${limit}`);
  }

  async getCustomer(id: string): Promise<Customer> {
    return this.request<Customer>(`/customers/${id}`);
  }

  async searchCustomers(query: string): Promise<Customer[]> {
    return this.request<Customer[]>(`/customers/search?q=${encodeURIComponent(query)}`);
  }

  async getCustomerHistory(id: string): Promise<Appointment[]> {
    return this.request<Appointment[]>(`/customers/${id}/history`);
  }

  async searchCustomerByPhone(phone: string): Promise<Customer | null> {
    const customers = await this.searchCustomers(phone);
    return customers[0] ?? null;
  }

  async createCustomer(customer: Omit<Customer, 'id' | 'created_at'>): Promise<Customer> {
    return this.request<Customer>('/customers', {
      method: 'POST',
      body: JSON.stringify(customer),
    });
  }

  async updateCustomer(id: string, updates: Partial<Omit<Customer, 'id' | 'created_at'>>): Promise<Customer> {
    return this.request<Customer>(`/customers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteCustomer(id: string): Promise<void> {
    return this.request<void>(`/customers/${id}`, {
      method: 'DELETE',
    });
  }

  /**
   * Cases API
   */
  async getCases(): Promise<any[]> {
    return this.request<any[]>('/cases');
  }

  async getCase(id: string): Promise<any> {
    return this.request<any>(`/cases/${id}`);
  }

  async createCase(caseData: {
    appointment_id: string;
    customer_name: string;
    phone_number: string;
    service_type: string;
    status?: string;
  }): Promise<any> {
    return this.request<any>('/cases', {
      method: 'POST',
      body: JSON.stringify(caseData),
    });
  }

  async updateCase(id: string, updates: any): Promise<any> {
    return this.request<any>(`/cases/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  /**
   * Deployment API
   */
  async triggerDeployment(): Promise<{ message: string; queue_item_url: string }> {
    return this.request<{ message: string; queue_item_url: string }>('/deployment/trigger', {
      method: 'POST'
    });
  }

  async getDeploymentStatus(): Promise<DeploymentStatus> {
    return this.request<DeploymentStatus>('/deployment/status');
  }

  async getBuildLogs(buildNumber: number, start: number = 0): Promise<BuildLog> {
    return this.request<BuildLog>(`/deployment/logs/${buildNumber}?start=${start}`);
  }

  /**
   * Utility Methods
   */
  async getAppointmentsByTimeframe(timeframe: '24h' | '7d' | '30d'): Promise<Appointment[]> {
    const appointments = await this.getAppointments();
    const now = new Date();
    const start = new Date();

    switch (timeframe) {
      case '24h':
        start.setHours(start.getHours() - 24);
        break;
      case '7d':
        start.setDate(start.getDate() - 7);
        break;
      case '30d':
        start.setDate(start.getDate() - 30);
        break;
    }

    return appointments.filter(apt => {
      const aptTime = new Date(apt.appointment_time);
      return aptTime >= start && aptTime <= now;
    });
  }

  async logError(error: any, context: string, metadata?: any): Promise<void> {
    if (isDevelopment) {
      console.error(`[${context}]`, error, metadata);
    }
    // Could send to backend logging endpoint if implemented
  }
}

// Export singleton instance
export const apiClient = new APIClient();

// For backwards compatibility with existing code
export const supabase = {
  from: (_table: string) => {
    throw new Error('Supabase is deprecated. Use apiClient instead.');
  },
  auth: {
    signInWithPassword: async ({ email, password }: { email: string; password: string }) => {
      const response = await apiClient.login(email, password);
      return { data: { session: { access_token: response.access_token } }, error: null };
    },
    signOut: async () => {
      apiClient.logout();
      return { error: null };
    },
    getSession: async () => {
      const user = apiClient.getStoredUser();
      return { data: { session: user ? { user } : null }, error: null };
    },
  },
};

// Export helper functions for compatibility
export const updateAppointmentStatus = (id: string, status: string) =>
  apiClient.updateAppointmentStatus(id, status);

export const rescheduleAppointment = (id: string, appointment_time: string) =>
  apiClient.rescheduleAppointment(id, appointment_time);

export const logError = (error: any, context: string, metadata?: any) =>
  apiClient.logError(error, context, metadata);

export const getAppointmentsByTimeframe = (timeframe: '24h' | '7d' | '30d') =>
  apiClient.getAppointmentsByTimeframe(timeframe);

// No real-time support with REST API
export const subscribeToAppointments = (_callback: (payload: any) => void) => {
  if (isDevelopment) {
    console.warn('Real-time subscriptions not supported with REST API');
  }
  return { unsubscribe: () => { } };
};