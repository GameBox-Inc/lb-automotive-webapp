import React, { useId, useEffect, useState } from 'react';
import { Dialog, DialogPanel, DialogTitle, Transition, TransitionChild } from '@headlessui/react';
import { apiClient, Customer } from '../lib/supabase';
import { Users, UserPlus, Edit2, Trash2, Phone, Mail, Calendar, History } from 'lucide-react';
import toast from 'react-hot-toast';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { EmptyState } from '../components/EmptyState';

const AdminCustomers = () => {
    const formId = useId();
    const [customers, setCustomers] = useState<Customer[]>([]);
    const [loading, setLoading] = useState(true);
    const [showAddModal, setShowAddModal] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);
    const [showHistoryModal, setShowHistoryModal] = useState(false);
    const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
    const [customerHistory, setCustomerHistory] = useState<any[]>([]);
    const [loadingHistory, setLoadingHistory] = useState(false);

    // Form state
    const [formData, setFormData] = useState({
        name: '',
        phone: '',
        email: ''
    });

    useEffect(() => {
        fetchCustomers();
    }, []);

    async function fetchCustomers() {
        try {
            setLoading(true);
            const data = await apiClient.getCustomers();
            setCustomers(data);
        } catch (error) {
            console.error('Error fetching customers:', error);
            toast.error('Failed to load customers');
        } finally {
            setLoading(false);
        }
    }

    async function handleAddCustomer(e: React.FormEvent) {
        e.preventDefault();
        try {
            await apiClient.createCustomer(formData);
            toast.success('Customer added successfully');
            setShowAddModal(false);
            resetForm();
            fetchCustomers();
        } catch (error: any) {
            toast.error(error.message || 'Failed to add customer');
        }
    }

    async function handleUpdateCustomer(e: React.FormEvent) {
        e.preventDefault();
        if (!selectedCustomer) return;

        try {
            await apiClient.updateCustomer(selectedCustomer.id, formData);
            toast.success('Customer updated successfully');
            setShowEditModal(false);
            resetForm();
            fetchCustomers();
        } catch (error: any) {
            toast.error(error.message || 'Failed to update customer');
        }
    }

    async function handleDeleteCustomer(customer: Customer) {
        if (!confirm(`Are you sure you want to delete ${customer.name}?`)) return;

        try {
            await apiClient.deleteCustomer(customer.id);
            toast.success('Customer deleted successfully');
            fetchCustomers();
        } catch (error) {
            toast.error('Failed to delete customer');
        }
    }

    async function viewCustomerHistory(customer: Customer) {
        setSelectedCustomer(customer);
        setShowHistoryModal(true);
        setLoadingHistory(true);

        try {
            const history = await apiClient.getCustomerHistory(customer.id);
            setCustomerHistory(history);
        } catch (error) {
            toast.error('Failed to load customer history');
        } finally {
            setLoadingHistory(false);
        }
    }

    function openEditModal(customer: Customer) {
        setSelectedCustomer(customer);
        setFormData({
            name: customer.name,
            phone: customer.phone,
            email: customer.email || ''
        });
        setShowEditModal(true);
    }

    function resetForm() {
        setFormData({ name: '', phone: '', email: '' });
        setSelectedCustomer(null);
    }

    function formatPhoneNumber(phone: string) {
        // Format as (XXX) XXX-XXXX
        const cleaned = phone.replace(/\D/g, '');
        if (cleaned.length === 10) {
            return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
        }
        return phone;
    }

    if (loading) return <LoadingSpinner />;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Customer Management</h1>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        Manage customer information and view appointment history
                    </p>
                </div>
                <button
                    onClick={() => setShowAddModal(true)}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-lb-red-primary hover:bg-lb-red-light"
                >
                    <UserPlus className="h-4 w-4 mr-2" />
                    Add Customer
                </button>
            </div>

            <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead className="bg-gray-50 dark:bg-gray-700">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                Name
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                Phone
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                Email
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                Joined
                            </th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                Actions
                            </th>
                        </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                        {customers.length === 0 ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-10">
                                    <EmptyState
                                        icon={<Users className="h-7 w-7" />}
                                        title="No customers yet"
                                        description="Add your first customer to get started."
                                        action={
                                            <button
                                                type="button"
                                                onClick={() => { setShowAddModal(true); resetForm(); }}
                                                className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-lb-red-primary rounded-md hover:bg-lb-red-light"
                                            >
                                                Add Customer
                                            </button>
                                        }
                                    />
                                </td>
                            </tr>
                        ) : (
                            customers.map((customer) => (
                                <tr key={customer.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="text-sm font-medium text-gray-900 dark:text-white">
                                            {customer.name}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="flex items-center text-sm text-gray-900 dark:text-white">
                                            <Phone className="h-4 w-4 mr-2 text-gray-400" />
                                            {formatPhoneNumber(customer.phone)}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="flex items-center text-sm text-gray-500 dark:text-gray-400">
                                            {customer.email ? (
                                                <>
                                                    <Mail className="h-4 w-4 mr-2" />
                                                    {customer.email}
                                                </>
                                            ) : (
                                                <span className="text-gray-400">No email</span>
                                            )}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                        <div className="flex items-center">
                                            <Calendar className="h-4 w-4 mr-2" />
                                            {new Date(customer.created_at || '').toLocaleDateString()}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                        <div className="flex justify-end space-x-2">
                                            <button
                                                onClick={() => viewCustomerHistory(customer)}
                                                className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300"
                                                title="View History"
                                            >
                                                <History className="h-4 w-4" />
                                            </button>
                                            <button
                                                onClick={() => openEditModal(customer)}
                                                className="text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300"
                                                title="Edit"
                                            >
                                                <Edit2 className="h-4 w-4" />
                                            </button>
                                            <button
                                                onClick={() => handleDeleteCustomer(customer)}
                                                className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                                                title="Delete"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {/* Add Customer Modal */}
            <Transition show={showAddModal}>
                <Dialog open={showAddModal} onClose={() => { setShowAddModal(false); resetForm(); }} className="relative z-50">
                    <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0" enterTo="opacity-100" leave="ease-in duration-150" leaveFrom="opacity-100" leaveTo="opacity-0">
                        <div className="fixed inset-0 bg-black/50" aria-hidden="true" />
                    </TransitionChild>
                    <div className="fixed inset-0 flex items-center justify-center p-4">
                        <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0 scale-95" enterTo="opacity-100 scale-100" leave="ease-in duration-150" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-95">
                            <DialogPanel className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md shadow-xl">
                                <DialogTitle className="text-xl font-bold text-gray-900 dark:text-white mb-4">Add New Customer</DialogTitle>
                        <form onSubmit={handleAddCustomer}>
                            <div className="space-y-4">
                                <div>
                                    <label htmlFor={`${formId}-add-name`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                        Name *
                                    </label>
                                    <input
                                        id={`${formId}-add-name`}
                                        type="text"
                                        value={formData.name}
                                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                        required
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    />
                                </div>
                                <div>
                                    <label htmlFor={`${formId}-add-phone`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                        Phone *
                                    </label>
                                    <input
                                        id={`${formId}-add-phone`}
                                        type="tel"
                                        value={formData.phone}
                                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                        required
                                        placeholder="(555) 555-5555"
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    />
                                </div>
                                <div>
                                    <label htmlFor={`${formId}-add-email`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                        Email
                                    </label>
                                    <input
                                        id={`${formId}-add-email`}
                                        type="email"
                                        value={formData.email}
                                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    />
                                </div>
                            </div>
                            <div className="mt-6 flex justify-end space-x-3">
                                <button
                                    type="button"
                                    onClick={() => { setShowAddModal(false); resetForm(); }}
                                    className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-lb-red-primary hover:bg-lb-red-light"
                                >
                                    Add Customer
                                </button>
                            </div>
                        </form>
                            </DialogPanel>
                        </TransitionChild>
                    </div>
                </Dialog>
            </Transition>

            {/* Edit Customer Modal */}
            <Transition show={showEditModal}>
                <Dialog open={showEditModal} onClose={() => { setShowEditModal(false); resetForm(); }} className="relative z-50">
                    <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0" enterTo="opacity-100" leave="ease-in duration-150" leaveFrom="opacity-100" leaveTo="opacity-0">
                        <div className="fixed inset-0 bg-black/50" aria-hidden="true" />
                    </TransitionChild>
                    <div className="fixed inset-0 flex items-center justify-center p-4">
                        <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0 scale-95" enterTo="opacity-100 scale-100" leave="ease-in duration-150" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-95">
                            <DialogPanel className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md shadow-xl">
                                <DialogTitle className="text-xl font-bold text-gray-900 dark:text-white mb-4">Edit Customer</DialogTitle>
                        <form onSubmit={handleUpdateCustomer}>
                            <div className="space-y-4">
                                <div>
                                    <label htmlFor={`${formId}-edit-name`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                        Name *
                                    </label>
                                    <input
                                        id={`${formId}-edit-name`}
                                        type="text"
                                        value={formData.name}
                                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                        required
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    />
                                </div>
                                <div>
                                    <label htmlFor={`${formId}-edit-phone`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                        Phone *
                                    </label>
                                    <input
                                        id={`${formId}-edit-phone`}
                                        type="tel"
                                        value={formData.phone}
                                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                        required
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    />
                                </div>
                                <div>
                                    <label htmlFor={`${formId}-edit-email`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                        Email
                                    </label>
                                    <input
                                        id={`${formId}-edit-email`}
                                        type="email"
                                        value={formData.email}
                                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    />
                                </div>
                            </div>
                            <div className="mt-6 flex justify-end space-x-3">
                                <button
                                    type="button"
                                    onClick={() => { setShowEditModal(false); resetForm(); }}
                                    className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-lb-red-primary hover:bg-lb-red-light"
                                >
                                    Save Changes
                                </button>
                            </div>
                        </form>
                            </DialogPanel>
                        </TransitionChild>
                    </div>
                </Dialog>
            </Transition>

            {/* Customer History Modal */}
            <Transition show={showHistoryModal && !!selectedCustomer}>
                <Dialog open={showHistoryModal && !!selectedCustomer} onClose={() => { setShowHistoryModal(false); setSelectedCustomer(null); }} className="relative z-50">
                    <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0" enterTo="opacity-100" leave="ease-in duration-150" leaveFrom="opacity-100" leaveTo="opacity-0">
                        <div className="fixed inset-0 bg-black/50" aria-hidden="true" />
                    </TransitionChild>
                    <div className="fixed inset-0 flex items-center justify-center p-4">
                        <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0 scale-95" enterTo="opacity-100 scale-100" leave="ease-in duration-150" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-95">
                            <DialogPanel className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-3xl max-h-[80vh] overflow-y-auto shadow-xl">
                                <DialogTitle className="text-xl font-bold text-gray-900 dark:text-white mb-4">
                                    Appointment History - {selectedCustomer?.name ?? ''}
                                </DialogTitle>

                        {loadingHistory ? (
                            <div className="flex justify-center py-8">
                                <LoadingSpinner />
                            </div>
                        ) : customerHistory.length === 0 ? (
                            <p className="text-center text-gray-500 dark:text-gray-400 py-8">
                                No appointment history found
                            </p>
                        ) : (
                            <div className="space-y-4">
                                {customerHistory.map((appointment) => (
                                    <div key={appointment.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                                        <div className="flex justify-between items-start">
                                            <div>
                                                <h3 className="font-medium text-gray-900 dark:text-white">
                                                    {appointment.service_type}
                                                </h3>
                                                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                                                    {new Date(appointment.appointment_time).toLocaleString()}
                                                </p>
                                                {appointment.notes && (
                                                    <p className="text-sm text-gray-600 dark:text-gray-300 mt-2">
                                                        {appointment.notes}
                                                    </p>
                                                )}
                                            </div>
                                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${appointment.status === 'completed'
                                                ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                                : appointment.status === 'cancelled'
                                                    ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                                                    : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                                                }`}>
                                                {appointment.status}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        <div className="mt-6 flex justify-end">
                            <button
                                onClick={() => { setShowHistoryModal(false); setSelectedCustomer(null); }}
                                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
                            >
                                Close
                            </button>
                        </div>
                            </DialogPanel>
                        </TransitionChild>
                    </div>
                </Dialog>
            </Transition>
        </div>
    );
};


export default AdminCustomers
