
import { useState, useEffect } from 'react';
import { apiClient, Appointment } from '../lib/supabase';
import { Car, Wrench, LayoutGrid, LayoutList, Phone, AlertCircle } from 'lucide-react';
import { formatCurrency, formatNumber } from '../utils/format';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { LoadingSpinner } from '../components/LoadingSpinner';

const StaffDashboard = () => {
    const [loading, setLoading] = useState(true);
    const [appointments, setAppointments] = useState<Appointment[]>([]);
    const [viewMode, setViewMode] = useState<'card' | 'table'>('table');
    const navigate = useNavigate();

    const [staff, setStaff] = useState<Array<{ id: string, name: string }>>([]);
    const [showAssignModal, setShowAssignModal] = useState(false);
    const [selectedAppointment, setSelectedAppointment] = useState<Appointment | null>(null);
    const [selectedStaffId, setSelectedStaffId] = useState('');

    useEffect(() => {
        fetchMyRepairs();
        fetchStaff();
    }, []);

    const fetchStaff = async () => {
        try {
            const staffList = await apiClient.getStaff();
            setStaff(staffList.filter(s => s.active));
        } catch (error) {
            console.error('Error fetching staff:', error);
        }
    };

    async function fetchMyRepairs() {
        try {
            const data = await apiClient.getAppointments();
            const user = await apiClient.getCurrentUser();

            if (user.staff_id) {
                const myApps = data.filter(a =>
                    a.assigned_staff_id === user.staff_id ||
                    (!a.assigned_staff_id && ['confirmed', 'pending'].includes(a.status))
                );
                setAppointments(myApps);
            } else if (user.is_admin) {
                setAppointments(data.filter(a => ['confirmed', 'in_progress', 'completed'].includes(a.status)));
            } else {
                setAppointments([]);
            }
        } catch (error) {
            console.error('Error fetching repairs:', error);
            toast.error('Failed to load repair queue');
        } finally {
            setLoading(false);
        }
    }

    const handleAssign = async () => {
        if (!selectedAppointment || !selectedStaffId) return;

        try {
            await apiClient.updateAppointment(selectedAppointment.id, {
                assigned_staff_id: selectedStaffId,
                status: 'in_progress'
            });
            toast.success('Repair assigned successfully');
            setShowAssignModal(false);
            setSelectedAppointment(null);
            setSelectedStaffId('');
            fetchMyRepairs();
        } catch (error) {
            console.error('Error assigning repair:', error);
            toast.error('Failed to assign repair');
        }
    };

    const openAssignModal = (apt: Appointment) => {
        setSelectedAppointment(apt);
        setSelectedStaffId(apt.assigned_staff_id || '');
        setShowAssignModal(true);
    };

    const handleOpenCase = async (appointment: Appointment) => {
        try {
            // First, try to find an existing case for this appointment
            const cases = await apiClient.getCases();
            let existingCase = cases.find((c: any) => c.appointment_id === appointment.id);

            if (existingCase) {
                // Case already exists, navigate to it
                navigate(`/cases/${existingCase.id}`);
                return;
            }

            // No existing case, create a new one
            try {
                const newCase = await apiClient.createCase({
                    appointment_id: appointment.id,
                    customer_name: appointment.customer_name,
                    phone_number: appointment.phone_number,
                    service_type: appointment.service_type,
                    status: 'diagnosing'
                });

                if (newCase && newCase.id) {
                    navigate(`/cases/${newCase.id}`);
                } else {
                    toast.error('Failed to create case');
                }
            } catch (createError) {
                console.error("Error creating case:", createError);
                toast.error("Failed to create case");
            }
        } catch (error) {
            console.error("Open case error", error);
            toast.error("Failed to open case");
        }
    };

    const formatElapsed = (startedAt: string | undefined): string => {
        if (!startedAt) return '--';
        const start = new Date(startedAt);
        const now = new Date();
        const diffMs = now.getTime() - start.getTime();
        const diffMin = Math.round(diffMs / 60000);

        if (diffMin < 60) return `${diffMin}m`;
        const h = Math.floor(diffMin / 60);
        const m = diffMin % 60;
        return `${h}h ${m}m`;
    };

    if (loading) return <LoadingSpinner />;

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white font-heading">
                        Repair Queue
                    </h1>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        Manage your assigned repairs and active cases.
                    </p>
                </div>

                <div className="flex bg-gray-100 dark:bg-gray-700 p-1 rounded-lg">
                    <button
                        onClick={() => setViewMode('table')}
                        className={`p-2 rounded-md transition-colors ${viewMode === 'table'
                            ? 'bg-white dark:bg-gray-600 shadow-sm text-indigo-600 dark:text-indigo-400'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                            }`}
                        title="Table View"
                    >
                        <LayoutList className="h-5 w-5" />
                    </button>
                    <button
                        onClick={() => setViewMode('card')}
                        className={`p-2 rounded-md transition-colors ${viewMode === 'card'
                            ? 'bg-white dark:bg-gray-600 shadow-sm text-indigo-600 dark:text-indigo-400'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                            }`}
                        title="Card View"
                    >
                        <LayoutGrid className="h-5 w-5" />
                    </button>
                </div>
            </div>

            {appointments.length === 0 ? (
                <div className="text-center py-12 bg-gray-50 dark:bg-gray-800 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-700">
                    <Wrench className="mx-auto h-12 w-12 text-gray-400" />
                    <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No repairs assigned</h3>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        You don't have any active repairs assigned to you.
                    </p>
                </div>
            ) : (
                <>
                    {viewMode === 'table' ? (
                        <div className="bg-white dark:bg-gray-800 shadow overflow-x-auto sm:rounded-lg">
                            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                                <thead className="bg-gray-50 dark:bg-gray-700">
                                    <tr>
                                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                            Customer / Vehicle
                                        </th>
                                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                            Service
                                        </th>
                                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                            Status
                                        </th>
                                        <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                            Time
                                        </th>
                                        <th scope="col" className="relative px-6 py-3">
                                            <span className="sr-only">Actions</span>
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                    {appointments.map((apt) => (
                                        <tr key={apt.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                <div className="flex items-center">
                                                    <div className="flex-shrink-0 h-10 w-10 bg-indigo-100 dark:bg-indigo-900 rounded-full flex items-center justify-center">
                                                        <Car className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                                                    </div>
                                                    <div className="ml-4">
                                                        <div className="text-sm font-medium text-gray-900 dark:text-white">
                                                            {apt.customer_name}
                                                        </div>
                                                        <div className="text-sm text-gray-500 dark:text-gray-400">
                                                            {apt.phone_number}
                                                        </div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                <div className="text-sm text-gray-900 dark:text-white">{apt.service_type}</div>
                                                {apt.emergency_request && (
                                                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                                                        Emergency
                                                    </span>
                                                )}
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                                            ${apt.status === 'in_progress' ? 'bg-blue-100 text-blue-800' :
                                                        apt.status === 'completed' ? 'bg-green-100 text-green-800' :
                                                            'bg-yellow-100 text-yellow-800'}`}>
                                                    {apt.status.replace('_', ' ')}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                                {apt.status === 'in_progress' ? (
                                                    <div className="flex flex-col">
                                                        <span className="font-bold text-blue-600 dark:text-blue-400">
                                                            {formatElapsed(apt.started_at)} elapsed
                                                        </span>
                                                        <span className="text-xs opacity-75">
                                                            Started {new Date(apt.started_at!).toLocaleTimeString()}
                                                        </span>
                                                    </div>
                                                ) : (
                                                    new Date(apt.appointment_time).toLocaleString()
                                                )}
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                                <button
                                                    onClick={() => handleOpenCase(apt)}
                                                    className="text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300 font-bold"
                                                >
                                                    Open Case
                                                </button>
                                                <button
                                                    onClick={() => openAssignModal(apt)}
                                                    className="ml-4 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-300 font-medium"
                                                >
                                                    {apt.assigned_staff_id ? 'Reassign' : 'Claim'}
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                            {appointments.map((apt) => (
                                <div key={apt.id} className="bg-white dark:bg-gray-800 overflow-hidden shadow rounded-lg border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow">
                                    <div className="px-4 py-5 sm:p-6">
                                        <div className="flex items-center justify-between mb-4">
                                            <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                                        ${apt.status === 'in_progress' ? 'bg-blue-100 text-blue-800' :
                                                    apt.status === 'completed' ? 'bg-green-100 text-green-800' :
                                                        'bg-yellow-100 text-yellow-800'}`}>
                                                {apt.status.replace('_', ' ')}
                                            </span>
                                            {apt.emergency_request && (
                                                <AlertCircle className="h-5 w-5 text-red-500" />
                                            )}
                                        </div>

                                        <h3 className="text-lg font-medium text-gray-900 dark:text-white truncate">
                                            {apt.customer_name}
                                        </h3>
                                        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400 flex items-center">
                                            <Phone className="h-3 w-3 mr-1" /> {apt.phone_number}
                                        </p>

                                        <div className="mt-4 border-t border-gray-200 dark:border-gray-700 pt-4">
                                            <div className="flex justify-between text-sm">
                                                <span className="text-gray-500 dark:text-gray-400">Service:</span>
                                                <span className="font-medium text-gray-900 dark:text-white">{apt.service_type}</span>
                                            </div>
                                            <div className="flex justify-between text-sm mt-2">
                                                <span className="text-gray-500 dark:text-gray-400">Time:</span>
                                                <span className="font-medium text-gray-900 dark:text-white">
                                                    {apt.status === 'in_progress' ? (
                                                        <span className="text-blue-600 dark:text-blue-400 font-bold">
                                                            {formatElapsed(apt.started_at)} (Running)
                                                        </span>
                                                    ) : (
                                                        new Date(apt.appointment_time).toLocaleDateString()
                                                    )}
                                                </span>
                                            </div>
                                        </div>

                                        <div className="mt-6">
                                            <button
                                                onClick={() => handleOpenCase(apt)}
                                                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                                            >
                                                Open Case
                                            </button>
                                            <button
                                                onClick={() => openAssignModal(apt)}
                                                className="mt-2 w-full flex justify-center py-2 px-4 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                                            >
                                                {apt.assigned_staff_id ? 'Reassign' : 'Claim Repair'}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </>
            )}

            {showAssignModal && selectedAppointment && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md">
                        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                            Assign Repair
                        </h3>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Select Staff Member
                                </label>
                                <select
                                    value={selectedStaffId}
                                    onChange={(e) => setSelectedStaffId(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                >
                                    <option value="">-- Select Staff --</option>
                                    {staff.map((s) => (
                                        <option key={s.id} value={s.id}>
                                            {s.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex justify-end gap-3">
                                <button
                                    onClick={() => setShowAssignModal(false)}
                                    className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleAssign}
                                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
                                >
                                    Assign
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};


export default StaffDashboard
