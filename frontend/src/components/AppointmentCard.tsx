import React, { useState } from 'react'
import { format } from 'date-fns'
import { Calendar, Clock, MapPin, User, ChevronRight, AlertCircle, Wrench, CheckCircle, Phone, PenTool as Tool, Edit2, X } from 'lucide-react'
import { formatCurrency } from '../utils/format'
import toast from 'react-hot-toast'
import { apiClient } from '../lib/supabase'

interface AppointmentCardProps {
  appointment: {
    id: string
    customer_name: string
    phone_number: string
    appointment_time: string
    service_type: string
    notes?: string
    status: string
    emergency_request?: boolean
    assigned_staff_id?: string
  }
  onUpdate: () => void
  services?: any[]
  staff?: any[]
}

export const AppointmentCard: React.FC<AppointmentCardProps> = ({ appointment, onUpdate, services = [], staff: propStaff = [] }) => {
  const [isLoading, setIsLoading] = useState(false)
  const [showReschedule, setShowReschedule] = useState(false)
  const [showStaffModal, setShowStaffModal] = useState(false)
  const [newDate, setNewDate] = useState(new Date(appointment.appointment_time))
  // const [retryCount, setRetryCount] = useState(0) // Removed unused state
  const [currentStatus, setCurrentStatus] = useState(appointment.status)
  // Use prop staff if available, otherwise default to empty (or internal state if we kept it? No, removing internal state)
  const staff = propStaff.filter((s: any) => s.active)
  const [selectedStaff, setSelectedStaff] = useState("")
  const [serviceDetails, setServiceDetails] = useState<{
    description: string
    duration: number
    price: number
  } | null>(null)

  // Edit State
  const [showEditModal, setShowEditModal] = useState(false)

  // Use prop services as available services
  const availableServices = services
  const [editData, setEditData] = useState({
    customer_name: appointment.customer_name,
    phone_number: appointment.phone_number,
    service_type: appointment.service_type,
    notes: appointment.notes || '',
    emergency_request: !!appointment.emergency_request
  })

  React.useEffect(() => {
    // Derive service details from props instead of fetching
    if (appointment.service_type && services.length > 0) {
      const service = services.find((s: any) => s.name === appointment.service_type)
      if (service) {
        setServiceDetails({
          description: service.description || '',
          duration: service.duration,
          price: service.price
        })
      } else {
        setServiceDetails(null)
      }
    }
  }, [appointment.service_type, appointment.id, services])

  // Removed useEffect for fetchServices on showEditModal since we have services prop

  // Removed useEffect for fetchStaff since we have staff prop

  React.useEffect(() => {
    setCurrentStatus(appointment.status)
  }, [appointment.status])

  const handleConfirm = async (e?: React.MouseEvent) => {
    // Prevent event bubbling if triggered by click
    e?.preventDefault();
    e?.stopPropagation();

    if (isLoading) return;

    setIsLoading(true)
    try {
      await apiClient.updateAppointmentStatus(appointment.id, 'confirmed')
      setCurrentStatus('confirmed') // Optimistic UI update
      toast.success('Appointment confirmed and customer notified')
      onUpdate()
    } catch (error) {
      console.error('Error confirming appointment:', error)
      setCurrentStatus(appointment.status) // Revert on error

      await apiClient.logError(error, 'appointment_confirmation', {
        appointment_id: appointment.id,
        phone_number: appointment.phone_number
      })

      toast.error('Failed to confirm appointment')
    } finally {
      setIsLoading(false)
      // Remove retry logic to prevent loops
    }
  }

  const handleStartRepair = async (arg: boolean | React.MouseEvent | any = false) => {
    const bypassModal = typeof arg === 'boolean' ? arg : false;
    // If not bypassing modal (i.e. changing staff) and no staff selected, show error
    if (!bypassModal && !selectedStaff) {
      toast.error('Please select a staff member')
      return
    }

    setIsLoading(true)
    try {
      const updatePayload: any = {
        status: 'in_progress'
      };

      // Only update staff if we selected one (via modal)
      if (selectedStaff) {
        updatePayload.assigned_staff_id = selectedStaff;
      }

      await apiClient.updateAppointment(appointment.id, updatePayload)
      setCurrentStatus('in_progress') // Optimistic UI update
      toast.success('Repair started')
      setShowStaffModal(false)
      onUpdate()
    } catch (error) {
      console.error('Error starting repair:', error)
      setCurrentStatus(appointment.status) // Revert on error
      toast.error('Failed to start repair')
    } finally {
      setIsLoading(false)
    }
  }

  const handleUpdateDetails = async () => {
    setIsLoading(true)
    try {
      // Find the service name if they picked an ID from the dropdown
      const selectedService = availableServices.find(s => s.id === editData.service_type || s.name === editData.service_type)

      const payload = {
        ...editData,
        service_type: selectedService ? selectedService.id : editData.service_type
      }

      await apiClient.updateAppointment(appointment.id, payload)
      toast.success('Appointment updated')
      setShowEditModal(false)
      onUpdate()
    } catch (error) {
      console.error('Error updating appointment:', error)
      toast.error('Failed to update appointment')
    } finally {
      setIsLoading(false)
    }
  }

  const handleReschedule = async () => {
    const appointmentDate = new Date(newDate)
    const isWeekend = appointmentDate.getDay() === 0 || appointmentDate.getDay() === 6
    if (isWeekend) {
      toast.error('Please select a weekday (Monday-Friday)')
      return
    }

    setIsLoading(true)
    try {
      await apiClient.rescheduleAppointment(appointment.id, newDate.toISOString())
      toast.success('Appointment rescheduled and customer notified')
      setShowReschedule(false)
      onUpdate()
    } catch (error) {
      console.error('Error rescheduling appointment:', error)

      await apiClient.logError(error, 'appointment_reschedule', {
        appointment_id: appointment.id,
        phone_number: appointment.phone_number,
        new_time: newDate.toISOString()
      })

      toast.error('Failed to reschedule appointment')
    } finally {
      setIsLoading(false)
    }
  }

  // Helper functions for formatting date and time
  const formatDate = (dateString: string) => {
    try {
      if (!dateString) return 'No Date';
      return format(new Date(dateString), 'MMM dd, yyyy');
    } catch (e) {
      return 'Invalid Date';
    }
  };

  const formatTime = (dateString: string) => {
    try {
      if (!dateString) return 'No Time';
      return format(new Date(dateString), 'hh:mm a');
    } catch (e) {
      return 'Invalid Time';
    }
  };

  const getEndTime = (startTime: string, durationMins: number) => {
    const start = new Date(startTime);
    return new Date(start.getTime() + durationMins * 60000);
  };


  // Status color mapping
  const statusColors: { [key: string]: string } = {
    pending: 'bg-[#FDB80E] text-gray-900',
    confirmed: 'bg-green-600 text-white',
    in_progress: 'bg-blue-600 text-white',
    rescheduled: 'bg-purple-100 text-purple-800',
    cancelled: 'bg-gray-400 text-white',
    completed: 'bg-gray-800 text-white',
  };

  const getStatusDisplay = (status: string) => {
    return status.replace('_', ' ').split(' ').map(word =>
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6 transition-all duration-200 hover:shadow-lg">
      <div className="flex justify-between items-start mb-4 gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold text-gray-900 truncate">{appointment.customer_name}</h3>
            <button
              onClick={() => setShowEditModal(true)}
              className="p-1 text-gray-400 hover:text-blue-600 transition-colors flex-shrink-0"
              title="Edit Details"
            >
              <Edit2 className="h-4 w-4" />
            </button>
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300 truncate">{appointment.service_type}</p>
        </div>
        <span
          className={`px-3 py-1 text-xs font-medium rounded-full whitespace-nowrap flex-shrink-0 ${statusColors[currentStatus] || 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'}`}
        >
          {getStatusDisplay(currentStatus)}
        </span>
      </div>

      <div className="space-y-2 text-sm text-gray-700 mb-4">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-gray-600 dark:text-gray-400" />
          <p>{formatDate(appointment.appointment_time)}</p>
        </div>
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-gray-600 dark:text-gray-400" />
          <p>
            {formatTime(appointment.appointment_time)}
            {serviceDetails && ` - ${formatTime(getEndTime(appointment.appointment_time, serviceDetails.duration).toISOString())}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Phone className="h-4 w-4 text-gray-600 dark:text-gray-400" />
          <p>{appointment.phone_number}</p>
        </div>
        {serviceDetails && (
          <>
            <div className="flex items-center gap-2">
              <Tool className="h-4 w-4 text-gray-600 dark:text-gray-400" />
              <p>{serviceDetails.description} ({serviceDetails.duration} mins)</p>
            </div>
            <div className="flex items-center gap-2">
              <p className="font-semibold text-gray-900 dark:text-gray-100">{formatCurrency(serviceDetails.price)}</p>
            </div>
          </>
        )}
      </div>

      <div className="flex flex-col gap-3">
        {appointment.emergency_request && (
          <span className="px-3 py-1 text-xs font-medium bg-red-100 text-red-800 rounded-full flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            Emergency
          </span>
        )}
        <div className="flex gap-2">
          {currentStatus === 'pending' && (
            <>
              <button
                onClick={handleConfirm}
                disabled={isLoading}
                className="flex-1 px-4 py-2 text-sm font-bold uppercase tracking-wide text-gray-900 bg-[#FDB80E] rounded-md hover:bg-[#FDE047] disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
              >
                {isLoading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-900" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Processing...
                  </span>
                ) : (
                  'Confirm'
                )}
              </button>
              <button
                onClick={() => setShowReschedule(true)}
                disabled={isLoading}
                className="flex-1 px-4 py-2 text-sm font-bold uppercase tracking-wide text-gray-700 border-2 border-transparent hover:border-gray-300 rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Reschedule
              </button>
            </>
          )}
          {currentStatus === 'confirmed' && (
            <>
              <button
                onClick={() => {
                  if (appointment.assigned_staff_id) {
                    // Already assigned, just start
                    handleStartRepair(true);
                  } else {
                    // Not assigned, show modal
                    setShowStaffModal(true);
                  }
                }}
                disabled={isLoading}
                className="flex-1 px-4 py-2 text-sm font-bold uppercase tracking-wide text-white bg-[#B91C1C] rounded-md hover:bg-[#991B1B] disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
              >
                Start Repair
              </button>
              <button
                onClick={() => setShowReschedule(true)}
                disabled={isLoading}
                className="flex-1 px-4 py-2 text-sm font-bold uppercase tracking-wide text-gray-700 border-2 border-transparent hover:border-gray-300 rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Reschedule
              </button>
            </>
          )}
          {currentStatus === 'in_progress' && (
            <div className="text-sm text-gray-600 dark:text-gray-400 italic">
              {appointment.assigned_staff_id && staff.find(s => s.id === appointment.assigned_staff_id)?.name ? (
                <span>Assigned to: <strong>{staff.find(s => s.id === appointment.assigned_staff_id)?.name}</strong></span>
              ) : (
                <span>Repair in progress...</span>
              )}
            </div>
          )}
        </div>
      </div>

      {showReschedule && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
              Reschedule Appointment
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  New Appointment Time
                </label>
                <input
                  type="datetime-local"
                  value={format(newDate, "yyyy-MM-dd'T'HH:mm")}
                  onChange={(e) => setNewDate(new Date(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
              </div>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowReschedule(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleReschedule}
                  disabled={isLoading}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isLoading ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showStaffModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
              Assign Staff & Start Repair
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Select Staff Member
                </label>
                <select
                  value={selectedStaff}
                  onChange={(e) => setSelectedStaff(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                >
                  <option value="">-- Select a staff member --</option>
                  {staff.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.role})
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => { setShowStaffModal(false); setSelectedStaff(''); }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleStartRepair}
                  disabled={isLoading || !selectedStaff}
                  className="px-4 py-2 text-sm font-bold uppercase tracking-wide text-white bg-[#B91C1C] rounded-md hover:bg-[#991B1B] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isLoading ? 'Starting...' : 'Assign & Start'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showEditModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-lg shadow-xl">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <Edit2 className="h-5 w-5 text-blue-600" />
                Edit Appointment
              </h3>
              <button onClick={() => setShowEditModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-6 w-6" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Customer Name</label>
                  <input
                    type="text"
                    value={editData.customer_name}
                    onChange={(e) => setEditData({ ...editData, customer_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 text-gray-900 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Phone Number</label>
                  <input
                    type="text"
                    value={editData.phone_number}
                    onChange={(e) => setEditData({ ...editData, phone_number: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 text-gray-900 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Service Type</label>
                <select
                  value={editData.service_type}
                  onChange={(e) => setEditData({ ...editData, service_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 text-gray-900 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                >
                  {availableServices.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                  {!availableServices.some(s => s.name === editData.service_type || s.id === editData.service_type) && (
                    <option value={editData.service_type}>{editData.service_type}</option>
                  )}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Notes</label>
                <textarea
                  value={editData.notes}
                  onChange={(e) => setEditData({ ...editData, notes: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 text-gray-900 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="edit-emergency"
                  checked={editData.emergency_request}
                  onChange={(e) => setEditData({ ...editData, emergency_request: e.target.checked })}
                  className="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300 rounded"
                />
                <label htmlFor="edit-emergency" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Emergency Request
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <button
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md"
                >
                  Cancel
                </button>
                <button
                  onClick={handleUpdateDetails}
                  disabled={isLoading}
                  className="px-4 py-2 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-sm disabled:opacity-50"
                >
                  {isLoading ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}