import { useState, useEffect, useMemo } from 'react';
import { apiClient, Appointment } from '../lib/supabase';
import { Car, Wrench, LayoutGrid, LayoutList, Phone, AlertCircle, User, Filter, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { LoadingSpinner } from '../components/LoadingSpinner';

// ── Status helpers ────────────────────────────────────────────────────────────
const STATUS_CONFIG: Record<string, { label: string; classes: string; progress: number }> = {
    pending: { label: 'Pending', classes: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300', progress: 10 },
    confirmed: { label: 'Confirmed', classes: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300', progress: 25 },
    diagnosing: { label: 'Diagnosing', classes: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300', progress: 40 },
    in_progress: { label: 'In Progress', classes: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300', progress: 65 },
    waiting_parts: { label: 'Waiting Parts', classes: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300', progress: 80 },
    completed: { label: 'Completed', classes: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300', progress: 100 },
    cancelled: { label: 'Cancelled', classes: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300', progress: 0 },
};

function StatusBadge({ status }: { status: string }) {
    const cfg = STATUS_CONFIG[status] ?? { label: status, classes: 'bg-gray-100 text-gray-800', progress: 0 };
    return (
        <span className={`px-2.5 py-0.5 inline-flex text-xs font-semibold rounded-full ${cfg.classes}`}>
            {cfg.label}
        </span>
    );
}

function ProgressBar({ status }: { status: string }) {
    const cfg = STATUS_CONFIG[status] ?? { progress: 0, label: status, classes: '' };
    const pct = cfg.progress;
    const color =
        pct === 100 ? 'bg-green-500' :
            pct >= 65 ? 'bg-blue-500' :
                pct >= 25 ? 'bg-indigo-500' :
                    'bg-yellow-500';
    return (
        <div className="w-full mt-1.5">
            <div className="flex justify-between text-xs text-gray-400 mb-0.5">
                <span>{cfg.label}</span>
                <span>{pct}%</span>
            </div>
            <div className="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all duration-500 ${color}`}
                    style={{ width: `${pct}%` }}
                />
            </div>
        </div>
    );
}

// ── Elapsed time formatter ─────────────────────────────────────────────────────
function formatElapsed(startedAt: string | null | undefined): string {
    if (!startedAt) return '—';
    const start = new Date(startedAt);
    if (isNaN(start.getTime())) return '—';
    const now = new Date();
    const diffMs = Math.max(0, now.getTime() - start.getTime()); // guard against negative
    const totalMin = Math.floor(diffMs / 60000);
    if (totalMin < 60) return `${totalMin}m elapsed`;
    const totalHours = Math.floor(totalMin / 60);
    const mins = totalMin % 60;
    if (totalHours < 24) return `${totalHours}h ${mins}m elapsed`;
    const days = Math.floor(totalHours / 24);
    const hours = totalHours % 24;
    return `${days}d ${hours}h elapsed`;
}

// ── Assignee display ───────────────────────────────────────────────────────────
function AssigneeChip({ staffId, staffList }: { staffId?: string | null; staffList: Array<{ id: string; name: string }> }) {
    if (!staffId) {
        return <span className="text-xs text-gray-400 italic">Unassigned</span>;
    }
    const member = staffList.find(s => s.id === staffId);
    const name = member?.name ?? 'Unknown';
    const initials = name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
    return (
        <div className="flex items-center gap-1.5">
            <div className="h-6 w-6 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                {initials}
            </div>
            <span className="text-sm text-gray-700 dark:text-gray-300 truncate">{name}</span>
        </div>
    );
}

// ── Main Component ─────────────────────────────────────────────────────────────
const StaffDashboard = () => {
    const [loading, setLoading] = useState(true);
    const [appointments, setAppointments] = useState<Appointment[]>([]);
    const [viewMode, setViewMode] = useState<'card' | 'table'>('table');
    const navigate = useNavigate();

    const [staff, setStaff] = useState<Array<{ id: string; name: string }>>([]);
    const [showAssignModal, setShowAssignModal] = useState(false);
    const [selectedAppointment, setSelectedAppointment] = useState<Appointment | null>(null);
    const [selectedStaffId, setSelectedStaffId] = useState('');

    // Filter state
    const [filterStatus, setFilterStatus] = useState('all');
    const [filterAssignee, setFilterAssignee] = useState('all');
    const [showFilters, setShowFilters] = useState(false);

    useEffect(() => {
        fetchMyRepairs();
        fetchStaffList();
    }, []);

    const fetchStaffList = async () => {
        try {
            const staffList = await apiClient.getStaff();
            setStaff(staffList.filter((s: any) => s.active));
        } catch (error) {
            console.error('Error fetching staff:', error);
        }
    };

    async function fetchMyRepairs() {
        try {
            const data = await apiClient.getAppointments();
            const user = await apiClient.getCurrentUser();

            if (user.staff_id) {
                const myApps = data.filter((a: Appointment) =>
                    a.assigned_staff_id === user.staff_id ||
                    (!a.assigned_staff_id && ['confirmed', 'pending'].includes(a.status))
                );
                setAppointments(myApps);
            } else if (user.is_admin) {
                setAppointments(data.filter((a: Appointment) =>
                    ['pending', 'confirmed', 'diagnosing', 'in_progress', 'waiting_parts', 'completed'].includes(a.status)
                ));
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

    const filteredAppointments = useMemo(() => {
        return appointments.filter(apt => {
            const matchStatus = filterStatus === 'all' || apt.status === filterStatus;
            const matchAssignee = filterAssignee === 'all'
                ? true
                : filterAssignee === 'unassigned'
                    ? !apt.assigned_staff_id
                    : apt.assigned_staff_id === filterAssignee;
            return matchStatus && matchAssignee;
        });
    }, [appointments, filterStatus, filterAssignee]);

    const activeFilters = (filterStatus !== 'all' ? 1 : 0) + (filterAssignee !== 'all' ? 1 : 0);

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
            const cases = await apiClient.getCases();
            const existingCase = cases.find((c: any) => c.appointment_id === appointment.id);
            if (existingCase) { navigate(`/cases/${existingCase.id}`); return; }
            const newCase = await apiClient.createCase({
                appointment_id: appointment.id,
                customer_name: appointment.customer_name,
                phone_number: appointment.phone_number,
                service_type: appointment.service_type,
                status: 'diagnosing'
            });
            if (newCase?.id) { navigate(`/cases/${newCase.id}`); }
            else { toast.error('Failed to create case'); }
        } catch (error) {
            console.error('Open case error', error);
            toast.error('Failed to open case');
        }
    };

    if (loading) return <LoadingSpinner />;

    return (
        <div className="space-y-6">

            {/* ── Header ── */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white font-heading">
                        My Repairs
                    </h1>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        Manage your assigned repairs and active cases.
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    {/* Filter toggle */}
                    <button
                        onClick={() => setShowFilters(f => !f)}
                        className={`relative flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${showFilters
                            ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-300'
                            : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                            }`}
                    >
                        <Filter className="h-4 w-4" />
                        Filter
                        {activeFilters > 0 && (
                            <span className="absolute -top-1 -right-1 h-4 w-4 flex items-center justify-center rounded-full bg-indigo-600 text-white text-xs">
                                {activeFilters}
                            </span>
                        )}
                    </button>

                    {/* View toggle */}
                    <div className="flex bg-gray-100 dark:bg-gray-700 p-1 rounded-lg">
                        <button onClick={() => setViewMode('table')} className={`p-2 rounded-md transition-colors ${viewMode === 'table' ? 'bg-white dark:bg-gray-600 shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'}`} title="Table View">
                            <LayoutList className="h-5 w-5" />
                        </button>
                        <button onClick={() => setViewMode('card')} className={`p-2 rounded-md transition-colors ${viewMode === 'card' ? 'bg-white dark:bg-gray-600 shadow-sm text-indigo-600' : 'text-gray-500 hover:text-gray-700'}`} title="Card View">
                            <LayoutGrid className="h-5 w-5" />
                        </button>
                    </div>
                </div>
            </div>

            {/* ── Filter Bar ── */}
            {showFilters && (
                <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 flex flex-wrap items-center gap-3">
                    {/* Status filter */}
                    <select
                        value={filterStatus}
                        onChange={e => setFilterStatus(e.target.value)}
                        className="px-3 py-2 bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded-lg text-sm text-gray-700 dark:text-gray-200 focus:ring-2 focus:ring-indigo-500/50"
                    >
                        <option value="all">All Statuses</option>
                        {Object.entries(STATUS_CONFIG).map(([key, { label }]) => (
                            <option key={key} value={key}>{label}</option>
                        ))}
                    </select>

                    {/* Assignee filter */}
                    <select
                        value={filterAssignee}
                        onChange={e => setFilterAssignee(e.target.value)}
                        className="px-3 py-2 bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded-lg text-sm text-gray-700 dark:text-gray-200 focus:ring-2 focus:ring-indigo-500/50"
                    >
                        <option value="all">All Technicians</option>
                        <option value="unassigned">Unassigned</option>
                        {staff.map(s => (
                            <option key={s.id} value={s.id}>{s.name}</option>
                        ))}
                    </select>

                    {/* Count badge */}
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                        {filteredAppointments.length} result{filteredAppointments.length !== 1 ? 's' : ''}
                    </span>

                    {/* Clear */}
                    {activeFilters > 0 && (
                        <button
                            onClick={() => { setFilterStatus('all'); setFilterAssignee('all'); }}
                            className="flex items-center gap-1 text-sm text-red-500 hover:text-red-700"
                        >
                            <X className="h-3.5 w-3.5" /> Clear
                        </button>
                    )}
                </div>
            )}

            {/* ── Empty state ── */}
            {filteredAppointments.length === 0 ? (
                <div className="text-center py-12 bg-gray-50 dark:bg-gray-800 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-700">
                    <Wrench className="mx-auto h-12 w-12 text-gray-400" />
                    <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">
                        {activeFilters > 0 ? 'No repairs match your filters' : 'No repairs assigned'}
                    </h3>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        {activeFilters > 0 ? 'Try adjusting your filters.' : "You don't have any active repairs assigned to you."}
                    </p>
                </div>
            ) : viewMode === 'table' ? (

                /* ── Table View ── */
                <div className="bg-white dark:bg-gray-800 shadow overflow-x-auto sm:rounded-lg">
                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                        <thead className="bg-gray-50 dark:bg-gray-700">
                            <tr>
                                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Customer</th>
                                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Service</th>
                                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Assigned To</th>
                                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Progress</th>
                                <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Time</th>
                                <th className="px-5 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                            {filteredAppointments.map(apt => (
                                <tr key={apt.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                                    <td className="px-5 py-4 whitespace-nowrap">
                                        <div className="flex items-center gap-3">
                                            <div className="h-9 w-9 bg-indigo-100 dark:bg-indigo-900/50 rounded-full flex items-center justify-center flex-shrink-0">
                                                <Car className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                                            </div>
                                            <div>
                                                <div className="text-sm font-semibold text-gray-900 dark:text-white">{apt.customer_name}</div>
                                                <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
                                                    <Phone className="h-3 w-3" />{apt.phone_number}
                                                </div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-5 py-4 whitespace-nowrap">
                                        <div className="text-sm text-gray-900 dark:text-white">{apt.service_type}</div>
                                        {apt.emergency_request && (
                                            <span className="px-2 inline-flex text-xs font-semibold rounded-full bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300">
                                                🚨 Emergency
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-5 py-4 whitespace-nowrap">
                                        <AssigneeChip staffId={apt.assigned_staff_id} staffList={staff} />
                                    </td>
                                    <td className="px-5 py-4 min-w-[160px]">
                                        <StatusBadge status={apt.status} />
                                        <ProgressBar status={apt.status} />
                                    </td>
                                    <td className="px-5 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                        {apt.status === 'in_progress' || apt.status === 'diagnosing' || apt.status === 'waiting_parts' ? (
                                            <div>
                                                <span className="font-bold text-blue-600 dark:text-blue-400">
                                                    {formatElapsed(apt.started_at)}
                                                </span>
                                                {apt.started_at && (
                                                    <div className="text-xs opacity-70">
                                                        Started {new Date(apt.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <span>{new Date(apt.appointment_time).toLocaleDateString()}</span>
                                        )}
                                    </td>
                                    <td className="px-5 py-4 whitespace-nowrap text-right text-sm font-medium space-x-3">
                                        <button
                                            onClick={() => handleOpenCase(apt)}
                                            className="inline-flex items-center px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 transition-colors"
                                        >
                                            Open Case
                                        </button>
                                        <button
                                            onClick={() => openAssignModal(apt)}
                                            className="inline-flex items-center px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                                        >
                                            <User className="h-3.5 w-3.5 mr-1" />
                                            {apt.assigned_staff_id ? 'Reassign' : 'Assign'}
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

            ) : (

                /* ── Card View ── */
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
                    {filteredAppointments.map(apt => (
                        <div key={apt.id} className="bg-white dark:bg-gray-800 overflow-hidden shadow-sm rounded-xl border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow">
                            <div className="p-5">
                                <div className="flex items-start justify-between mb-3">
                                    <div>
                                        <h3 className="text-base font-semibold text-gray-900 dark:text-white">{apt.customer_name}</h3>
                                        <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1 mt-0.5">
                                            <Phone className="h-3 w-3" />{apt.phone_number}
                                        </p>
                                    </div>
                                    {apt.emergency_request && <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />}
                                </div>

                                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">{apt.service_type}</p>

                                {/* Assignee */}
                                <div className="flex items-center gap-1.5 mb-3 text-xs text-gray-500 dark:text-gray-400">
                                    <User className="h-3.5 w-3.5" />
                                    <AssigneeChip staffId={apt.assigned_staff_id} staffList={staff} />
                                </div>

                                {/* Progress */}
                                <ProgressBar status={apt.status} />

                                {/* Elapsed */}
                                {(apt.status === 'in_progress' || apt.status === 'diagnosing' || apt.status === 'waiting_parts') && apt.started_at && (
                                    <p className="mt-2 text-xs font-semibold text-blue-600 dark:text-blue-400">
                                        {formatElapsed(apt.started_at)}
                                    </p>
                                )}

                                {/* Actions */}
                                <div className="mt-4 flex gap-2">
                                    <button
                                        onClick={() => handleOpenCase(apt)}
                                        className="flex-1 py-2 px-3 rounded-lg text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-colors text-center"
                                    >
                                        Open Case
                                    </button>
                                    <button
                                        onClick={() => openAssignModal(apt)}
                                        className="py-2 px-3 rounded-lg text-sm font-medium border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                                    >
                                        <User className="h-4 w-4" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* ── Assign Modal ── */}
            {showAssignModal && selectedAppointment && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-md shadow-xl">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                            Assign Technician
                        </h3>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                            {selectedAppointment.customer_name} — {selectedAppointment.service_type}
                        </p>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Technician
                                </label>
                                <select
                                    value={selectedStaffId}
                                    onChange={e => setSelectedStaffId(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                >
                                    <option value="">— Select technician —</option>
                                    {staff.map(s => (
                                        <option key={s.id} value={s.id}>{s.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex justify-end gap-3">
                                <button onClick={() => setShowAssignModal(false)} className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors">
                                    Cancel
                                </button>
                                <button onClick={handleAssign} disabled={!selectedStaffId} className="px-4 py-2 text-sm font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors">
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

export default StaffDashboard;
