import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../lib/supabase';

import { ArrowLeft, Save, Plus, Trash2, FileText, CheckCircle, Clock, AlertTriangle, PenTool, Printer, Wrench, Wand2 } from 'lucide-react';
import { formatCurrency } from '../utils/format';
import toast from 'react-hot-toast';
import { LoadingSpinner } from '../components/LoadingSpinner';
import SignatureCanvas from 'react-signature-canvas';

// Interface for strictly typed state
interface CaseNote {
    id: string;
    note: string;
    is_internal: boolean;
    created_at: string;
    staff_id: string;
}

interface CasePart {
    id: string;
    part_name: string;
    quantity: number;
    price: number;
    status: string;
    created_at: string;
}

interface CaseDetail {
    id: string;
    case_number: number;
    status: string;
    customer_signature?: string;
    appointment_id: string;
    notes: CaseNote[];
    parts: CasePart[];
    customer_name?: string; // Enriched
    service_type?: string; // Enriched
    vehicle_info?: string; // Enriched from metadata or appt
}

const CaseDetails = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [caseData, setCaseData] = useState<CaseDetail | null>(null);
    const [activeTab, setActiveTab] = useState<'notes' | 'parts' | 'sign'>('notes');

    // Form States
    const [newNote, setNewNote] = useState('');
    const [newPartName, setNewPartName] = useState('');
    const [newPartPrice, setNewPartPrice] = useState('');
    const [newPartQty, setNewPartQty] = useState(1);

    // AI State
    const [isGenerating, setIsGenerating] = useState(false);

    // Signature
    const sigCanvas = useRef<SignatureCanvas>(null);
    const [isSigning, setIsSigning] = useState(false);

    useEffect(() => {
        if (id) {
            console.log('CaseDetails mounted with ID:', id);
            fetchCaseDetails(id.trim());
        }
    }, [id]);

    async function fetchCaseDetails(caseId: string) {
        console.log('Fetching case details for:', caseId);
        try {
            // Trim ID to prevent URL errors
            const cleanId = caseId.trim();
            const data = await apiClient.request<CaseDetail>(`/cases/${cleanId}`);
            const appt = await apiClient.getAppointment(data.appointment_id);
            setCaseData({
                ...data,
                customer_name: appt.customer_name,
                service_type: appt.service_type,
                vehicle_info: appt.notes
            });
        } catch (error) {
            console.error('Error fetching case:', error);
            toast.error('Failed to load case details');
        } finally {
            setLoading(false);
        }
    }

    const handleStatusChange = async (newStatus: string) => {
        if (!caseData) return;
        try {
            await apiClient.request(`/cases/${caseData.id}`, {
                method: 'PUT',
                body: JSON.stringify({ status: newStatus })
            });

            // Also update appointment status if it's 'completed' or 'in_progress'
            const apptStatus = newStatus === 'completed' ? 'completed' : 'in_progress';
            await apiClient.updateAppointmentStatus(caseData.appointment_id, apptStatus);

            setCaseData(prev => prev ? { ...prev, status: newStatus } : null);
            toast.success(`Status updated to ${newStatus.replace('_', ' ')} `);

            if (newStatus === 'completed') {
                setActiveTab('sign');
            }
        } catch (error) {
            toast.error('Failed to update status');
        }
    };

    const handleAddNote = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!caseData || !newNote.trim()) return;

        try {
            await apiClient.request(`/cases/${caseData.id}/notes`, {
                method: 'POST',
                body: JSON.stringify({ note: newNote, is_internal: true })
            });
            toast.success('Note added');
            setNewNote('');
            fetchCaseDetails(caseData.id);
        } catch (error) {
            toast.error('Failed to add note');
        }
    };

    const handleAIGenerate = async () => {
        if (!caseData || !newNote.trim()) {
            toast.error('Please enter rough notes first');
            return;
        }

        if (newNote.length < 5) {
            toast.error('Note is too short for AI polishing');
            return;
        }

        setIsGenerating(true);
        try {
            const result = await apiClient.request<{ note: string }>(`/cases/${caseData.id}/generate-note`, {
                method: 'POST',
                body: JSON.stringify({ text: newNote })
            });

            setNewNote(result.note);
            toast.success('Note polished by AI ✨');
        } catch (error) {
            console.error(error);
            toast.error('Failed to generate note');
        } finally {
            setIsGenerating(false);
        }
    };

    const handleAddPart = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!caseData || !newPartName.trim()) return;

        try {
            await apiClient.request(`/cases/${caseData.id}/parts`, {
                method: 'POST',
                body: JSON.stringify({
                    part_name: newPartName,
                    quantity: newPartQty,
                    price: parseFloat(newPartPrice) || 0
                })
            });
            toast.success('Part added');
            setNewPartName('');
            setNewPartPrice('');
            setNewPartQty(1);
            fetchCaseDetails(caseData.id);
        } catch (error) {
            toast.error('Failed to add part');
        }
    };

    const handleCompleteAndSign = async () => {
        if (!caseData || !sigCanvas.current) return;

        if (sigCanvas.current.isEmpty()) {
            toast.error('Please provide a signature');
            return;
        }

        const signatureData = sigCanvas.current.toDataURL();
        setIsSigning(true);

        try {
            await apiClient.request(`/cases/${caseData.id}/sign`, {
                method: 'POST',
                body: JSON.stringify({
                    customer_signature: signatureData,
                    status: 'completed'
                })
            });

            // Update appointment status to completed
            await apiClient.updateAppointmentStatus(caseData.appointment_id, 'completed');

            // Update local state to show "Case Completed" view immediately
            setCaseData(prev => prev ? {
                ...prev,
                status: 'completed',
                customer_signature: signatureData
            } : null);

            toast.success('Case completed and signed!');

            // Short delay so they can see the completed UI state before redirect
            setTimeout(() => {
                navigate('/repairs');
            }, 2000);

        } catch (error) {
            console.error(error);
            toast.error('Failed to complete case');
        } finally {
            setIsSigning(false);
        }
    };

    if (loading) return <LoadingSpinner />;
    if (!caseData) return <div>Case not found</div>;

    return (
        <div className="max-w-4xl mx-auto space-y-6 pb-20">
            {/* Header */}
            <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                    <button onClick={() => navigate(-1)} className="text-gray-500 hover:text-gray-700">
                        <ArrowLeft className="h-6 w-6" />
                    </button>
                    <span className="px-3 py-1 rounded-full text-sm font-bold bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200">
                        Case #{caseData.case_number}
                    </span>
                </div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                    {caseData.customer_name}
                </h1>
                <div className="grid grid-cols-2 gap-4 text-sm text-gray-500 dark:text-gray-400">
                    <div>Service: <span className="font-medium text-gray-900 dark:text-white">{caseData.service_type}</span></div>
                    <div className="flex items-center gap-2">
                        <span>Status:</span>
                        <select
                            value={caseData.status}
                            onChange={(e) => handleStatusChange(e.target.value)}
                            className="bg-gray-50 dark:bg-gray-700 border-none text-xs font-bold py-1 px-2 rounded-full cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600 focus:ring-2 focus:ring-indigo-500 transition-all capitalize text-gray-900 dark:text-white"
                        >
                            <option value="open">Open</option>
                            <option value="diagnosing">Diagnosing</option>
                            <option value="waiting_for_parts">Waiting for Parts</option>
                            <option value="repairing">Repairing</option>
                            <option value="testing">Testing</option>
                            <option value="completed">Completed</option>
                            <option value="cancelled">Cancelled</option>
                        </select>
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 sticky top-0 z-10">
                <button
                    onClick={() => setActiveTab('notes')}
                    className={`flex-1 py-4 text-sm font-medium text-center border-b-2 ${activeTab === 'notes' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'
                        }`}
                >
                    <FileText className="w-5 h-5 mx-auto mb-1" />
                    Notes
                </button>
                <button
                    onClick={() => setActiveTab('parts')}
                    className={`flex-1 py-4 text-sm font-medium text-center border-b-2 ${activeTab === 'parts' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'
                        }`}
                >
                    <Wrench className="w-5 h-5 mx-auto mb-1" />
                    Parts
                </button>
                <button
                    onClick={() => setActiveTab('sign')}
                    className={`flex-1 py-4 text-sm font-medium text-center border-b-2 ${activeTab === 'sign' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'
                        }`}
                >
                    <CheckCircle className="w-5 h-5 mx-auto mb-1" />
                    Sign & Close
                </button>
            </div>

            {/* Content */}
            <div className="space-y-6">
                {activeTab === 'notes' && (
                    <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
                        <div className="space-y-4 mb-6 max-h-96 overflow-y-auto">
                            {caseData.notes.length === 0 ? (
                                <p className="text-gray-500 text-center italic">No notes yet.</p>
                            ) : (
                                caseData.notes.map(note => (
                                    <div key={note.id} className="bg-gray-50 dark:bg-gray-700 p-3 rounded-lg">
                                        <p className="text-sm text-gray-800 dark:text-gray-200">{note.note}</p>
                                        <div className="mt-1 text-xs text-gray-500">
                                            {new Date(note.created_at).toLocaleString()}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                        <form onSubmit={handleAddNote} className="space-y-2">
                            <div className="relative">
                                <textarea
                                    value={newNote}
                                    onChange={(e) => setNewNote(e.target.value)}
                                    placeholder="Add a note... (Dictate roughly and click wand to polish)"
                                    className="w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    rows={3}
                                />
                                <button
                                    type="button"
                                    onClick={handleAIGenerate}
                                    disabled={isGenerating || !newNote.trim()}
                                    className="absolute bottom-2 right-2 p-1.5 bg-indigo-100 text-indigo-600 rounded-md hover:bg-indigo-200 disabled:opacity-50 dark:bg-indigo-900/50 dark:text-indigo-300"
                                    title="AI Polish"
                                >
                                    {isGenerating ? <LoadingSpinner size="sm" /> : <Wand2 className="h-4 w-4" />}
                                </button>
                            </div>
                            <button
                                type="submit"
                                disabled={isGenerating}
                                className="w-full px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 font-medium"
                            >
                                Send Internal Note
                            </button>
                        </form>
                    </div>
                )}

                {activeTab === 'parts' && (
                    <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
                        <div className="space-y-4 mb-6">
                            {caseData.parts.map(part => (
                                <div key={part.id} className="flex justify-between items-center py-2 border-b border-gray-100 dark:border-gray-700">
                                    <div>
                                        <div className="font-medium text-gray-900 dark:text-white">{part.part_name}</div>
                                        <div className="text-sm text-gray-500">Qty: {part.quantity} @ {formatCurrency(part.price)} each</div>
                                    </div>
                                    <div className="font-mono font-medium">
                                        {formatCurrency(part.price * part.quantity)}
                                    </div>
                                </div>
                            ))}
                            <div className="flex justify-between items-center pt-2 font-bold text-lg">
                                <span>Total Parts Cost:</span>
                                <span>
                                    {formatCurrency(caseData.parts.reduce((sum, part) => sum + (part.price * part.quantity), 0))}
                                </span>
                            </div>
                        </div>

                        <form onSubmit={handleAddPart} className="space-y-4 bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
                            <h3 className="text-sm font-medium text-gray-900 dark:text-white">Add Part</h3>
                            <div className="grid grid-cols-6 gap-4">
                                <div className="col-span-3">
                                    <input
                                        type="text"
                                        value={newPartName}
                                        onChange={(e) => setNewPartName(e.target.value)}
                                        placeholder="Part Name"
                                        className="w-full rounded-md border-gray-300 shadow-sm sm:text-sm dark:bg-gray-800 dark:border-gray-600"
                                    />
                                </div>
                                <div className="col-span-1">
                                    <input
                                        type="number"
                                        value={newPartQty}
                                        onChange={(e) => setNewPartQty(parseInt(e.target.value))}
                                        min="1"
                                        className="w-full rounded-md border-gray-300 shadow-sm sm:text-sm dark:bg-gray-800 dark:border-gray-600"
                                    />
                                </div>
                                <div className="col-span-2">
                                    <input
                                        type="number"
                                        value={newPartPrice}
                                        onChange={(e) => setNewPartPrice(e.target.value)}
                                        placeholder="Price"
                                        step="0.01"
                                        className="w-full rounded-md border-gray-300 shadow-sm sm:text-sm dark:bg-gray-800 dark:border-gray-600"
                                    />
                                </div>
                            </div>
                            <button
                                type="submit"
                                className="w-full px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
                            >
                                <Plus className="h-4 w-4 inline-block mr-2" />
                                Add Part
                            </button>
                        </form>
                    </div>
                )}

                {activeTab === 'sign' && (
                    <div className="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
                        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">Customer Authorization</h3>

                        {caseData.customer_signature ? (
                            <div className="space-y-6">
                                <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-white">
                                    <p className="text-sm text-gray-500 mb-2">Signed by Customer:</p>
                                    <img
                                        src={caseData.customer_signature}
                                        alt="Customer Signature"
                                        className="max-w-full h-auto mx-auto border-b border-gray-100 pb-4"
                                    />
                                </div>

                                <div className="bg-green-50 dark:bg-green-900/30 p-4 rounded-lg flex items-center justify-center text-green-700 dark:text-green-300">
                                    <CheckCircle className="h-6 w-6 mr-2" />
                                    <div>
                                        <p className="font-bold">Case Completed & Signed</p>
                                        <p className="text-xs opacity-75">
                                            {/* Closed at isn't in CaseDetail yet but status is */}
                                            This case is closed.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <>
                                <p className="text-sm text-gray-500 mb-4">
                                    By signing below, I acknowledge the completion of repairs and authorize the charges listed above.
                                </p>

                                <div className="border-2 border-dashed border-gray-300 rounded-lg p-1 bg-white">
                                    <SignatureCanvas
                                        ref={sigCanvas}
                                        canvasProps={{
                                            className: 'w-full h-48',
                                            style: { width: '100%', height: '200px' }
                                        }}
                                    />
                                </div>
                                <div className="flex justify-between mt-2 text-sm">
                                    <button onClick={() => sigCanvas.current?.clear()} className="text-red-500 hover:text-red-700 font-medium">Clear</button>
                                    <span className="text-gray-400">Sign in the box above</span>
                                </div>

                                <div className="mt-8">
                                    <button
                                        onClick={handleCompleteAndSign}
                                        disabled={isSigning}
                                        className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-base font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
                                    >
                                        {isSigning ? <LoadingSpinner /> : (
                                            <>
                                                <CheckCircle className="h-5 w-5 mr-2" />
                                                Complete Case & Send Report
                                            </>
                                        )}
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};


export default CaseDetails
