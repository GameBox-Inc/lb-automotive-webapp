import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface UIState {
    isSidebarOpen: boolean;
    theme: 'light' | 'dark';
    notifications: Array<{ id: string; message: string; type: 'success' | 'error' | 'info' }>;
}

const initialState: UIState = {
    isSidebarOpen: false,
    theme: 'light',
    notifications: [],
};

const uiSlice = createSlice({
    name: 'ui',
    initialState,
    reducers: {
        toggleSidebar: (state) => {
            state.isSidebarOpen = !state.isSidebarOpen;
        },
        setSidebarOpen: (state, action: PayloadAction<boolean>) => {
            state.isSidebarOpen = action.payload;
        },
        setTheme: (state, action: PayloadAction<'light' | 'dark'>) => {
            state.theme = action.payload;
        },
        addNotification: (state, action: PayloadAction<{ message: string; type: 'success' | 'error' | 'info' }>) => {
            state.notifications.push({
                id: Date.now().toString(),
                ...action.payload,
            });
        },
        removeNotification: (state, action: PayloadAction<string>) => {
            state.notifications = state.notifications.filter((n) => n.id !== action.payload);
        },
    },
});

export const { toggleSidebar, setSidebarOpen, setTheme, addNotification, removeNotification } = uiSlice.actions;
export default uiSlice.reducer;
