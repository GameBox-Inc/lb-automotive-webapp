import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { apiClient, User } from '../../lib/supabase';

interface AuthState {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
    loading: boolean;
    error: string | null;
}

const initialState: AuthState = {
    user: null,
    token: localStorage.getItem('auth_token'),
    isAuthenticated: !!localStorage.getItem('auth_token'),
    loading: true,
    error: null,
};

// Async Thunks
export const loginUser = createAsyncThunk(
    'auth/login',
    async ({ username, password, captchaId }: { username: string; password: string; captchaId?: string }, { rejectWithValue }) => {
        try {
            const response = await apiClient.login(username, password, captchaId);
            return response;
        } catch (error: any) {
            return rejectWithValue(error.message || 'Login failed');
        }
    }
);

export const registerUser = createAsyncThunk(
    'auth/register',
    async ({ username, password, email, staffId }: { username: string; password: string; email?: string, staffId?: string }, { rejectWithValue }) => {
        try {
            if (staffId) {
                return await apiClient.registerStaffUser(username, password, staffId);
            }
            return await apiClient.register(username, password, email);
        } catch (error: any) {
            return rejectWithValue(error.message || 'Registration failed');
        }
    }
);

export const checkAuth = createAsyncThunk(
    'auth/checkAuth',
    async (_, { rejectWithValue }) => {
        try {
            if (!apiClient.isAuthenticated()) {
                throw new Error('Not authenticated');
            }
            const user = await apiClient.getCurrentUser();
            return user;
        } catch (error: any) {
            return rejectWithValue(error.message);
        }
    }
);

export const logoutUser = createAsyncThunk(
    'auth/logout',
    async () => {
        apiClient.logout();
    }
);

const authSlice = createSlice({
    name: 'auth',
    initialState,
    reducers: {
        clearError: (state) => {
            state.error = null;
        },
        setUser: (state, action: PayloadAction<User>) => {
            state.user = action.payload;
            state.isAuthenticated = true;
            state.loading = false;
        },
        setToken: (state, action: PayloadAction<string>) => {
            state.token = action.payload;
        }
    },
    extraReducers: (builder) => {
        // Login
        builder.addCase(loginUser.pending, (state) => {
            state.loading = true;
            state.error = null;
        });
        builder.addCase(loginUser.fulfilled, (state, action) => {
            state.loading = false;
            state.isAuthenticated = true;
            state.token = action.payload.access_token;
        });
        builder.addCase(loginUser.rejected, (state, action) => {
            state.loading = false;
            state.error = action.payload as string;
            state.isAuthenticated = false;
            state.token = null;
        });

        // Check Auth
        builder.addCase(checkAuth.pending, (state) => {
            state.loading = true;
        });
        builder.addCase(checkAuth.fulfilled, (state, action) => {
            state.loading = false;
            state.isAuthenticated = true;
            state.user = action.payload;
        });
        builder.addCase(checkAuth.rejected, (state) => {
            state.loading = false;
            state.isAuthenticated = false;
            state.user = null;
            state.token = null;
        });

        // Logout
        builder.addCase(logoutUser.fulfilled, (state) => {
            state.user = null;
            state.token = null;
            state.isAuthenticated = false;
            state.loading = false;
        });
    },
});

export const { clearError, setUser, setToken } = authSlice.actions;
export default authSlice.reducer;
