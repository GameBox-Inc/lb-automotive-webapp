import React, { useState } from 'react'
import { Calendar, PenTool as Tool, User, BarChart3, AlertCircle, Wrench } from 'lucide-react'
import { Link } from 'react-router-dom'

import { LoadingSpinner } from '../components/LoadingSpinner'
import { ReportModal } from '../components/ReportModal'
import { useAppointments } from '../hooks/useAppointments'
import { apiClient } from '../lib/supabase'
import { formatNumber } from '../utils/format'
import { DailyTimeline } from '../components/DailyTimeline'

export function Dashboard() {
  const {
    appointments,
    metrics,
    services,
    loading,
    timeframe,
    setTimeframe
  } = useAppointments()

  const [showReports, setShowReports] = useState(false)

  const todayAppointments = appointments.filter(
    (apt) => new Date(apt.appointment_time).toDateString() === new Date().toDateString()
  )

  const MetricCard = ({ title, value, icon }: { title: string, value: string | number, icon: React.ReactElement }) => (
    <div className="group bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 rounded-xl shadow-lg hover:shadow-2xl p-6 border border-gray-100 dark:border-gray-700 transition-all duration-300 hover:-translate-y-2 hover:scale-105 cursor-pointer">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide">{title}</p>
          <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2 transition-all duration-300 group-hover:scale-110">{value}</p>
        </div>
        <div className="p-4 bg-gradient-to-br from-blue-500 to-blue-600 dark:from-blue-600 dark:to-blue-700 rounded-2xl shadow-lg group-hover:shadow-xl group-hover:scale-110 transition-all duration-300">
          {React.cloneElement(icon, { className: 'h-7 w-7 text-white' })}
        </div>
      </div>
      <div className="mt-3 h-1 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transform scale-x-0 group-hover:scale-x-100 transition-transform duration-300 origin-left"></div>
    </div>
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <LoadingSpinner size="lg" />
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
              className="inline-flex items-center px-4 py-2 border border-blue-600 shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 transition-colors"
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

          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value as any)}
            className="block rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white bg-white w-40 p-2"
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
        <DailyTimeline appointments={appointments} services={services} />
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
