import { useEffect, useState } from 'react';
import { apiClient, Setting } from '../lib/supabase';
import { Phone, Clock, MessageSquare, Save, Settings, BarChart2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { LoadingSpinner } from '../components/LoadingSpinner';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts';

const AdminIVR = () => {
    const [settings, setSettings] = useState<Setting[]>([]);
    const [loading, setLoading] = useState(true);
    const [editingKey, setEditingKey] = useState<string | null>(null);
    const [editValue, setEditValue] = useState('');
    const [activeTab, setActiveTab] = useState<'config' | 'analytics'>('config');
    const [analyticsSummary, setAnalyticsSummary] = useState<any>(null);
    const [analyticsNodes, setAnalyticsNodes] = useState<any[]>([]);

    useEffect(() => {
        fetchSettings();
        fetchAnalytics();
    }, []);

    async function fetchAnalytics() {
        try {
            const [summary, nodes] = await Promise.all([
                apiClient.getIvrAnalyticsSummary(),
                apiClient.getIvrAnalyticsNodes()
            ]);
            setAnalyticsSummary(summary);
            setAnalyticsNodes(nodes);
        } catch (error) {
            console.error('Error fetching analytics:', error);
        }
    }

    async function fetchSettings() {
        try {
            const data = await apiClient.getSettings();
            setSettings(data);
        } catch (error) {
            console.error('Error fetching settings:', error);
            // toast.error('Failed to load settings'); 
        } finally {
            setLoading(false);
        }
    }

    const handleEdit = (setting: Setting) => {
        setEditingKey(setting.key);
        setEditValue(setting.value);
    };

    const handleSave = async (key: string) => {
        try {
            await apiClient.updateSetting(key, editValue);
            toast.success('Setting updated successfully');
            setEditingKey(null);
            fetchSettings();
        } catch (error) {
            console.error('Error updating setting:', error);
            toast.error('Failed to update setting');
        }
    };

    const handleCancel = () => {
        setEditingKey(null);
        setEditValue('');
    };

    if (loading) return <LoadingSpinner />;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">IVR Management</h1>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Manage system settings and view call analytics.
                </p>
                <div className="mt-4 border-b border-gray-200 dark:border-gray-700">
                    <nav className="-mb-px flex space-x-8">
                        <button
                            onClick={() => setActiveTab('config')}
                            className={`${activeTab === 'config'
                                ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
                        >
                            <Settings className="h-5 w-5 mr-2" />
                            Configuration
                        </button>
                        <button
                            onClick={() => setActiveTab('analytics')}
                            className={`${activeTab === 'analytics'
                                ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
                        >
                            <BarChart2 className="h-5 w-5 mr-2" />
                            Analytics
                        </button>
                    </nav>
                </div>
            </div>

            <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
                {activeTab === 'config' ? (
                    <div className="px-4 py-5 sm:p-6 space-y-8">

                        {/* General Settings Section */}
                        <div>
                            <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-white flex items-center">
                                <Settings className="h-5 w-5 mr-2 text-indigo-500" />
                                General Settings
                            </h3>
                            <div className="mt-4 grid grid-cols-1 gap-y-6 sm:grid-cols-2 sm:gap-x-8">
                                {Array.isArray(settings) && settings.filter(s => !s.key.includes('time') && !s.key.startsWith('ivr_')).map(setting => (
                                    <div key={setting.key} className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                                    {setting.description || setting.key.replace('_', ' ')}
                                                </label>
                                                {editingKey === setting.key ? (
                                                    <input
                                                        type="text"
                                                        value={editValue}
                                                        onChange={(e) => setEditValue(e.target.value)}
                                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                                    />
                                                ) : (
                                                    <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                                        {setting.value}
                                                    </p>
                                                )}
                                            </div>
                                            <div>
                                                {editingKey === setting.key ? (
                                                    <div className="flex space-x-2">
                                                        <button
                                                            onClick={() => handleSave(setting.key)}
                                                            className="text-green-600 hover:text-green-700 p-1"
                                                        >
                                                            <Save className="h-5 w-5" />
                                                        </button>
                                                        <button
                                                            onClick={handleCancel}
                                                            className="text-gray-400 hover:text-gray-500 p-1"
                                                        >
                                                            <span className="sr-only">Cancel</span>
                                                            x
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={() => handleEdit(setting)}
                                                        className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
                                                    >
                                                        Edit
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="border-t border-gray-200 dark:border-gray-700" />

                        {/* Business Hours Section */}
                        <div>
                            <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-white flex items-center">
                                <Clock className="h-5 w-5 mr-2 text-indigo-500" />
                                Business Hours
                            </h3>
                            <div className="mt-4 grid grid-cols-1 gap-y-6 sm:grid-cols-2 sm:gap-x-8">
                                {Array.isArray(settings) && settings.filter(s => s.key.includes('time')).map(setting => (
                                    <div key={setting.key} className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                                    {setting.description || setting.key}
                                                </label>
                                                {editingKey === setting.key ? (
                                                    <input
                                                        type="time"
                                                        value={editValue}
                                                        onChange={(e) => setEditValue(e.target.value)}
                                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                                    />
                                                ) : (
                                                    <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
                                                        {setting.value}
                                                    </p>
                                                )}
                                            </div>
                                            <div>
                                                {editingKey === setting.key ? (
                                                    <div className="flex space-x-2">
                                                        <button
                                                            onClick={() => handleSave(setting.key)}
                                                            className="text-green-600 hover:text-green-700 p-1"
                                                        >
                                                            <Save className="h-5 w-5" />
                                                        </button>
                                                        <button
                                                            onClick={handleCancel}
                                                            className="text-gray-400 hover:text-gray-500 p-1"
                                                        >
                                                            <span className="sr-only">Cancel</span>
                                                            x
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={() => handleEdit(setting)}
                                                        className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
                                                    >
                                                        Edit
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="border-t border-gray-200 dark:border-gray-700" />

                        {/* Messages Section */}
                        <div>
                            <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-white flex items-center">
                                <MessageSquare className="h-5 w-5 mr-2 text-indigo-500" />
                                IVR Messages
                            </h3>
                            <div className="mt-4 space-y-4">
                                {Array.isArray(settings) && settings.filter(s => s.key.startsWith('ivr_') && !['ivr_voice', 'ivr_language'].includes(s.key)).map(setting => (
                                    <div key={setting.key} className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
                                        <div className="flex justify-between items-start">
                                            <div className="flex-1 mr-4">
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                                    {setting.description || setting.key}
                                                </label>
                                                {editingKey === setting.key ? (
                                                    <textarea
                                                        rows={3}
                                                        value={editValue}
                                                        onChange={(e) => setEditValue(e.target.value)}
                                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                                    />
                                                ) : (
                                                    <p className="mt-1 text-sm text-gray-900 dark:text-white whitespace-pre-wrap">
                                                        {setting.value}
                                                    </p>
                                                )}
                                            </div>
                                            <div>
                                                {editingKey === setting.key ? (
                                                    <div className="flex space-x-2">
                                                        <button
                                                            onClick={() => handleSave(setting.key)}
                                                            className="text-green-600 hover:text-green-700 p-1"
                                                        >
                                                            <Save className="h-5 w-5" />
                                                        </button>
                                                        <button
                                                            onClick={handleCancel}
                                                            className="text-gray-400 hover:text-gray-500 p-1"
                                                        >
                                                            <span className="sr-only">Cancel</span>
                                                            x
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={() => handleEdit(setting)}
                                                        className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
                                                    >
                                                        Edit
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="border-t border-gray-200 dark:border-gray-700" />

                        {/* Voice Settings */}
                        <div>
                            <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-white flex items-center">
                                <Phone className="h-5 w-5 mr-2 text-indigo-500" />
                                Voice Configuration
                            </h3>
                            <div className="mt-4 grid grid-cols-1 gap-y-6 sm:grid-cols-2 sm:gap-x-8">
                                {Array.isArray(settings) && settings.filter(s => ['ivr_voice', 'ivr_language'].includes(s.key)).map(setting => (
                                    <div key={setting.key} className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                                    {setting.description || setting.key}
                                                </label>
                                                {editingKey === setting.key ? (
                                                    <input
                                                        type="text"
                                                        value={editValue}
                                                        onChange={(e) => setEditValue(e.target.value)}
                                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                                    />
                                                ) : (
                                                    <p className="mt-1 text-sm font-mono text-gray-900 dark:text-white">
                                                        {setting.value}
                                                    </p>
                                                )}
                                            </div>
                                            <div>
                                                {editingKey === setting.key ? (
                                                    <div className="flex space-x-2">
                                                        <button
                                                            onClick={() => handleSave(setting.key)}
                                                            className="text-green-600 hover:text-green-700 p-1"
                                                        >
                                                            <Save className="h-5 w-5" />
                                                        </button>
                                                        <button
                                                            onClick={handleCancel}
                                                            className="text-gray-400 hover:text-gray-500 p-1"
                                                        >
                                                            <span className="sr-only">Cancel</span>
                                                            x
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={() => handleEdit(setting)}
                                                        className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
                                                    >
                                                        Edit
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="border-t border-gray-200 dark:border-gray-700" />

                    </div>
                ) : (
                    <div className="px-4 py-5 sm:p-6 space-y-8">
                        {/* Analytics Section */}
                        <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
                            <div className="bg-gray-50 dark:bg-gray-700/50 overflow-hidden shadow rounded-lg">
                                <div className="px-4 py-5 sm:p-6">
                                    <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">Total Calls (30d)</dt>
                                    <dd className="mt-1 text-3xl font-semibold text-gray-900 dark:text-white">{analyticsSummary?.total_calls || 0}</dd>
                                </div>
                            </div>
                            <div className="bg-gray-50 dark:bg-gray-700/50 overflow-hidden shadow rounded-lg">
                                <div className="px-4 py-5 sm:p-6">
                                    <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">Total Interactions</dt>
                                    <dd className="mt-1 text-3xl font-semibold text-gray-900 dark:text-white">{analyticsSummary?.total_steps || 0}</dd>
                                </div>
                            </div>
                            <div className="bg-gray-50 dark:bg-gray-700/50 overflow-hidden shadow rounded-lg">
                                <div className="px-4 py-5 sm:p-6">
                                    <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">Avg Steps per Call</dt>
                                    <dd className="mt-1 text-3xl font-semibold text-gray-900 dark:text-white">{analyticsSummary?.avg_steps_per_call || 0}</dd>
                                </div>
                            </div>
                        </div>

                        <div className="mt-8">
                            <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-white mb-4">IVR Node Visits</h3>
                            <div className="h-96 w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={analyticsNodes}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis dataKey="node_name" />
                                        <YAxis />
                                        <Tooltip />
                                        <Legend />
                                        <Bar dataKey="visits" fill="#4F46E5" name="Visits" />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};


export default AdminIVR
