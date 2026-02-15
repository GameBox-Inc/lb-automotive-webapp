import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { apiClient, Appointment } from '../../lib/supabase';
import { RootState } from '../index';

interface AppointmentsState {
    appointments: Appointment[];
    loading: boolean;
    error: string | null;
    timeframe: '24h' | '7d' | '30d';
    lastUpdated: number | null;
}

const initialState: AppointmentsState = {
    appointments: [],
    loading: false,
    error: null,
    timeframe: '24h',
    lastUpdated: null,
};

export const fetchAppointments = createAsyncThunk(
    'appointments/fetchAppointments',
    async (_, { rejectWithValue }) => {
        try {
            const data = await apiClient.getAppointments();
            return data;
        } catch (error: any) {
            return rejectWithValue(error.message || 'Failed to fetch appointments');
        }
    }
);

export const createAppointment = createAsyncThunk(
    'appointments/createAppointment',
    async (appointment: Omit<Appointment, 'id' | 'created_at' | 'updated_at' | 'status'>, { rejectWithValue }) => {
        try {
            const data = await apiClient.createAppointment(appointment);
            return data;
        } catch (error: any) {
            return rejectWithValue(error.message || 'Failed to create appointment');
        }
    }
);

export const updateAppointmentStatus = createAsyncThunk(
    'appointments/updateStatus',
    async ({ id, status }: { id: string; status: string }, { rejectWithValue }) => {
        try {
            const data = await apiClient.updateAppointmentStatus(id, status);
            return data;
        } catch (error: any) {
            return rejectWithValue(error.message || 'Failed to update status');
        }
    }
);

const appointmentsSlice = createSlice({
    name: 'appointments',
    initialState,
    reducers: {
        setTimeframe: (state, action: PayloadAction<'24h' | '7d' | '30d'>) => {
            state.timeframe = action.payload;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchAppointments.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchAppointments.fulfilled, (state, action) => {
                state.loading = false;
                state.appointments = action.payload;
                state.lastUpdated = Date.now();
            })
            .addCase(fetchAppointments.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload as string;
            })
            .addCase(createAppointment.fulfilled, (state, action) => {
                state.appointments.push(action.payload);
            })
            .addCase(updateAppointmentStatus.fulfilled, (state, action) => {
                const index = state.appointments.findIndex(a => a.id === action.payload.id);
                if (index !== -1) {
                    state.appointments[index] = action.payload;
                }
            });
    },
});

export const { setTimeframe } = appointmentsSlice.actions;

// Selectors
export const selectAppointments = (state: RootState) => state.appointments.appointments;
export const selectFilteredAppointments = (state: RootState) => {
    const { appointments, timeframe } = state.appointments;
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

    return appointments.filter(apt => new Date(apt.appointment_time) >= start);
};

export default appointmentsSlice.reducer;
