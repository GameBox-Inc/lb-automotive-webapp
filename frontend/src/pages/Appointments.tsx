import React, { useId, useState, useEffect, startTransition } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { fetchServices, fetchStaff } from '../store/slices/shopSlice'
import { RootState } from '../store'
import { apiClient } from '../lib/supabase'
import { AppointmentCard } from '../components/AppointmentCard'
import { DailyTimeline } from '../components/DailyTimeline'
import { AppointmentCalendar } from '../components/AppointmentCalendar'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { SkeletonList, SkeletonCard } from '../components/Skeleton'
import { EmptyState } from '../components/EmptyState'
import { VoicePrompt } from '../components/VoicePrompt'
import { Dialog, DialogPanel, DialogTitle, Transition, TransitionChild } from '@headlessui/react';
import { Plus, Search, Calendar, Clock, X, Maximize2, Minimize2, RefreshCw } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import toast from 'react-hot-toast'
import { Appointment, Service, Customer } from '../types'
import { VEHICLE_MAKE_MODEL_OPTIONS, COMMON_COLORS } from '../constants/vehicleData'
import { isActiveAppointmentStatus } from '../constants/appointments'

export function Appointments() {
  const formId = useId()
  const navigate = useNavigate()
  const location = useLocation()
  const dispatch = useAppDispatch()
  const services = useAppSelector((state: RootState) => state.shop.services)
  const staff = useAppSelector((state: RootState) => state.shop.staff)
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<'card' | 'list' | 'calendar'>('list')
  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState('')

  // Filter State
  const [filterDate, setFilterDate] = useState('')
  const [filterStatus, setFilterStatus] = useState('all')
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')
  const [hideCompleted, setHideCompleted] = useState(true)

  // Customer Search State (selectedCustomerId used to save vehicle to profile)
  const [customerQuery, setCustomerQuery] = useState('')
  const [customerResults, setCustomerResults] = useState<Customer[]>([])
  const [showCustomerResults, setShowCustomerResults] = useState(false)
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null)

  // Availability State
  const [availableSlots, setAvailableSlots] = useState<string[]>([])
  const [checkingAvailability, setCheckingAvailability] = useState(false)
  const [selectedDate, setSelectedDate] = useState(format(new Date(), 'yyyy-MM-dd'))

  const isWallboardMode = location.pathname === '/wallboard/calendar'

  const [newAppointment, setNewAppointment] = useState({
    customer_name: '',
    phone_number: '',
    appointment_time: '',
    service_type: '',
    notes: '',
    emergency_request: false,
    vehicle_make: '',
    vehicle_model: '',
    vehicle_color: '',
    vehicle_year: new Date().getFullYear(),
  })

  useEffect(() => {
    fetchAppointments()
    // Load shop data (services/staff) into Redux if not already loaded
    if (services.length === 0) dispatch(fetchServices())
    if (staff.length === 0) dispatch(fetchStaff())
  }, [dispatch])

  // Wallboard: force calendar view and refresh periodically
  useEffect(() => {
    if (!isWallboardMode) return
    setViewMode('calendar')
    const interval = globalThis.setInterval(() => {
      fetchAppointments()
    }, 30000)
    return () => globalThis.clearInterval(interval)
    // Intentionally exclude fetchAppointments from deps to avoid re-registering the interval.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isWallboardMode])

  // Customer Search
  useEffect(() => {
    const searchCustomers = async () => {
      if (customerQuery.length > 2) {
        try {
          const results = await apiClient.searchCustomers(customerQuery)
          setCustomerResults(results)
          setShowCustomerResults(true)
        } catch (error) {
          console.error('Error searching customers:', error)
        }
      } else {
        setCustomerResults([])
        setShowCustomerResults(false)
      }
    }

    const debounce = setTimeout(searchCustomers, 300)
    return () => clearTimeout(debounce)
  }, [customerQuery])

  // Check Availability (service_type stores service id from dropdown)
  useEffect(() => {
    const checkAvailability = async () => {
      const service = services.find(s => s.id === newAppointment.service_type)
      if (selectedDate && service) {
        setCheckingAvailability(true)
        try {
          const slots = await apiClient.getAvailableSlots(selectedDate, service.id)
          setAvailableSlots(slots)
        } catch (error: unknown) {
          console.error("Error fetching availability", error)
          const msg = error && typeof error === 'object' && 'message' in error ? String((error as { message?: string }).message) : 'Failed to load available times'
          toast.error(msg)
          setAvailableSlots([])
        } finally {
          setCheckingAvailability(false)
        }
      } else {
        setAvailableSlots([])
      }
    }

    if (showAddModal) {
      checkAvailability()
    }
  }, [selectedDate, newAppointment.service_type, services, showAddModal])

  async function fetchAppointments() {
    try {
      const data = await apiClient.getAppointments()
      // Fix: Ensure emergency_request is always boolean if API returns undefined
      const sanitizedData = data.map(apt => ({
        ...apt,
        emergency_request: !!apt.emergency_request
      }))
      setAppointments(sanitizedData)
    } catch (error) {
      console.error('Error fetching appointments:', error)
      toast.error('Failed to load appointments')
    } finally {
      setLoading(false)
    }
  }

  const handleOpenCase = async (appointment: Appointment) => {
    try {
      // First, try to find an existing case for this appointment
      const cases = await apiClient.getCases();
      const existingCase = cases.find((c: any) => c.appointment_id === appointment.id);

      if (existingCase) {
        // Case already exists, navigate to it
        startTransition(() => {
          navigate(`/cases/${existingCase.id}`);
        });
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
          startTransition(() => {
            navigate(`/cases/${newCase.id}`);
          });
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

  const handleSelectCustomer = async (customer: Customer) => {
    setSelectedCustomerId(customer.id)
    setNewAppointment(prev => ({
      ...prev,
      customer_name: customer.name,
      phone_number: customer.phone
    }))
    setCustomerQuery('')
    setShowCustomerResults(false)
    // Pre-fill vehicle from customer profile when available
    try {
      const full = await apiClient.getCustomer(customer.id)
      if (full.vehicle_make || full.vehicle_model || full.vehicle_color || full.vehicle_year) {
        setNewAppointment(prev => ({
          ...prev,
          customer_name: customer.name,
          phone_number: customer.phone,
          vehicle_make: full.vehicle_make ?? prev.vehicle_make,
          vehicle_model: full.vehicle_model ?? prev.vehicle_model,
          vehicle_color: full.vehicle_color ?? prev.vehicle_color,
          vehicle_year: full.vehicle_year ?? prev.vehicle_year,
        }))
      }
    } catch {
      // Profile may not have vehicle fields yet
    }
  }

  const handleAddAppointment = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!newAppointment.appointment_time) {
      toast.error("Please select a time slot")
      return
    }

    const fullDateTime = `${selectedDate}T${newAppointment.appointment_time}`
    const payload = {
      ...newAppointment,
      appointment_time: fullDateTime,
      ...(selectedService && { service_id: selectedService.id }),
    }

    try {
      await apiClient.createAppointment(payload)

      // Save vehicle to customer profile only if they don't already have one
      if (selectedCustomerId && (newAppointment.vehicle_make || newAppointment.vehicle_model || newAppointment.vehicle_color || newAppointment.vehicle_year)) {
        try {
          const existing = await apiClient.getCustomer(selectedCustomerId)
          const hasExistingVehicle =
            !!(existing.vehicle_make || existing.vehicle_model || existing.vehicle_color || existing.vehicle_year)

          if (!hasExistingVehicle) {
            await apiClient.updateCustomer(selectedCustomerId, {
              name: existing.name,
              phone: existing.phone,
              email: existing.email,
              vehicle_make: newAppointment.vehicle_make || undefined,
              vehicle_model: newAppointment.vehicle_model || undefined,
              vehicle_color: newAppointment.vehicle_color || undefined,
              vehicle_year: newAppointment.vehicle_year || undefined,
            })
          }
        } catch (err) {
          console.warn('Could not update customer vehicle profile', err)
        }
      }

      toast.success('Appointment created successfully')
      setShowAddModal(false)
      resetForm()
      fetchAppointments()
    } catch (error) {
      console.error('Error creating appointment:', error)
      const message = error instanceof Error ? error.message : 'Failed to create appointment'
      toast.error(message)
    }
  }

  const resetForm = () => {
    setSelectedCustomerId(null)
    setNewAppointment({
      customer_name: '',
      phone_number: '',
      appointment_time: '',
      service_type: '',
      notes: '',
      emergency_request: false,
      vehicle_make: '',
      vehicle_model: '',
      vehicle_color: '',
      vehicle_year: new Date().getFullYear(),
    })
    setSelectedCategory('')
    setCustomerQuery('')
  }

  const servicesByCategory = services.reduce((acc, service) => {
    const category = service?.category ?? 'general';
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(service);
    return acc;
  }, {} as Record<string, Service[]>)

  const categories = Object.keys(servicesByCategory).sort()
  const selectedService = services.find(s => s.id === newAppointment.service_type)

  const filteredAppointments = appointments
    .filter(apt => isActiveAppointmentStatus(apt.status))
    .filter(apt => {
      const matchDate = filterDate ? apt.appointment_time.startsWith(filterDate) : true;
      const matchStatus = filterStatus === 'all' ? true : apt.status === filterStatus;
      const matchCompleted = hideCompleted ? apt.status !== 'completed' : true;
      return matchDate && matchStatus && matchCompleted;
    })
    .sort((a, b) => {
    const dateA = new Date(a.appointment_time).getTime();
    const dateB = new Date(b.appointment_time).getTime();
    return sortOrder === 'desc' ? dateB - dateA : dateA - dateB;
  });

  return (
    <div className={isWallboardMode ? 'space-y-4' : 'space-y-6'}>
      {isWallboardMode && (
        <div className="flex items-center justify-between bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200/50 dark:border-gray-700/50 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-50 dark:bg-indigo-900/30">
              <Calendar className="h-5 w-5 text-indigo-600 dark:text-indigo-300" />
            </div>
            <div>
              <div className="text-sm font-semibold text-gray-900 dark:text-white">Shop Calendar (Live)</div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Auto-refreshing every 30 seconds</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => fetchAppointments()}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-700 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
              title="Refresh now"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
            <button
              type="button"
              onClick={() => navigate('/appointments')}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-lb-red-primary text-white text-sm font-medium hover:opacity-95"
              title="Exit wallboard"
            >
              <Minimize2 className="h-4 w-4" />
              Exit
            </button>
          </div>
        </div>
      )}

      {/* Enhanced Header Section */}
      {!isWallboardMode && (
        <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-md sticky top-0 z-20 p-4 rounded-2xl shadow-sm border border-gray-200/50 dark:border-gray-700/50 transition-all duration-200">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">

          {/* Title & Count */}
          <div>
            <div className="flex items-center gap-3">
              <span className="px-3 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                {filteredAppointments.length} Total
              </span>
            </div>
          </div>

          {/* Actions - Right Side */}
          <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">

            {/* New Appointment Button */}
            <button
              onClick={() => setShowAddModal(true)}
              className="w-full sm:w-auto inline-flex items-center justify-center px-5 py-2.5 rounded-xl text-sm font-medium text-white shadow-lg shadow-indigo-500/20 bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 transform hover:-translate-y-0.5 transition-all duration-200"
            >
              <Plus className="h-5 w-5 mr-2" />
              New Appointment
            </button>

            {viewMode === 'calendar' && (
              <button
                type="button"
                onClick={() => navigate('/wallboard/calendar')}
                className="w-full sm:w-auto inline-flex items-center justify-center px-5 py-2.5 rounded-xl text-sm font-medium text-gray-900 dark:text-white bg-white/90 dark:bg-gray-700/70 border border-gray-200/70 dark:border-gray-600/70 hover:bg-white dark:hover:bg-gray-700 transition-colors"
                title="Maximize calendar for shop monitor"
              >
                <Maximize2 className="h-5 w-5 mr-2" />
                Maximize
              </button>
            )}
          </div>
        </div>

        {/* Filters Divider */}
        <div className="h-px bg-gray-200 dark:bg-gray-700 my-4" />

        {/* Filter Bar */}
        <div className="flex flex-col lg:flex-row items-center justify-between gap-4">

          {/* Inputs Group */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full lg:w-auto overflow-x-auto pb-1 sm:pb-0">

            {/* Date Filter */}
            <div className={`relative group flex items-center transition-all duration-200 ${filterDate ? 'ring-2 ring-indigo-500/20 rounded-lg' : ''}`}>
              <div className="absolute left-3 text-gray-400 group-focus-within:text-indigo-500 pointer-events-none">
                <Calendar className="h-4 w-4" />
              </div>
              <input
                type="date"
                value={filterDate}
                onChange={(e) => setFilterDate(e.target.value)}
                className="pl-9 pr-4 py-2 w-full sm:w-auto bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded-xl text-sm text-gray-700 dark:text-gray-200 focus:ring-2 focus:ring-lb-red-primary/50 focus:border-lb-red-primary transition-all hover:bg-white dark:hover:bg-gray-800"
              />
            </div>

            {/* Status Filter */}
            <div className={`relative group flex items-center transition-all duration-200 ${filterStatus !== 'all' ? 'ring-2 ring-indigo-500/20 rounded-lg' : ''}`}>
              <div className="absolute left-3 text-gray-400 group-focus-within:text-indigo-500 pointer-events-none">
                <Clock className="h-4 w-4" />
              </div>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="pl-9 pr-8 py-2 w-full sm:w-auto bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded-xl text-sm text-gray-700 dark:text-gray-200 focus:ring-2 focus:ring-lb-red-primary/50 focus:border-lb-red-primary transition-all hover:bg-white dark:hover:bg-gray-800 appearance-none cursor-pointer"
              >
                <option value="all">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="confirmed">Confirmed</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
              <div className="absolute right-3 text-gray-400 pointer-events-none">
                <svg className="h-4 w-4 fill-current" viewBox="0 0 20 20"><path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" /></svg>
              </div>
            </div>

            {/* Sort Toggle */}
            <button
              onClick={() => setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
              className="px-3 py-2 flex items-center bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded-xl text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-white dark:hover:bg-gray-800 transition-colors whitespace-nowrap"
            >
              {sortOrder === 'desc' ? 'Recent First' : 'Oldest First'}
              <svg className={`ml-1.5 h-4 w-4 transform transition-transform ${sortOrder === 'desc' ? '' : 'rotate-180'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Hide Completed Toggle */}
            <button
              onClick={() => setHideCompleted(prev => !prev)}
              className={`px-3 py-2 flex items-center border rounded-xl text-sm font-medium transition-colors whitespace-nowrap ${hideCompleted
                ? 'bg-indigo-50 border-indigo-200 text-indigo-700 dark:bg-indigo-900/30 dark:border-indigo-800 dark:text-indigo-300'
                : 'bg-gray-50 border-gray-200 text-gray-700 dark:bg-gray-900/50 dark:border-gray-700 dark:text-gray-200 hover:bg-white dark:hover:bg-gray-800'}`}
            >
              {hideCompleted ? 'Hidden: Completed' : 'Showing: Completed'}
            </button>

            {/* Clear Filters */}
            {(filterDate || filterStatus !== 'all' || !hideCompleted || sortOrder === 'asc') && (
              <button
                onClick={() => {
                  setFilterDate('');
                  setFilterStatus('all');
                  setHideCompleted(true);
                  setSortOrder('desc');
                }}
                className="px-3 py-2 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-colors flex items-center justify-center"
              >
                <X className="h-4 w-4 mr-1.5" />
                Clear
              </button>
            )}
          </div>

          {/* View Toggles */}
          <div className="bg-gray-100/50 dark:bg-gray-700/50 p-1 rounded-xl flex items-center border border-gray-200 dark:border-gray-600">
            <button
              onClick={() => setViewMode('card')}
              className={`flex items-center px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${viewMode === 'card'
                ? 'bg-white dark:bg-gray-600 text-indigo-600 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-200/50 dark:hover:bg-gray-600/50'
                }`}
            >
              <div className="mr-1.5">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="7" height="7" x="3" y="3" rx="1" /><rect width="7" height="7" x="14" y="3" rx="1" /><rect width="7" height="7" x="14" y="14" rx="1" /><rect width="7" height="7" x="3" y="14" rx="1" /></svg>
              </div>
              Grid
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`flex items-center px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${viewMode === 'list'
                ? 'bg-white dark:bg-gray-600 text-indigo-600 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-200/50 dark:hover:bg-gray-600/50'
                }`}
            >
              <div className="mr-1.5">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" x2="21" y1="6" y2="6" /><line x1="3" x2="21" y1="12" y2="12" /><line x1="3" x2="21" y1="18" y2="18" /></svg>
              </div>
              List
            </button>
            <button
              onClick={() => setViewMode('calendar')}
              className={`flex items-center px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${viewMode === 'calendar'
                ? 'bg-white dark:bg-gray-600 text-indigo-600 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-200/50 dark:hover:bg-gray-600/50'
                }`}
            >
              <div className="mr-1.5">
                <Calendar className="h-4 w-4" />
              </div>
              Calendar
            </button>
          </div>
        </div>
      </div>
      )}

      {loading ? (
        <div className="space-y-4">
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
          <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden p-4">
            <SkeletonList rows={5} />
          </div>
        </div>
      ) : filteredAppointments.length === 0 ? (
        <EmptyState
          icon={<Calendar className="h-7 w-7" />}
          title="No appointments found"
          description="Try adjusting filters or add a new appointment."
          action={apiClient.getStoredUser()?.is_admin && (
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-lb-red-primary rounded-md hover:bg-lb-red-light"
            >
              Add Appointment
            </button>
          )}
        />
      ) : (
        <>
          {viewMode === 'card' && (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {filteredAppointments.map((appointment) => (
                <AppointmentCard
                  key={appointment.id}
                  appointment={appointment}
                  onUpdate={fetchAppointments}
                  services={services}
                  staff={staff}
                />
              ))}
            </div>
          )}

          {viewMode === 'list' && (
            <div className="bg-white dark:bg-gray-800 shadow rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-gray-900">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Customer</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Service</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Date & Time</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Status</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                    {filteredAppointments.map((appointment) => (
                      <tr key={appointment.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900 dark:text-white">{appointment.customer_name}</div>
                          <div className="text-sm text-gray-500 dark:text-gray-400">{appointment.phone_number}</div>
                          {appointment.emergency_request && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                              Emergency
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900 dark:text-white">{appointment.service_type}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900 dark:text-white">
                            {format(new Date(appointment.appointment_time), 'MMM dd, yyyy')}
                          </div>
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {format(new Date(appointment.appointment_time), 'hh:mm a')}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2.5 py-0.5 inline-flex text-xs leading-5 font-semibold rounded-full
                          ${appointment.status === 'completed' ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300' :
                              appointment.status === 'in_progress' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300' :
                                appointment.status === 'confirmed' ? 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300' :
                                  appointment.status === 'pending' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300' :
                                    appointment.status === 'cancelled' ? 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300' :
                                      'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'}`}>
                            {appointment.status === 'in_progress' ? 'In Progress' :
                              appointment.status.charAt(0).toUpperCase() + appointment.status.slice(1)}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          <button
                            onClick={() => handleOpenCase(appointment)}
                            className="text-indigo-600 hover:text-indigo-900 dark:text-indigo-400 dark:hover:text-indigo-300"
                          >
                            Open Case
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {viewMode === 'calendar' && (
            <div className="space-y-6">
              <AppointmentCalendar
                appointments={filteredAppointments}
                services={services}
                onDateClick={(date) => setFilterDate(format(date, 'yyyy-MM-dd'))}
              />
              <DailyTimeline
                appointments={filteredAppointments}
                services={services}
                selectedDate={filterDate ? parseISO(filterDate + 'T12:00:00') : undefined}
                onAppointmentClick={handleOpenCase}
              />
            </div>
          )}
        </>
      )}

      <Transition show={showAddModal}>
        <Dialog
          open={showAddModal}
          onClose={() => {
            setShowAddModal(false)
            resetForm()
          }}
          className="relative z-50"
        >
          <TransitionChild
            enter="ease-out duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50" aria-hidden="true" />
          </TransitionChild>
          <div className="fixed inset-0 flex items-center justify-center p-4">
            <TransitionChild
              enter="ease-out duration-200"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-150"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <DialogPanel className="bg-white dark:bg-gray-800 p-6 rounded-lg w-full max-w-md max-h-[90vh] overflow-y-auto shadow-xl">
                <div className="flex justify-between items-center mb-4">
                  <DialogTitle className="text-lg font-medium text-gray-900 dark:text-white">New Appointment</DialogTitle>
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddModal(false)
                      resetForm()
                    }}
                    className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                <form onSubmit={handleAddAppointment} className="space-y-4">
              <div className="relative">
                <label htmlFor={`${formId}-customer`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Customer
                </label>
                <div className="mt-1 relative">
                  <div className="flex">
                    <input
                      id={`${formId}-customer`}
                      type="text"
                      placeholder="Search or enter name..."
                      value={newAppointment.customer_name}
                      onChange={(e) => {
                        setNewAppointment({ ...newAppointment, customer_name: e.target.value })
                        setCustomerQuery(e.target.value)
                      }}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                      required
                    />
                    <div className="absolute right-3 top-2.5 text-gray-400">
                      <Search className="h-4 w-4" />
                    </div>
                  </div>
                </div>
                {showCustomerResults && customerResults.length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-white dark:bg-gray-700 shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none sm:text-sm">
                    {customerResults.map((customer) => (
                      <button
                        key={customer.id}
                        type="button"
                        onClick={() => handleSelectCustomer(customer)}
                        className="w-full text-left cursor-default select-none relative py-2 pl-3 pr-9 hover:bg-gray-100 dark:hover:bg-gray-600 text-gray-900 dark:text-white"
                      >
                        <span className="block truncate font-medium">{customer.name}</span>
                        <span className="block truncate text-xs text-gray-500 dark:text-gray-400">{customer.phone}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <label htmlFor={`${formId}-phone`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Phone Number
                </label>
                <input
                  id={`${formId}-phone`}
                  type="tel"
                  value={newAppointment.phone_number}
                  onChange={e => setNewAppointment({ ...newAppointment, phone_number: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                  required
                />
              </div>

              <div>
                <label htmlFor={`${formId}-category`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Service Category
                </label>
                <select
                  id={`${formId}-category`}
                  value={selectedCategory}
                  onChange={e => {
                    setSelectedCategory(e.target.value)
                    setNewAppointment({ ...newAppointment, service_type: '' })
                  }}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white"
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
                  <label htmlFor={`${formId}-service`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Service Type
                  </label>
                  <select
                    id={`${formId}-service`}
                    value={newAppointment.service_type}
                    onChange={e => setNewAppointment({ ...newAppointment, service_type: e.target.value, appointment_time: '' })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    required
                  >
                    <option value="">Select a service</option>
                    {servicesByCategory[selectedCategory]?.map(service => (
                      <option key={service.id} value={service.id}>
                        {service.name} - ${service.price} ({service.duration} min)
                      </option>
                    ))}
                  </select>
                  {selectedService && (
                    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                      {selectedService.description}
                    </p>
                  )}
                </div>
              )}

              <div>
                <label htmlFor={`${formId}-date`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Date
                </label>
                <input
                  id={`${formId}-date`}
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  min={format(new Date(), 'yyyy-MM-dd')}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                  required
                />
              </div>

              {selectedService && (
                <div role="group" aria-labelledby="available-times-heading">
                  <p id="available-times-heading" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Available Times
                  </p>
                  {checkingAvailability ? (
                    <div className="flex items-center text-sm text-gray-500 dark:text-gray-400">
                      <LoadingSpinner size="sm" className="mr-2" />
                      Checking availability...
                    </div>
                  ) : availableSlots.length > 0 ? (
                    <div className="grid grid-cols-4 gap-2">
                      {availableSlots.map(time => (
                        <button
                          key={time}
                          type="button"
                          onClick={() => setNewAppointment(prev => ({ ...prev, appointment_time: time }))}
                          className={`px-2 py-1 text-sm border rounded hover:bg-blue-50 dark:hover:bg-blue-900 ${newAppointment.appointment_time === time
                            ? 'bg-lb-red-primary text-white border-lb-red-primary'
                            : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-600'
                            }`}
                        >
                          {format(parseISO(`${selectedDate}T${time}`), 'hh:mm a')}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-red-500 dark:text-red-400">
                      No slots available for this date.
                      {selectedDate && (
                        <> {format(parseISO(selectedDate), 'EEEE (M/d)')} may be closed or have no staff scheduled. Check <Link to="/admin/ivr" className="underline font-medium">Admin → IVR → Configuration (Business Hours)</Link> and <Link to="/admin/staff" className="underline font-medium">Admin → Staff (Schedules)</Link>.</>
                      )}
                      {!selectedDate && ' Check staff schedules.'}
                    </p>
                  )}
                </div>
              )}

              {/* Optional Vehicle Details (dropdowns; pre-filled from customer profile when set) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label htmlFor={`${formId}-vmake`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Vehicle Make (optional)
                  </label>
                  <select
                    id={`${formId}-vmake`}
                    value={newAppointment.vehicle_make}
                    onChange={e => setNewAppointment({ ...newAppointment, vehicle_make: e.target.value, vehicle_model: '' })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                  >
                    <option value="">Select make</option>
                    {VEHICLE_MAKE_MODEL_OPTIONS.map(opt => (
                      <option key={opt.make} value={opt.make}>{opt.make}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor={`${formId}-vmodel`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Vehicle Model (optional)
                  </label>
                  <select
                    id={`${formId}-vmodel`}
                    value={newAppointment.vehicle_model}
                    onChange={e => setNewAppointment({ ...newAppointment, vehicle_model: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    disabled={!newAppointment.vehicle_make}
                  >
                    <option value="">Select model</option>
                    {VEHICLE_MAKE_MODEL_OPTIONS.find(m => m.make === newAppointment.vehicle_make)?.models.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label htmlFor={`${formId}-vcolor`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Vehicle Color (optional)
                  </label>
                  <select
                    id={`${formId}-vcolor`}
                    value={newAppointment.vehicle_color}
                    onChange={e => setNewAppointment({ ...newAppointment, vehicle_color: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                  >
                    <option value="">Select color</option>
                    {COMMON_COLORS.map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor={`${formId}-vyear`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Vehicle Year (optional)
                  </label>
                  <select
                    id={`${formId}-vyear`}
                    value={newAppointment.vehicle_year ?? ''}
                    onChange={e => setNewAppointment({ ...newAppointment, vehicle_year: Number(e.target.value) || new Date().getFullYear() })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                  >
                    <option value="">Select year</option>
                    {Array.from({ length: 32 }, (_, i) => new Date().getFullYear() + 1 - i).map(y => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label htmlFor={`${formId}-notes`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Notes
                </label>
                <textarea
                  id={`${formId}-notes`}
                  value={newAppointment.notes}
                  onChange={e => setNewAppointment({ ...newAppointment, notes: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                  rows={3}
                />
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id={`${formId}-emergency`}
                  checked={newAppointment.emergency_request}
                  onChange={e => setNewAppointment({ ...newAppointment, emergency_request: e.target.checked })}
                  className="h-4 w-4 text-lb-red-primary focus:ring-lb-red-primary border-gray-300 rounded dark:bg-gray-700 dark:border-gray-600"
                />
                <label htmlFor={`${formId}-emergency`} className="ml-2 block text-sm text-gray-900 dark:text-white">
                  Emergency Request
                </label>
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddModal(false)
                    resetForm()
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm font-medium text-white bg-lb-red-primary rounded-md hover:bg-lb-red-light disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Create Appointment
                </button>
              </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </Dialog>
      </Transition>

      <VoicePrompt onAppointmentCreated={fetchAppointments} />
    </div>
  )
}