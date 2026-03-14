import { useEffect, useState } from 'react';
import { apiClient, Setting, BusinessHours, BusinessHoursUpdate } from '../lib/supabase';
import { Phone, Clock, MessageSquare, Save, Settings, BarChart2, X } from 'lucide-react';
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
    const [businessHours, setBusinessHours] = useState<BusinessHours[]>([]);
    const [editingDay, setEditingDay] = useState<number | null>(null);
    const [editHours, setEditHours] = useState<{ is_closed: boolean; opening_time: string | null; closing_time: string | null }>({ is_closed: false, opening_time: null, closing_time: null });

    useEffect(() => {
        fetchSettings();
        fetchAnalytics();
        fetchBusinessHours();
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

    async function fetchBusinessHours() {
        try {
            const data = await apiClient.getBusinessHours();
            setBusinessHours(data);
        } catch (error) {
            console.error('Error fetching business hours:', error);
            toast.error('Failed to load business hours');
        }
    }

    const handleEditHours = (hours: BusinessHours) => {
        setEditingDay(hours.day_of_week);
        setEditHours({
            is_closed: hours.is_closed,
            opening_time: hours.opening_time || '',
            closing_time: hours.closing_time || ''
        });
    };

    const handleSaveHours = async (dayOfWeek: number) => {
        try {
            const update: BusinessHoursUpdate = {
                is_closed: editHours.is_closed,
                opening_time: editHours.is_closed ? null : (editHours.opening_time || null),
                closing_time: editHours.is_closed ? null : (editHours.closing_time || null)
            };
            await apiClient.updateBusinessHours(dayOfWeek, update);
            toast.success('Business hours updated successfully');
            setEditingDay(null);
            fetchBusinessHours();
        } catch (error) {
            console.error('Error updating business hours:', error);
            toast.error('Failed to update business hours');
        }
    };

    const handleCancelHours = () => {
        setEditingDay(null);
        setEditHours({ is_closed: false, opening_time: null, closing_time: null });
    };

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
                                Business Hours (24/7 Booking Enabled)
                            </h3>
                            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                                Configure hours for each day of the week. Customers can book appointments 24/7, even when closed.
                            </p>
                            <div className="mt-4 overflow-x-auto">
                                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                                    <thead className="bg-gray-50 dark:bg-gray-700">
                                        <tr>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Day</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Status</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Opening Time</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Closing Time</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                        {businessHours.map((hours) => (
                                            <tr key={hours.day_of_week}>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                                                    {hours.day_name}
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    {editingDay === hours.day_of_week ? (
                                                        <label className="flex items-center">
                                                            <input
                                                                type="checkbox"
                                                                checked={!editHours.is_closed}
                                                                onChange={(e) => setEditHours({ ...editHours, is_closed: !e.target.checked })}
                                                                className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                                                            />
                                                            <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                                                                {editHours.is_closed ? 'Closed' : 'Open'}
                                                            </span>
                                                        </label>
                                                    ) : (
                                                        <span className={`text-sm ${hours.is_closed ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                                                            {hours.is_closed ? 'Closed' : 'Open'}
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    {editingDay === hours.day_of_week ? (
                                                        <input
                                                            type="time"
                                                            value={editHours.opening_time || ''}
                                                            onChange={(e) => setEditHours({ ...editHours, opening_time: e.target.value })}
                                                            disabled={editHours.is_closed}
                                                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white disabled:opacity-50"
                                                        />
                                                    ) : (
                                                        <span className="text-sm text-gray-900 dark:text-white">
                                                            {hours.opening_time || '—'}
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap">
                                                    {editingDay === hours.day_of_week ? (
                                                        <input
                                                            type="time"
                                                            value={editHours.closing_time || ''}
                                                            onChange={(e) => setEditHours({ ...editHours, closing_time: e.target.value })}
                                                            disabled={editHours.is_closed}
                                                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white disabled:opacity-50"
                                                        />
                                                    ) : (
                                                        <span className="text-sm text-gray-900 dark:text-white">
                                                            {hours.closing_time || '—'}
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                                    {editingDay === hours.day_of_week ? (
                                                        <div className="flex space-x-2">
                                                            <button
                                                                onClick={() => handleSaveHours(hours.day_of_week)}
                                                                className="text-green-600 hover:text-green-700"
                                                                title="Save"
                                                            >
                                                                <Save className="h-5 w-5" />
                                                            </button>
                                                            <button
                                                                onClick={handleCancelHours}
                                                                className="text-gray-400 hover:text-gray-500"
                                                                title="Cancel"
                                                            >
                                                                <X className="h-5 w-5" />
                                                            </button>
                                                        </div>
                                                    ) : (
                                                        <button
                                                            onClick={() => handleEditHours(hours)}
                                                            className="text-indigo-600 hover:text-indigo-700"
                                                        >
                                                            Edit
                                                        </button>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
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
