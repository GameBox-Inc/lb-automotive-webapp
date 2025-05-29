import React, { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { AppointmentCard } from '../components/AppointmentCard'
import { VoicePrompt } from '../components/VoicePrompt'
import { Calendar, Clock, Plus, X } from 'lucide-react'
import { format } from 'date-fns'
import toast from 'react-hot-toast'

interface Appointment {
  id: string
  customer_name: string
  phone_number: string
  appointment_time: string
  service_type: string
  notes: string
  status: string
  emergency_request?: boolean
}

interface Service {
  id: string
  name: string
  description: string
  duration: number
  price: number
  category: string
}

export function Appointments() {
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState('')
  const [newAppointment, setNewAppointment] = useState({
    customer_name: '',
    phone_number: '',
    appointment_time: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
    service_type: '',
    notes: '',
    emergency_request: false
  })

  useEffect(() => {
    fetchAppointments()
    fetchServices()
  }, [])

  async function fetchAppointments() {
    try {
      const { data, error } = await supabase
        .from('appointments')
        .select('*')
        .order('appointment_time', { ascending: true })

      if (error) throw error
      setAppointments(data || [])
    } catch (error) {
      console.error('Error fetching appointments:', error)
      toast.error('Failed to load appointments')
    } finally {
      setLoading(false)
    }
  }

  async function fetchServices() {
    try {
      const { data, error } = await supabase
        .from('services')
        .select('*')
        .order('category')
        .order('name')

      if (error) throw error
      setServices(data || [])
    } catch (error) {
      console.error('Error fetching services:', error)
      toast.error('Failed to load services')
    }
  }

  const handleAddAppointment = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const { error } = await supabase
        .from('appointments')
        .insert([{
          ...newAppointment,
          status: 'scheduled'
        }])

      if (error) throw error

      toast.success('Appointment created successfully')
      setShowAddModal(false)
      setNewAppointment({
        customer_name: '',
        phone_number: '',
        appointment_time: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
        service_type: '',
        notes: '',
        emergency_request: false
      })
      setSelectedCategory('')
      fetchAppointments()
    } catch (error) {
      console.error('Error creating appointment:', error)
      toast.error('Failed to create appointment')
    }
  }

  const servicesByCategory = services.reduce((acc, service) => {
    if (!acc[service.category]) {
      acc[service.category] = []
    }
    acc[service.category].push(service)
    return acc
  }, {} as Record<string, Service[]>)

  const categories = Object.keys(servicesByCategory)
  const selectedService = services.find(s => s.name === newAppointment.service_type)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Appointments</h1>
        <button 
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <Plus className="h-5 w-5 mr-2" />
          New Appointment
        </button>
      </div>

      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center space-x-4 mb-6">
          <div className="flex items-center text-gray-600">
            <Calendar className="h-5 w-5 mr-2" />
            <span>Filter by date</span>
          </div>
          <div className="flex items-center text-gray-600">
            <Clock className="h-5 w-5 mr-2" />
            <span>Filter by time</span>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-500">Loading appointments...</p>
          </div>
        ) : appointments.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500">No appointments found</p>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {appointments.map((appointment) => (
              <AppointmentCard 
                key={appointment.id} 
                appointment={appointment} 
                onUpdate={fetchAppointments}
              />
            ))}
          </div>
        )}
      </div>

      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium">New Appointment</h3>
              <button onClick={() => {
                setShowAddModal(false)
                setSelectedCategory('')
              }}>
                <X className="h-5 w-5 text-gray-500" />
              </button>
            </div>
            <form onSubmit={handleAddAppointment} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Customer Name
                </label>
                <input
                  type="text"
                  value={newAppointment.customer_name}
                  onChange={e => setNewAppointment({ ...newAppointment, customer_name: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Phone Number
                </label>
                <input
                  type="tel"
                  value={newAppointment.phone_number}
                  onChange={e => setNewAppointment({ ...newAppointment, phone_number: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Service Category
                </label>
                <select
                  value={selectedCategory}
                  onChange={e => {
                    setSelectedCategory(e.target.value)
                    setNewAppointment({ ...newAppointment, service_type: '' })
                  }}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  required
                >
                  <option value="">Select a category</option>
                  {categories.map(category => (
                    <option key={category} value={category}>
                      {category.charAt(0).toUpperCase() + category.slice(1)}
                    </option>
                  ))}
                </select>
              </div>
              {selectedCategory && (
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Service Type
                  </label>
                  <select
                    value={newAppointment.service_type}
                    onChange={e => setNewAppointment({ ...newAppointment, service_type: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                    required
                  >
                    <option value="">Select a service</option>
                    {servicesByCategory[selectedCategory]?.map(service => (
                      <option key={service.id} value={service.name}>
                        {service.name} - ${service.price} ({service.duration} min)
                      </option>
                    ))}
                  </select>
                  {selectedService && (
                    <p className="mt-2 text-sm text-gray-500">
                      {selectedService.description}
                    </p>
                  )}
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Appointment Time
                </label>
                <input
                  type="datetime-local"
                  value={newAppointment.appointment_time}
                  onChange={e => setNewAppointment({ ...newAppointment, appointment_time: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Notes
                </label>
                <textarea
                  value={newAppointment.notes}
                  onChange={e => setNewAppointment({ ...newAppointment, notes: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  rows={3}
                />
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="emergency_request"
                  checked={newAppointment.emergency_request}
                  onChange={e => setNewAppointment({ ...newAppointment, emergency_request: e.target.checked })}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="emergency_request" className="ml-2 block text-sm text-gray-900">
                  Emergency Request
                </label>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddModal(false)
                    setSelectedCategory('')
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-md"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                >
                  Create Appointment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <VoicePrompt onAppointmentCreated={fetchAppointments} />
    </div>
  )
}