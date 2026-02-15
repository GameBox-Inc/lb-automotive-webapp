import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { apiClient, Service, Staff } from '../../lib/supabase';
import { RootState } from '../index';

interface ShopState {
    services: Service[];
    staff: Staff[];
    loading: boolean;
    error: string | null;
}

const initialState: ShopState = {
    services: [],
    staff: [],
    loading: false,
    error: null,
};

export const fetchServices = createAsyncThunk(
    'shop/fetchServices',
    async (_, { rejectWithValue }) => {
        try {
            return await apiClient.getServices();
        } catch (error: any) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchStaff = createAsyncThunk(
    'shop/fetchStaff',
    async (_, { rejectWithValue }) => {
        try {
            return await apiClient.getStaff();
        } catch (error: any) {
            return rejectWithValue(error.message);
        }
    }
);

const shopSlice = createSlice({
    name: 'shop',
    initialState,
    reducers: {},
    extraReducers: (builder) => {
        builder
            .addCase(fetchServices.fulfilled, (state, action) => {
                state.services = action.payload;
            })
            .addCase(fetchStaff.fulfilled, (state, action) => {
                state.staff = action.payload;
            });
    },
});

export const selectServices = (state: RootState) => state.shop.services;
export const selectStaff = (state: RootState) => state.shop.staff;

export default shopSlice.reducer;
