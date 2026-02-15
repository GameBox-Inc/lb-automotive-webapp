import { configureStore } from '@reduxjs/toolkit';
import authReducer from './slices/authSlice';
import uiReducer from './slices/uiSlice';
import appointmentsReducer from './slices/appointmentsSlice';
import shopReducer from './slices/shopSlice';
import deploymentReducer from './slices/deploymentSlice';

export const store = configureStore({
    reducer: {
        auth: authReducer,
        ui: uiReducer,
        appointments: appointmentsReducer,
        shop: shopReducer,
        deployment: deploymentReducer,
    },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
