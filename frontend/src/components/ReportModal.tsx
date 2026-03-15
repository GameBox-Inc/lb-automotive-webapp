import React, { useState, useEffect } from 'react';
import { Dialog, DialogPanel, DialogTitle, Transition, TransitionChild } from '@headlessui/react';
import { X, DollarSign, Wrench, Clock, Calendar, Download } from 'lucide-react';
import { apiClient } from '../lib/supabase';
import { formatCurrency, formatNumber } from '../utils/format';
import { LoadingSpinner } from './LoadingSpinner';
import { format } from 'date-fns';
import toast from 'react-hot-toast';

interface ReportModalProps {
    isOpen: boolean;
    onClose: () => void;
}

interface ReportSummary {
    total_revenue: number;
    total_repairs: number;
    avg_duration: number;
    avg_session_time: number;
}

interface RepairHistoryItem {
    case_number: number;
    date: string;
    customer: string;
    service: string;
    price: number;
    duration: number;
    actual_duration: number;
}

export function ReportModal({ isOpen, onClose }: ReportModalProps) {
    const [loading, setLoading] = useState(true);
    const [timeframe, setTimeframe] = useState<'7d' | '30d' | '90d' | 'all'>('30d');
    const [summary, setSummary] = useState<ReportSummary | null>(null);
    const [history, setHistory] = useState<RepairHistoryItem[]>([]);

    useEffect(() => {
        if (isOpen) {
            fetchReportData();
        }
    }, [isOpen, timeframe]);

    const downloadCsv = () => {
        try {
            const rows = history.map((item) => ({
                date: item.date,
                case_number: item.case_number,
                customer: item.customer,
                service: item.service,
                price: item.price,
                estimated_minutes: item.duration,
                actual_minutes: item.actual_duration
            }));

            const header = Object.keys(rows[0] || {
                date: '',
                case_number: '',
                customer: '',
                service: '',
                price: '',
                estimated_minutes: '',
                actual_minutes: ''
            });

            const escape = (value: unknown) => {
                const s = value == null ? '' : String(value);
                const needsQuotes = /[",\n]/.test(s);
                const escaped = s.replaceAll('"', '""');
                return needsQuotes ? `"${escaped}"` : escaped;
            };

            const csv = [
                header.join(','),
                ...rows.map(r => header.map(k => escape((r as any)[k])).join(','))
            ].join('\n');

            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `lb-automotive-reports-${timeframe}.csv`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error('CSV export failed', e);
            toast.error('Failed to export CSV');
        }
    };

    const fetchReportData = async () => {
        setLoading(true);
        try {
            const summaryData = await apiClient.getReportSummary(timeframe);
            const historyData = await apiClient.getReportHistory(timeframe, 100); // Keep table consistent with timeframe
            setSummary(summaryData as any);
            setHistory(historyData as any);
        } catch (error) {
            console.error('Error fetching reports:', error);
            toast.error('Failed to load report data');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Transition show={isOpen}>
            <Dialog open={isOpen} onClose={onClose} className="relative z-50">
                <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0" enterTo="opacity-100" leave="ease-in duration-150" leaveFrom="opacity-100" leaveTo="opacity-0">
                    <div className="fixed inset-0 bg-black/50" aria-hidden="true" />
                </TransitionChild>
                <div className="fixed inset-0 flex items-center justify-center p-4">
                    <TransitionChild enter="ease-out duration-200" enterFrom="opacity-0 scale-95" enterTo="opacity-100 scale-100" leave="ease-in duration-150" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-95">
                        <DialogPanel className="bg-white dark:bg-gray-800 rounded-lg w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col shadow-xl">
                            {/* Header */}
                            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-900">
                                <div className="flex items-center gap-3">
                                    <div className="bg-blue-100 dark:bg-blue-900 p-2 rounded-lg">
                                        <Calendar className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                                    </div>
                                    <div>
                                        <DialogTitle className="text-xl font-bold text-gray-900 dark:text-white">Performance Reports</DialogTitle>
                                        <p className="text-sm text-gray-500 dark:text-gray-400">Repair history and shop metrics</p>
                                    </div>
                                </div>
                                <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                                    <X className="h-6 w-6" />
                                </button>
                            </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6">

                    {/* Controls */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div className="inline-flex rounded-md shadow-sm w-full sm:w-auto" role="group">
                            {(['7d', '30d', '90d', 'all'] as const).map((period) => (
                                <button
                                    key={period}
                                    type="button"
                                    onClick={() => setTimeframe(period)}
                                    className={`px-4 py-2 text-sm font-medium border ${timeframe === period
                                        ? 'bg-blue-600 text-white border-blue-600'
                                        : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-600'
                                        } ${period === '7d' ? 'rounded-l-lg' : period === 'all' ? 'rounded-r-lg' : ''
                                        }`}
                                >
                                    {period === 'all' ? 'All Time' : `Last ${period.replace('d', ' Days')}`}
                                </button>
                            ))}
                        </div>
                        <button
                            type="button"
                            onClick={downloadCsv}
                            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-700 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
                            title="Export recent history as CSV"
                        >
                            <Download className="h-4 w-4" />
                            Export CSV
                        </button>
                    </div>

                    {loading ? (
                        <div className="flex justify-center py-12">
                            <LoadingSpinner size="lg" />
                        </div>
                    ) : (
                        <>
                            {/* Metrics Cards */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                                <div className="bg-green-50 dark:bg-green-900/20 p-6 rounded-xl border border-green-100 dark:border-green-800">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium text-green-600 dark:text-green-400">Total Revenue</p>
                                            <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                                                {formatCurrency(summary?.total_revenue ?? 0)}
                                            </p>
                                        </div>
                                        <div className="bg-green-100 dark:bg-green-800 p-3 rounded-full">
                                            <DollarSign className="w-6 h-6 text-green-600 dark:text-green-300" />
                                        </div>
                                    </div>
                                </div>

                                <div className="bg-blue-50 dark:bg-blue-900/20 p-6 rounded-xl border border-blue-100 dark:border-blue-800">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium text-blue-600 dark:text-blue-400">Total Repairs</p>
                                            <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                                                {formatNumber(summary?.total_repairs ?? 0)}
                                            </p>
                                        </div>
                                        <div className="bg-blue-100 dark:bg-blue-800 p-3 rounded-full">
                                            <Wrench className="w-6 h-6 text-blue-600 dark:text-blue-300" />
                                        </div>
                                    </div>
                                </div>

                                <div className="bg-purple-50 dark:bg-purple-900/20 p-6 rounded-xl border border-purple-100 dark:border-purple-800">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium text-purple-600 dark:text-purple-400">Est. Duration</p>
                                            <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                                                {summary?.avg_duration ?? 0} <span className="text-lg font-normal text-gray-500">min</span>
                                            </p>
                                        </div>
                                        <div className="bg-purple-100 dark:bg-purple-800 p-3 rounded-full">
                                            <Wrench className="w-6 h-6 text-purple-600 dark:text-purple-300" />
                                        </div>
                                    </div>
                                </div>

                                <div className="bg-orange-50 dark:bg-orange-900/20 p-6 rounded-xl border border-orange-100 dark:border-orange-800">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium text-orange-600 dark:text-orange-400">Avg Session Time</p>
                                            <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                                                {summary?.avg_session_time ?? 0} <span className="text-lg font-normal text-gray-500">min</span>
                                            </p>
                                        </div>
                                        <div className="bg-orange-100 dark:bg-orange-800 p-3 rounded-full">
                                            <Clock className="w-6 h-6 text-orange-600 dark:text-orange-300" />
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* History Table */}
                            <div className="bg-white dark:bg-gray-800 rounded-lg shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
                                <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                                    <h3 className="text-lg font-medium text-gray-900 dark:text-white">Repair History</h3>
                                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Filtered by timeframe (max 100 rows)</p>
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                                        <thead className="bg-gray-50 dark:bg-gray-900">
                                            <tr>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Date</th>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Case #</th>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Customer</th>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Service</th>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Price</th>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Est. Time</th>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actual Time</th>
                                            </tr>
                                        </thead>
                                        <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                                            {history.length === 0 ? (
                                                <tr>
                                                    <td colSpan={7} className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
                                                        No completed repair history found for the selected period.
                                                    </td>
                                                </tr>
                                            ) : (
                                                history.map((item, index) => (
                                                    <tr key={index} className="hover:bg-gray-50 dark:hover:bg-gray-700 text-sm">
                                                        <td className="px-6 py-4 whitespace-nowrap text-gray-900 dark:text-white">
                                                            {format(new Date(item.date), 'MMM dd, yyyy')}
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-gray-500 dark:text-gray-400">
                                                            #{item.case_number}
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-gray-900 dark:text-white font-medium">
                                                            {item.customer}
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-gray-500 dark:text-gray-300">
                                                            {item.service}
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-green-600 dark:text-green-400 font-medium">
                                                            {formatCurrency(item.price)}
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-gray-500 dark:text-gray-400">
                                                            {item.duration} min
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-blue-600 dark:text-blue-400 font-medium">
                                                            {item.actual_duration} min
                                                        </td>
                                                    </tr>
                                                ))
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </>
                    )}
                </div>
                        </DialogPanel>
                    </TransitionChild>
                </div>
            </Dialog>
        </Transition>
    );
}
