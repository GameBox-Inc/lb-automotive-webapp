import { useEffect, useReducer, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '../store/hooks';
import { triggerDeployment, checkDeploymentStatus } from '../store/slices/deploymentSlice';
import { apiClient } from '../lib/supabase';
import { Terminal, Play, RefreshCw, AlertCircle, CheckCircle, XCircle, Clock } from 'lucide-react';
import toast from 'react-hot-toast';

// Complex Log State Management with useReducer
interface LogState {
    logs: string[];
    isLoadingLogs: boolean;
    nextStart: number;
    hasMore: boolean;
    error: string | null;
}

type LogAction =
    | { type: 'INIT_LOGS' }
    | { type: 'ADD_LOGS'; payload: { logs: string; nextStart: number; hasMore: boolean } }
    | { type: 'LOG_ERROR'; payload: string }
    | { type: 'RESET' };

const initialLogState: LogState = {
    logs: [],
    isLoadingLogs: false,
    nextStart: 0,
    hasMore: true,
    error: null,
};

function logReducer(state: LogState, action: LogAction): LogState {
    switch (action.type) {
        case 'INIT_LOGS':
            return { ...state, isLoadingLogs: true, error: null };
        case 'ADD_LOGS':
            // Jenkins logs might come in chunks, we split by newline for display
            const newLines = action.payload.logs.split('\n').filter(line => line.length > 0);
            return {
                ...state,
                logs: [...state.logs, ...newLines],
                isLoadingLogs: false,
                nextStart: action.payload.nextStart,
                hasMore: action.payload.hasMore,
            };
        case 'LOG_ERROR':
            return { ...state, isLoadingLogs: false, error: action.payload };
        case 'RESET':
            return initialLogState;
        default:
            return state;
    }
}

const AdminDeploy = () => {
    const dispatch = useAppDispatch();
    const { status, currentBuildId, isDeploying, lastChecked, error: globalError } = useAppSelector((state) => state.deployment);

    // Local state for logs using reducer
    const [logState, dispatchLog] = useReducer(logReducer, initialLogState);

    // Ref for auto-scrolling terminal
    const terminalEndRef = useRef<HTMLDivElement>(null);

    // Ref for polling interval to clear it on unmount
    const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

    // Scroll to bottom effect
    useEffect(() => {
        terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logState.logs]);

    // Initial Check
    useEffect(() => {
        dispatch(checkDeploymentStatus());
    }, [dispatch]);

    // Handle Deploy Trigger
    const handleDeploy = async () => {
        try {
            if (isDeploying) return;
            toast.success('Triggering deployment...');
            dispatchLog({ type: 'RESET' });
            await dispatch(triggerDeployment()).unwrap();
        } catch (err) {
            toast.error('Failed to trigger deployment');
        }
    };

    // Poll for logs and status if deploying
    useEffect(() => {
        if (status === 'building' && currentBuildId) {
            // Clear any existing interval
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

            // Start polling logs
            pollIntervalRef.current = setInterval(async () => {
                try {
                    // check status update
                    dispatch(checkDeploymentStatus());

                    // fetch logs
                    const logData = await apiClient.getBuildLogs(currentBuildId, logState.nextStart);

                    dispatchLog({
                        type: 'ADD_LOGS',
                        payload: {
                            logs: logData.logs,
                            nextStart: parseInt(logData.next_start) || logState.nextStart + logData.logs.length,
                            hasMore: logData.more_data
                        }
                    });

                    if (!logData.more_data && status !== 'building') {
                        // Stop polling if done
                        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
                    }

                } catch (err) {
                    console.error("Polling error", err);
                    dispatchLog({ type: 'LOG_ERROR', payload: 'Failed to fetch logs' });
                }
            }, 2000);
        }

        return () => {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        };
    }, [status, currentBuildId, dispatch, logState.nextStart]);


    const getStatusColor = (s: string) => {
        switch (s) {
            case 'SUCCESS': return 'text-green-500';
            case 'FAILURE': return 'text-red-500';
            case 'building': return 'text-blue-500 animate-pulse';
            default: return 'text-gray-500';
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                        <Terminal className="h-8 w-8 text-[#B91C1C]" />
                        Pipeline Deployment
                    </h1>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        Manage and monitor Jenkins CI/CD pipelines.
                    </p>
                </div>
                <button
                    onClick={handleDeploy}
                    disabled={isDeploying || status === 'building'}
                    className={`
            flex items-center gap-2 px-6 py-3 rounded-lg font-bold text-white shadow-lg transition-all
            ${isDeploying ? 'bg-gray-500 cursor-not-allowed' : 'bg-gradient-to-r from-[#B91C1C] to-[#DC2626] hover:scale-105 active:scale-95'}
          `}
                >
                    {isDeploying ? <RefreshCw className="h-5 w-5 animate-spin" /> : <Play className="h-5 w-5" />}
                    {isDeploying ? 'Deploying...' : 'Deploy to Production'}
                </button>
            </div>

            {/* Status Panel */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Current Status</h3>
                    <div className={`mt-2 text-2xl font-bold flex items-center gap-2 ${getStatusColor(status || 'unknown')}`}>
                        {status === 'SUCCESS' && <CheckCircle className="h-6 w-6" />}
                        {status === 'FAILURE' && <XCircle className="h-6 w-6" />}
                        {status === 'building' && <RefreshCw className="h-6 w-6 animate-spin" />}
                        {status || 'IDLE'}
                    </div>
                </div>
                <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Last Check</h3>
                    <div className="mt-2 text-xl font-mono text-gray-700 dark:text-gray-200 flex items-center gap-2">
                        <Clock className="h-5 w-5" />
                        {lastChecked ? new Date(lastChecked).toLocaleTimeString() : 'Never'}
                    </div>
                </div>
                <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Build ID</h3>
                    <div className="mt-2 text-2xl font-mono text-gray-900 dark:text-white">
                        #{currentBuildId || '---'}
                    </div>
                </div>
            </div>

            {/* Global Error Alert */}
            {globalError && (
                <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-md">
                    <div className="flex">
                        <div className="flex-shrink-0">
                            <AlertCircle className="h-5 w-5 text-red-500" />
                        </div>
                        <div className="ml-3">
                            <p className="text-sm text-red-700">{globalError}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Terminal Window */}
            <div className="bg-[#1e1e1e] rounded-xl shadow-2xl border border-gray-700 overflow-hidden font-mono text-sm">
                <div className="bg-[#2d2d2d] px-4 py-2 border-b border-gray-700 flex items-center justify-between">
                    <div className="flex gap-2">
                        <div className="w-3 h-3 rounded-full bg-red-500"></div>
                        <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                        <div className="w-3 h-3 rounded-full bg-green-500"></div>
                    </div>
                    <span className="text-gray-400 text-xs">jenkins-runner-01</span>
                </div>
                <div className="p-4 h-[500px] overflow-y-auto text-gray-300 space-y-1 scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-transparent">
                    {logState.logs.length === 0 && !isDeploying && (
                        <div className="text-gray-500 italic text-center mt-20">Ready to deploy...</div>
                    )}
                    {logState.logs.map((log, i) => (
                        <div key={i} className="break-words font-mono hover:bg-white/5 px-1 rounded">
                            <span className="text-gray-500 select-none mr-3">
                                {String(i + 1).padStart(3, '0')}
                            </span>
                            {log}
                        </div>
                    ))}
                    {isDeploying && (
                        <div className="flex items-center gap-2 text-[#FDB80E] mt-2">
                            <span className="animate-pulse">_</span>
                        </div>
                    )}
                    <div ref={terminalEndRef} />
                </div>
            </div>
        </div>
    );
};

export default AdminDeploy;
