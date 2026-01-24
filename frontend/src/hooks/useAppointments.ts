import { useState, useEffect, useCallback } from 'react'
import { apiClient, Appointment, Service, Staff } from '../lib/supabase'
import { addDays, startOfDay, endOfDay } from 'date-fns'

export interface Metrics {
  totalAppointments: number
  emergencyRequests: number
  completedToday: number
  customerSatisfaction: number
}

export function useAppointments() {
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [staff, setStaff] = useState<Staff[]>([])
  const [metrics, setMetrics] = useState<Metrics>({
    totalAppointments: 0,
    emergencyRequests: 0,
    completedToday: 0,
    customerSatisfaction: 98,
  })
  const [loading, setLoading] = useState(true)
  const [timeframe, setTimeframe] = useState<'24h' | '7d' | '30d'>('24h')

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const now = new Date()
      const start = startOfDay(
        timeframe === '24h'
          ? now
          : timeframe === '7d'
            ? addDays(now, -7)
            : addDays(now, -30)
      )

      const [appointmentsResult, servicesResult, staffResult] = await Promise.allSettled([
        apiClient.getAppointments(),
        apiClient.getServices(),
        apiClient.getStaff()
      ])

      let appointmentsData: Appointment[] = []
      let servicesData: Service[] = []
      let staffData: Staff[] = []

      if (appointmentsResult.status === 'fulfilled') {
        appointmentsData = appointmentsResult.value
      } else {
        console.error('Failed to fetch appointments:', appointmentsResult.reason)
      }

      if (servicesResult.status === 'fulfilled') {
        servicesData = servicesResult.value
      } else {
        console.error('Failed to fetch services:', servicesResult.reason)
      }

      const filteredAppointments = appointmentsData.filter(apt =>
        new Date(apt.appointment_time) >= start
      )

      const todayStart = startOfDay(now)
      const todayEnd = endOfDay(now)

      const calculatedMetrics = {
        totalAppointments: filteredAppointments.length,
        emergencyRequests: filteredAppointments.filter(a => a.emergency_request).length,
        completedToday: filteredAppointments.filter(
          a => a.status === 'completed' &&
            new Date(a.appointment_time) >= todayStart &&
            new Date(a.appointment_time) <= todayEnd
        ).length,
        customerSatisfaction: 98
      }

      setAppointments(filteredAppointments.sort((a, b) =>
        new Date(a.appointment_time).getTime() - new Date(b.appointment_time).getTime()
      ))
      setServices(servicesData.sort((a, b) => a.name.localeCompare(b.name)))
      setStaff(staffData)
      setMetrics(calculatedMetrics)
    } catch (error) {
      console.error('Error in data fetching:', error)
    } finally {
      setLoading(false)
    }
  }, [timeframe])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [fetchData])

  const refreshAppointments = () => {
    fetchData()
  }

  return {
    appointments,
    services,
    staff,
    metrics,
    loading,
    timeframe,
    setTimeframe,
    refreshAppointments
  }
}