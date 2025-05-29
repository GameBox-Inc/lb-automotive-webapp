import React, { useState } from 'react'
import { format } from 'date-fns'
import { Calendar, Clock, Phone, PenTool as Tool, User, AlertCircle, DollarSign } from 'lucide-react'
import toast from 'react-hot-toast'
import { supabase } from '../lib/supabase'

interface AppointmentCardProps {
  appointment: {
    id: string
    customer_name: string
    phone_number: string
    appointment_time: string
    service_type: string
    status: string
    emergency_request?: boolean
  }
  onUpdate: () => void
}

export const AppointmentCard: React.FC<AppointmentCardProps> = ({ appointment, onUpdate }) => {
  const [isLoading, setIsLoading] = useState(false)
  const [showReschedule, setShowReschedule] = useState(false)
  const [newDate, setNewDate] = useState(new Date(appointment.appointment_time))
  const [retryCount, setRetryCount] = useState(0)
  const [serviceDetails, setServiceDetails] = useState<{
    description: string
    duration: number
    price: number
  } | null>(null)

  React.useEffect(() => {
    const fetchServiceDetails = async () => {
      try {
        const { data, error } = await supabase
          .from('services')
          .select('description, duration, price')
          .eq('name', appointment.service_type)
          .maybeSingle()

        if (error) {
          if (error.message.includes('no rows')) {
            // Service not found, set details to null
            setServiceDetails(null)
            return
          }
          throw error
        }

        setServiceDetails(data)
      } catch (error) {
        console.error('Error fetching service details:', error)
        
        // Log the error to the error_logs table
        await supabase.from('error_logs').insert([{
          error_message: error.message,
          error_stack: error.stack,
          context: 'fetch_service_details',
          metadata: {
            service_type: appointment.service_type,
            appointment_id: appointment.id
          }
        }])
      }
    }

    if (appointment.service_type) {
      fetchServiceDetails()
    }
  }, [appointment.service_type, appointment.id])

  const handleConfirm = async () => {
    setIsLoading(true)
    try {
      await supabase
        .from('appointments')
        .update({ status: 'confirmed' })
        .eq('id', appointment.id)

      const response = await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/twilio-webhook`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${import.meta.env.VITE_SUPABASE_ANON_KEY}`
        },
        body: JSON.stringify({
          to: appointment.phone_number,
          message: `Your appointment at LB Automotive has been confirmed for ${format(
            new Date(appointment.appointment_time),
            'PPp'
          )}. Thank you for choosing our service!`
        }),
      })

      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || 'Failed to send SMS')
      }

      toast.success('Appointment confirmed')
      onUpdate()
    } catch (error) {
      console.error('Error confirming appointment:', error)
      
      if (retryCount === 0) {
        setRetryCount(1)
        handleConfirm()
        return
      }

      await supabase.from('error_logs').insert([{
        error_message: error.message,
        error_stack: error.stack,
        context: 'appointment_confirmation',
        metadata: {
          appointment_id: appointment.id,
          phone_number: appointment.phone_number
        }
      }])

      toast.error('Failed to confirm appointment')
    } finally {
      setIsLoading(false)
      setRetryCount(0)
    }
  }

  const handleReschedule = async () => {
    const appointmentDate = new Date(newDate)
    const isWeekend = appointmentDate.getDay() === 0 || appointmentDate.getDay() === 6
    const hour = appointmentDate.getHours()
    const isBusinessHours = hour >= 8 && hour < 18

    if (isWeekend) {
      toast.error('Please select a weekday (Monday-Friday)')
      return
    }

    if (!isBusinessHours) {
      toast.error('Please select a time between 8 AM and 6 PM')
      return
    }

    setIsLoading(true)
    try {
      await supabase
        .from('appointments')
        .update({ 
          appointment_time: newDate.toISOString(),
          status: 'rescheduled'
        })
        .eq('id', appointment.id)

      const response = await fetch(`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/twilio-webhook`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${import.meta.env.VITE_SUPABASE_ANON_KEY}`
        },
        body: JSON.stringify({
          to: appointment.phone_number,
          message: `Your appointment at LB Automotive has been rescheduled to ${format(
            newDate,
            'PPp'
          )}. Please contact us if you need to make any changes.`
        }),
      })

      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || 'Failed to send SMS')
      }

      toast.success('Appointment rescheduled')
      setShowReschedule(false)
      onUpdate()
    } catch (error) {
      console.error('Error rescheduling appointment:', error)
      
      await supabase.from('error_logs').insert([{
        error_message: error.message,
        error_stack: error.stack,
        context: 'appointment_reschedule',
        metadata: {
          appointment_id: appointment.id,
          phone_number: appointment.phone_number,
          new_time: newDate.toISOString()
        }
      }])

      toast.error('Failed to reschedule appointment')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6 transition-all duration-200 hover:shadow-lg">
      <div className="flex items-start justify-between">
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <User className="h-5 w-5 text-gray-400" />
            <p className="text-lg font-medium text-gray-900">{appointment.customer_name}</p>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-gray-400" />
            <p className="text-gray-600">
              {format(new Date(appointment.appointment_time), 'PPp')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Tool className="h-5 w-5 text-gray-400" />
            <div>
              <p className="text-gray-600">{appointment.service_type}</p>
              {serviceDetails ? (
                <div className="mt-1 text-sm text-gray-500">
                  <p className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {serviceDetails.duration} mins
                  </p>
                  <p className="flex items-center gap-1">
                    <DollarSign className="h-4 w-4" />
                    ${serviceDetails.price}
                  </p>
                  <p className="mt-1">{serviceDetails.description}</p>
                </div>
              ) : (
                <p className="mt-1 text-sm text-gray-500 italic">Service details not available</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Phone className="h-5 w-5 text-gray-400" />
            <p className="text-gray-600">{appointment.phone_number}</p>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          {appointment.emergency_request && (
            <span className="px-3 py-1 text-xs font-medium bg-red-100 text-red-800 rounded-full flex items-center gap-1">
              <AlertCircle className="h-3 w-3" />
              Emergency
            </span>
          )}
          <span
            className={`px-3 py-1 text-xs font-medium rounded-full ${
              appointment.status === 'confirmed'
                ? 'bg-green-100 text-green-800'
                : appointment.status === 'rescheduled'
                ? 'bg-yellow-100 text-yellow-800'
                : 'bg-gray-100 text-gray-800'
            }`}
          >
            {appointment.status}
          </span>
          <button
            onClick={handleConfirm}
            disabled={isLoading || appointment.status === 'confirmed'}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Confirming...
              </span>
            ) : (
              'Confirm'
            )}
          </button>
          <button
            onClick={() => setShowReschedule(true)}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-blue-600 border border-blue-600 rounded-md hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Reschedule
          </button>
        </div>
      </div>

      {showReschedule && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Reschedule Appointment
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  New Appointment Time
                </label>
                <input
                  type="datetime-local"
                  value={format(newDate, "yyyy-MM-dd'T'HH:mm")}
                  onChange={(e) => setNewDate(new Date(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowReschedule(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-md transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleReschedule}
                  disabled={isLoading}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isLoading ? (
                    <span className="flex items-center justify-center">
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Saving...
                    </span>
                  ) : (
                    'Save Changes'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}