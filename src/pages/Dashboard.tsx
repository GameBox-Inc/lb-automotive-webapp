import React from 'react'
import { Calendar, PenTool as Tool, FileText, User } from 'lucide-react'
import { AppointmentCard } from '../components/AppointmentCard'
import { useAppointments } from '../hooks/useAppointments'

export function Dashboard() {
  const { appointments, metrics, loading, timeframe, setTimeframe } = useAppointments()

  const todayAppointments = appointments.filter(
    (apt) => new Date(apt.appointment_time).toDateString() === new Date().toDateString()
  )

  const MetricCard = ({ title, value, icon }) => (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
        </div>
        <div className="p-3 bg-blue-100 rounded-full">
          {React.cloneElement(icon, { className: 'h-6 w-6 text-blue-600' })}
        </div>
      </div>
    </div>
  )

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6">
        <div className="flex gap-2">
          {(['24h', '7d', '30d'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTimeframe(t)}
              className={`px-4 py-2 text-sm font-medium rounded-md ${
                timeframe === t
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <MetricCard
          title="Today's Appointments"
          value={todayAppointments.length}
          icon={<Calendar />}
        />
        <MetricCard
          title="Emergency Requests"
          value={metrics.emergencyRequests}
          icon={<Tool />}
        />
        <MetricCard
          title="Completed Today"
          value={metrics.completedToday}
          icon={<FileText />}
        />
        <MetricCard
          title="Customer Satisfaction"
          value={`${metrics.customerSatisfaction}%`}
          icon={<User />}
        />
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Upcoming Appointments</h2>
        </div>
        {appointments.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-xl text-gray-600">No appointments scheduled</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {appointments.map((appointment) => (
              <AppointmentCard
                key={appointment.id}
                appointment={appointment}
                onUpdate={() => {}} // No need for manual updates with real-time subscriptions
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}