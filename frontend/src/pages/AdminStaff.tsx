import React, { useId, useEffect, useState } from 'react';
import { Dialog, DialogPanel, DialogTitle, Transition, TransitionChild } from '@headlessui/react';
import { apiClient, Staff, StaffSchedule } from '../lib/supabase';
import { Users, Calendar, UserPlus, Trash2, Clock, Save, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { LoadingSpinner } from '../components/LoadingSpinner';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

const AdminStaff = () => {
    const formId = useId();
    const [activeTab, setActiveTab] = useState<'list' | 'schedule'>('list');
    const [staff, setStaff] = useState<Staff[]>([]);
    const [loading, setLoading] = useState(true);

    // List State
    const [newStaffName, setNewStaffName] = useState('');
    const [newStaffRole, setNewStaffRole] = useState('mechanic');
    const [showAddStaff, setShowAddStaff] = useState(false);

    // Schedule State
    const [selectedStaffId, setSelectedStaffId] = useState<string | null>(null);
    const [schedules, setSchedules] = useState<StaffSchedule[]>([]);
    const [editedSchedule, setEditedSchedule] = useState<any[]>([]);

    useEffect(() => {
        fetchStaff();
    }, []);

    useEffect(() => {
        if (activeTab === 'schedule' && staff.length > 0 && !selectedStaffId) {
            setSelectedStaffId(staff[0].id);
        }
    }, [activeTab, staff]);

    useEffect(() => {
        if (selectedStaffId) {
            fetchSchedule(selectedStaffId);
        }
    }, [selectedStaffId]);

    const fetchStaff = async () => {
        try {
            const data = await apiClient.getStaff();
            setStaff(data);
        } catch (error) {
            console.error('Error fetching staff:', error);
            toast.error('Failed to load staff');
        } finally {
            setLoading(false);
        }
    };

    const fetchSchedule = async (staffId: string) => {
        try {
            const data = await apiClient.getStaffSchedule(staffId);
            setSchedules(data);

            // Initialize edited schedule with defaults if missing
            const defaults = DAYS.map((_, index) => {
                const existing = data.find(s => s.day_of_week === index);
                return existing || {
                    day_of_week: index,
                    start_time: '09:00',
                    end_time: '17:00',
                    is_off: index === 5 || index === 6 // Weekend off by default
                };
            });
            setEditedSchedule(defaults);
        } catch (error) {
            console.error('Error fetching schedule:', error);
            toast.error('Failed to load schedule');
        }
    };

    const handleAddStaff = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await apiClient.createStaff({
                name: newStaffName,
                role: newStaffRole,
                active: true
            });
            toast.success('Staff member added');
            setNewStaffName('');
            setShowAddStaff(false);
            fetchStaff();
        } catch (error) {
            toast.error('Failed to add staff');
        }
    };

    const handleDeleteStaff = async (id: string) => {
        if (!confirm('Are you sure you want to remove this staff member?')) return;
        try {
            await apiClient.deleteStaff(id);
            toast.success('Staff member removed');
            fetchStaff();
        } catch (error) {
            toast.error('Failed to remove staff');
        }
    };

    const handleToggleStatus = async (staffId: string, currentStatus: boolean, name: string) => {
        try {
            await apiClient.updateStaff(staffId, { active: !currentStatus });
            toast.success(`Updated status for ${name}`);
            fetchStaff();
        } catch (error) {
            toast.error('Failed to update status');
        }
    };

    // Credentials Modal Logic
    const [showCredsModal, setShowCredsModal] = useState(false);
    const [credsStaffId, setCredsStaffId] = useState<string | null>(null);
    const [credsData, setCredsData] = useState({ username: '', password: '', is_admin: false });
    const [credsLoading, setCredsLoading] = useState(false);

    const openCredentialsModal = async (staffId: string) => {
        setCredsStaffId(staffId);
        setCredsData({ username: '', password: '', is_admin: false });
        setShowCredsModal(true);

        try {
            const data = await apiClient.getStaffCredentials(staffId);
            if (data.has_account) {
                setCredsData(prev => ({
                    ...prev,
                    username: data.username || '',
                    is_admin: data.is_admin || false
                }));
            }
        } catch (error) {
            console.error(error);
        }
    };

    const handleSaveCredentials = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!credsStaffId) return;

        setCredsLoading(true);
        try {
            await apiClient.updateStaffCredentials(credsStaffId, credsData);
            toast.success('Credentials updated successfully');
            setShowCredsModal(false);
        } catch (error: any) {
            toast.error(error.message || 'Failed to update credentials');
        } finally {
            setCredsLoading(false);
        }
    };

    const handleScheduleChange = (dayIndex: number, field: string, value: any) => {
        setEditedSchedule(prev => prev.map((s, i) =>
            i === dayIndex ? { ...s, [field]: value } : s
        ));
    };

    const saveSchedule = async () => {
        if (!selectedStaffId) return;
        try {
            await apiClient.updateStaffSchedule(selectedStaffId, editedSchedule);
            toast.success('Schedule updated');
            fetchSchedule(selectedStaffId);
        } catch (error) {
            toast.error('Failed to update schedule');
        }
    };

    if (loading) return <LoadingSpinner />;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Staff Management</h1>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Manage employees, credentials, and their weekly working schedules.
                </p>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-200 dark:border-gray-700">
                <nav className="-mb-px flex space-x-8">
                    <button
                        onClick={() => setActiveTab('list')}
                        className={`${activeTab === 'list'
                            ? 'border-indigo-500 text-lb-red-primary'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
                    >
                        <Users className="h-5 w-5 mr-2" />
                        Staff List
                    </button>
                    <button
                        onClick={() => setActiveTab('schedule')}
                        className={`${activeTab === 'schedule'
                            ? 'border-indigo-500 text-lb-red-primary'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
                    >
                        <Calendar className="h-5 w-5 mr-2" />
                        Schedules
                    </button>
                </nav>
            </div>

            {activeTab === 'list' ? (
                // Staff List View
                <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
                    <div className="flex justify-between items-center mb-6">
                        <h2 className="text-lg font-medium text-gray-900 dark:text-white">Staff Members</h2>
                        <button
                            onClick={() => setShowAddStaff(!showAddStaff)}
                            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-lb-red-primary hover:bg-lb-red-light"
                        >
                            <UserPlus className="h-4 w-4 mr-2" />
                            Add Staff
                        </button>
                    </div>

                    {showAddStaff && (
                        <form onSubmit={handleAddStaff} className="mb-6 bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                                <div>
                                    <label htmlFor={`${formId}-name`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">Name</label>
                                    <input
                                        id={`${formId}-name`}
                                        type="text"
                                        value={newStaffName}
                                        onChange={(e) => setNewStaffName(e.target.value)}
                                        required
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    />
                                </div>
                                <div>
                                    <label htmlFor={`${formId}-role`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">Role</label>
                                    <select
                                        id={`${formId}-role`}
                                        value={newStaffRole}
                                        onChange={(e) => setNewStaffRole(e.target.value)}
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    >
                                        <option value="mechanic">Mechanic</option>
                                        <option value="service_advisor">Service Advisor</option>
                                        <option value="manager">Manager</option>
                                    </select>
                                </div>
                            </div>
                            <div className="mt-4 flex justify-end space-x-2">
                                <button
                                    type="button"
                                    onClick={() => setShowAddStaff(false)}
                                    className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                                >
                                    Cancel
                                </button>
                                <button type="submit" className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-lb-red-primary hover:bg-lb-red-light">
                                    Save
                                </button>
                            </div>
                        </form>
                    )}

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {staff.map((member) => (
                            <div key={member.id} className="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg flex justify-between items-start">
                                <div>
                                    <h3 className="text-sm font-medium text-gray-900 dark:text-white">{member.name}</h3>
                                    <p className="text-xs text-gray-500 dark:text-gray-400 capitalize mb-2">{member.role.replace('_', ' ')}</p>

                                    <button
                                        onClick={() => handleToggleStatus(member.id, member.active, member.name)}
                                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium cursor-pointer transition-colors ${member.active ? 'bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-900 dark:text-green-200' : 'bg-gray-200 text-gray-800 hover:bg-gray-300 dark:bg-gray-600 dark:text-gray-200'
                                            }`}
                                    >
                                        {member.active ? 'Active' : 'Inactive'}
                                    </button>
                                </div>
                                <div className="flex space-x-2">
                                    <button
                                        onClick={() => openCredentialsModal(member.id)}
                                        className="text-lb-red-primary hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300 p-1"
                                        title="Manage Credentials"
                                    >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                                        </svg>
                                    </button>
                                    <button
                                        onClick={() => handleDeleteStaff(member.id)}
                                        className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300 p-1"
                                        title="Remove staff"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Credentials Modal */}
                    <Transition show={showCredsModal}>
                        <Dialog open={showCredsModal} onClose={() => setShowCredsModal(false)} className="relative z-50">
                            <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0" enterTo="opacity-100" leave="ease-in duration-150" leaveFrom="opacity-100" leaveTo="opacity-0">
                                <div className="fixed inset-0 bg-black/50" aria-hidden="true" />
                            </TransitionChild>
                            <div className="fixed inset-0 flex items-center justify-center p-4">
                                <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0 scale-95" enterTo="opacity-100 scale-100" leave="ease-in duration-150" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-95">
                                    <DialogPanel className="bg-white dark:bg-gray-800 rounded-lg max-w-md w-full p-6 shadow-xl">
                                        <div className="flex justify-between items-center mb-4">
                                            <DialogTitle className="text-lg font-medium text-gray-900 dark:text-white">Manage Credentials</DialogTitle>
                                            <button type="button" onClick={() => setShowCredsModal(false)} className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-200">
                                                <X className="h-5 w-5" />
                                            </button>
                                        </div>
                                        <form onSubmit={handleSaveCredentials} className="space-y-4">
                                    <div>
                                        <label htmlFor={`${formId}-username`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">Username</label>
                                        <input
                                            id={`${formId}-username`}
                                            type="text"
                                            value={credsData.username}
                                            onChange={e => setCredsData({ ...credsData, username: e.target.value })}
                                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label htmlFor={`${formId}-password`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                            Password
                                            <span className="text-xs text-gray-500 ml-2 font-normal">(Leave blank to keep unchanged)</span>
                                        </label>
                                        <input
                                            id={`${formId}-password`}
                                            type="password"
                                            value={credsData.password}
                                            onChange={e => setCredsData({ ...credsData, password: e.target.value })}
                                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                            minLength={6}
                                        />
                                    </div>
                                    <div className="flex items-center">
                                        <input
                                            type="checkbox"
                                            id={`${formId}-isAdmin`}
                                            checked={credsData.is_admin}
                                            onChange={e => setCredsData({ ...credsData, is_admin: e.target.checked })}
                                            className="h-4 w-4 text-lb-red-primary focus:ring-lb-red-primary border-gray-300 rounded"
                                        />
                                        <label htmlFor={`${formId}-isAdmin`} className="ml-2 block text-sm text-gray-900 dark:text-white">
                                            Grant Admin Access
                                        </label>
                                    </div>
                                    <div className="flex justify-end gap-3 pt-4 border-t border-gray-100 dark:border-gray-700 mt-4">
                                        <button
                                            type="button"
                                            onClick={() => setShowCredsModal(false)}
                                            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            type="submit"
                                            disabled={credsLoading}
                                            className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-lb-red-primary hover:bg-lb-red-light disabled:opacity-50"
                                        >
                                            {credsLoading ? 'Saving...' : 'Save Credentials'}
                                        </button>
                                    </div>
                                </form>
                                    </DialogPanel>
                                </TransitionChild>
                            </div>
                        </Dialog>
                    </Transition>
                </div>
            ) : (
                // Schedule View
                <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
                        <div className="w-full sm:w-64">
                            <label htmlFor={`${formId}-staff-select`} className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Select Staff Member</label>
                            <select
                                id={`${formId}-staff-select`}
                                value={selectedStaffId || ''}
                                onChange={(e) => setSelectedStaffId(e.target.value)}
                                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                            >
                                {staff.map(s => (
                                    <option key={s.id} value={s.id}>{s.name}</option>
                                ))}
                            </select>
                        </div>
                        <button
                            onClick={saveSchedule}
                            disabled={!selectedStaffId}
                            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <Save className="h-4 w-4 mr-2" />
                            Save Schedule
                        </button>
                    </div>

                    {selectedStaffId && (
                        <div className="mt-6 border rounded-lg border-gray-200 dark:border-gray-700 overflow-hidden">
                            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                                <thead className="bg-gray-50 dark:bg-gray-900">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Day</th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Status</th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Start Time</th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">End Time</th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                    {editedSchedule.map((day, index) => (
                                        <tr key={index} className={day.is_off ? 'bg-gray-50 dark:bg-gray-900/50' : ''}>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                                                {DAYS[index]}
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                <button
                                                    onClick={() => handleScheduleChange(index, 'is_off', !day.is_off)}
                                                    className={`px-2 py-1 rounded text-xs font-semibold ${day.is_off
                                                        ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                                                        : 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                                        }`}
                                                >
                                                    {day.is_off ? 'Off Duty' : 'Working'}
                                                </button>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                <input
                                                    type="time"
                                                    value={day.start_time}
                                                    onChange={(e) => handleScheduleChange(index, 'start_time', e.target.value)}
                                                    disabled={day.is_off}
                                                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm disabled:opacity-50 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                                />
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                <input
                                                    type="time"
                                                    value={day.end_time}
                                                    onChange={(e) => handleScheduleChange(index, 'end_time', e.target.value)}
                                                    disabled={day.is_off}
                                                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm disabled:opacity-50 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                                />
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};


export default AdminStaff
