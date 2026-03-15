import React, { useState, startTransition } from 'react'
import { Calendar, PenTool as Tool, User, BarChart3, AlertCircle, Wrench } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

import { LoadingSpinner } from '../components/LoadingSpinner'
import { SkeletonCard, Skeleton } from '../components/Skeleton'
import { ReportModal } from '../components/ReportModal'
import { useAppointments } from '../hooks/useAppointments'
import { apiClient } from '../lib/supabase'
import { formatNumber } from '../utils/format'
import { DailyTimeline } from '../components/DailyTimeline'
import { isActiveAppointmentStatus } from '../constants/appointments'
import type { Appointment } from '../lib/supabase'

export function Dashboard() {
  const timeframeId = React.useId()
  const navigate = useNavigate()
  const {
    appointments,
    metrics,
    services,
    loading,
    timeframe,
    setTimeframe
  } = useAppointments()

  const [showReports, setShowReports] = useState(false)

  const activeAppointments = appointments.filter((apt) => isActiveAppointmentStatus(apt.status))
  const todayAppointments = activeAppointments.filter(
    (apt) => new Date(apt.appointment_time).toDateString() === new Date().toDateString()
  )

  const handleOpenCase = async (appointment: Appointment) => {
    try {
      const cases = await apiClient.getCases()
      const existingCase = cases.find((c: { appointment_id?: string }) => c.appointment_id === appointment.id)
      if (existingCase) {
        startTransition(() => navigate(`/cases/${existingCase.id}`))
        return
      }
      try {
        const newCase = await apiClient.createCase({
          appointment_id: appointment.id,
          customer_name: appointment.customer_name,
          phone_number: appointment.phone_number,
          service_type: appointment.service_type,
          status: 'diagnosing',
        })
        if (newCase?.id) {
          startTransition(() => navigate(`/cases/${newCase.id}`))
        } else {
          toast.error('Failed to create case')
        }
      } catch {
        toast.error('Failed to create case')
      }
    } catch {
      toast.error('Failed to open repair details')
    }
  }

  const MetricCard = ({ title, value, icon }: { title: string, value: string | number, icon: React.ReactElement }) => (
    <div className="card group p-6 cursor-pointer hover:-translate-y-2 hover:scale-105 dark:bg-gray-800 dark:border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide">{title}</p>
          <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2 transition-all duration-300 group-hover:scale-110">{value}</p>
        </div>
        <div className="p-4 bg-gradient-to-br from-lb-red-primary to-lb-red-dark dark:from-lb-red-primary dark:to-lb-red-dark rounded-2xl shadow-lg group-hover:shadow-xl group-hover:scale-110 transition-all duration-300">
          {React.cloneElement(icon, { className: 'h-7 w-7 text-white' })}
        </div>
      </div>
      <div className="mt-3 h-1 bg-gradient-to-r from-lb-red-primary to-lb-yellow rounded-full transform scale-x-0 group-hover:scale-x-100 transition-transform duration-300 origin-left"></div>
    </div>
  )

  if (loading) {
    return (
      <div className="space-y-6 fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <Skeleton className="h-8 w-48" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
        <div className="mt-8 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
          <Skeleton className="h-5 w-32 mb-4" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Dashboard Overview</h1>

        <div className="flex items-center gap-2 sm:gap-4 overflow-x-auto pb-2 sm:pb-0">
          {apiClient.getStoredUser()?.staff_id && (
            <Link
              to="/repairs"
              className="inline-flex items-center px-4 py-2 border border-lb-red-primary shadow-sm text-sm font-medium rounded-md text-white bg-lb-red-primary hover:bg-lb-red-light transition-colors"
            >
              <Wrench className="h-4 w-4 mr-2" />
              My Repairs
            </Link>
          )}

          {apiClient.getStoredUser()?.is_admin && (
            <button
              onClick={() => setShowReports(true)}
              className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600 dark:hover:bg-gray-600 whitespace-nowrap"
            >
              <BarChart3 className="h-4 w-4 mr-2" />
              Reports
            </button>
          )}

          <label htmlFor={timeframeId} className="sr-only">Time range</label>
          <select
            id={timeframeId}
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value as any)}
            className="block rounded-md border-gray-300 shadow-sm focus:border-lb-red-primary focus:ring-lb-red-primary sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white bg-white w-40 p-2"
          >
            <option value="24h">24 Hours</option>
            <option value="7d">7 Days</option>
            <option value="30d">30 Days</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Today's Appointments"
          value={formatNumber(todayAppointments.length)}
          icon={<Calendar />}
        />
        <MetricCard
          title="Emergency Requests"
          value={formatNumber(metrics.emergencyRequests)}
          icon={<AlertCircle />}
        />
        <MetricCard
          title="Completed Today"
          value={metrics.completedToday}
          icon={<Tool />}
        />
        <MetricCard
          title="Satisfaction"
          value={`${metrics.customerSatisfaction}%`}
          icon={<User />}
        />
      </div>



      <div className="mt-8">
        <DailyTimeline
          appointments={activeAppointments}
          services={services}
          onAppointmentClick={handleOpenCase}
        />
      </div>

      <ReportModal isOpen={showReports} onClose={() => setShowReports(false)} />
    </div>
  )
}

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <circle cx="12" cy="12" r="10"></circle>
      <line x1="12" y1="8" x2="12" y2="12"></line>
      <line x1="12" y1="16" x2="12.01" y2="16"></line>
    </svg>
  )
}
export default Dashboard
