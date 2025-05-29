import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { addDays, startOfDay, endOfDay } from 'date-fns'

export interface Appointment {
  id: string
  customer_name: string
  phone_number: string
  appointment_time: string
  service_type: string
  notes?: string
  status: string
  emergency_request?: boolean
}

export interface Service {
  id: string
  name: string
  description: string
  duration: number
  price: number
  is_emergency: boolean
  category: string
}

export interface Metrics {
  totalAppointments: number
  emergencyRequests: number
  completedToday: number
  customerSatisfaction: number
}

export function useAppointments() {
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [metrics, setMetrics] = useState<Metrics>({
    totalAppointments: 0,
    emergencyRequests: 0,
    completedToday: 0,
    customerSatisfaction: 98, // Placeholder until we implement ratings
  })
  const [loading, setLoading] = useState(true)
  const [timeframe, setTimeframe] = useState<'24h' | '7d' | '30d'>('24h')

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Get date range based on timeframe
        const now = new Date()
        const start = startOfDay(
          timeframe === '24h' 
            ? now 
            : timeframe === '7d' 
              ? addDays(now, -7) 
              : addDays(now, -30)
        )

        // Fetch appointments
        const { data: appointmentsData, error: appointmentsError } = await supabase
          .from('appointments')
          .select('*')
          .gte('appointment_time', start.toISOString())
          .order('appointment_time', { ascending: true })

        if (appointmentsError) throw appointmentsError

        // Fetch services
        const { data: servicesData, error: servicesError } = await supabase
          .from('services')
          .select('*')
          .order('name')

        if (servicesError) throw servicesError

        // Calculate metrics
        const todayStart = startOfDay(now)
        const todayEnd = endOfDay(now)

        const metrics = {
          totalAppointments: appointmentsData?.length || 0,
          emergencyRequests: appointmentsData?.filter(a => a.emergency_request).length || 0,
          completedToday: appointmentsData?.filter(
            a => a.status === 'completed' && 
            new Date(a.appointment_time) >= todayStart &&
            new Date(a.appointment_time) <= todayEnd
          ).length || 0,
          customerSatisfaction: 98 // Placeholder
        }

        setAppointments(appointmentsData || [])
        setServices(servicesData || [])
        setMetrics(metrics)
        setLoading(false)
      } catch (error) {
        console.error('Error fetching data:', error)
        setLoading(false)
      }
    }

    fetchData()

    // Subscribe to real-time changes
    const appointmentsSubscription = supabase
      .channel('appointments-changes')
      .on(
        'postgres_changes',
        { 
          event: '*', 
          schema: 'public', 
          table: 'appointments' 
        },
        fetchData
      )
      .subscribe()

    const servicesSubscription = supabase
      .channel('services-changes')
      .on(
        'postgres_changes',
        { 
          event: '*', 
          schema: 'public', 
          table: 'services' 
        },
        fetchData
      )
      .subscribe()

    return () => {
      appointmentsSubscription.unsubscribe()
      servicesSubscription.unsubscribe()
    }
  }, [timeframe])

  return { appointments, services, metrics, loading, timeframe, setTimeframe }
}