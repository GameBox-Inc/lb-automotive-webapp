import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { apiClient } from '../../lib/supabase';
import { DeploymentStatus } from '../../types';

interface DeploymentState {
    status: DeploymentStatus['status'];
    currentBuildId: number | null;
    isDeploying: boolean;
    lastChecked: number | null;
    error: string | null;
}

const initialState: DeploymentState = {
    status: 'idle',
    currentBuildId: null,
    isDeploying: false,
    lastChecked: null,
    error: null,
};

export const checkDeploymentStatus = createAsyncThunk(
    'deployment/checkStatus',
    async () => {
        const status = await apiClient.getDeploymentStatus();
        return status;
    }
);

export const triggerDeployment = createAsyncThunk(
    'deployment/trigger',
    async () => {
        await apiClient.triggerDeployment();
        // After triggering, we immediately check status to get the new build info (might need a delay in real app)
        const status = await apiClient.getDeploymentStatus();
        return status;
    }
);

const deploymentSlice = createSlice({
    name: 'deployment',
    initialState,
    reducers: {
        resetDeploymentState: (state) => {
            state.status = 'idle';
            state.error = null;
        }
    },
    extraReducers: (builder) => {
        builder
            .addCase(checkDeploymentStatus.fulfilled, (state, action: PayloadAction<DeploymentStatus>) => {
                state.status = action.payload.status;
                state.currentBuildId = action.payload.build_number;
                state.lastChecked = Date.now();
                // If status is building, we consider it deploying
                state.isDeploying = action.payload.status === 'building';
                state.error = action.payload.detail || null;
            })
            .addCase(checkDeploymentStatus.rejected, (state, action) => {
                state.error = action.error.message || 'Failed to check status';
            })
            .addCase(triggerDeployment.pending, (state) => {
                state.isDeploying = true;
                state.error = null;
            })
            .addCase(triggerDeployment.fulfilled, (state, action: PayloadAction<DeploymentStatus>) => {
                state.isDeploying = true;
                state.status = 'building';
                if (action.payload.build_number) {
                    state.currentBuildId = action.payload.build_number;
                }
            })
            .addCase(triggerDeployment.rejected, (state, action) => {
                state.isDeploying = false;
                state.error = action.error.message || 'Failed to trigger deployment';
            });
    },
});

export const { resetDeploymentState } = deploymentSlice.actions;
export default deploymentSlice.reducer;
